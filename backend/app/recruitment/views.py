"""
Recruitment API (all POST, envelope {status, message, data, errors?}).

  applicant/create/          applicant.create
  applicant/list/            applicant.view   (+ summary counts for the dashboard)
  applicant/detail/          applicant.view   (everything for the 3 tabs in one call)
  applicant/update/          applicant.update (interviewers with applicant.view:
                                               feedback on their own interviews only)
  applicant/status-update/   applicant.status_update
  applicant/verification/    verification.update (checks + offer + complete)
  applicant/onboarding/      onboarding.complete (joining details + checks)
  applicant/convert/         onboarding.complete (employee + salary + user + leave)

Who sees which applicants: users with any recruitment write code (or the
owner) see all; users with only applicant.view see applicants assigned to
them or where they are an interviewer.
"""
import json

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from app.audit.services import log_activity
from common.permissions import OrgAPIView, RequiredPermsMixin, get_user_employee, has_any_perm, has_perm
from common.s3_utils import upload_to_s3
from common.services import get_user_organization

from .models import Applicant, ApplicantDocument
from .serializers import (
    ApplicantCheckSerializer,
    ApplicantDetailSerializer,
    ApplicantDocumentSerializer,
    ApplicantHistorySerializer,
    ApplicantInterviewSerializer,
    ApplicantListSerializer,
    ApplicantOfferSerializer,
    ApplicantWriteSerializer,
    CheckInputSerializer,
    InterviewInputSerializer,
    OfferInputSerializer,
)
from .services import (
    RecruitmentError,
    allowed_actions,
    change_status,
    convert_applicant,
    create_applicant,
    current_offer,
    resolve_position,
    update_applicant,
    update_onboarding,
    update_verification,
)

FULL_ACCESS_CODES = (
    "applicant.create", "applicant.update", "applicant.status_update",
    "verification.update", "onboarding.complete",
)
POSITION_KEYS = ("branch_id", "department_id", "designation_id")


# =========================================================
# SHARED
# =========================================================
class ApplicantBaseAPIView(RequiredPermsMixin, OrgAPIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    # ---- input helpers ----
    @staticmethod
    def json_field(data, key, default=None):
        """Lists / objects may arrive as JSON strings in multipart bodies."""
        value = data.get(key, default)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return default
            try:
                return json.loads(value)
            except ValueError:
                raise RecruitmentError("Validation failed.", {key: ["Must be valid JSON."]})
        return value

    @staticmethod
    def id_list(data, key):
        if hasattr(data, "getlist"):
            values = data.getlist(key)
            if len(values) == 1 and isinstance(values[0], str) and values[0].startswith("["):
                values = json.loads(values[0])
        else:
            values = data.get(key) or []
        try:
            return [int(v) for v in values]
        except (TypeError, ValueError):
            raise RecruitmentError("Validation failed.", {key: ["Must be a list of ids."]})

    @staticmethod
    def plain(data):
        """QueryDict -> dict of single values (multipart); dict passes through."""
        if hasattr(data, "dict"):
            return data.dict()
        return dict(data)

    def uploaded_documents(self, request):
        """resume (single, RESUME) + documents[] with optional document_types[]."""
        out = []
        valid = dict(ApplicantDocument.TYPE_CHOICES)
        resume = request.FILES.get("resume")
        if resume:
            out.append(("RESUME", resume.name, upload_to_s3(file=resume, folder="recruitment/documents")))
        files = request.FILES.getlist("documents")
        types = request.data.getlist("document_types") if hasattr(request.data, "getlist") else []
        for index, file in enumerate(files):
            doc_type = (types[index] if index < len(types) else "OTHER") or "OTHER"
            doc_type = doc_type.upper() if doc_type.upper() in valid else "OTHER"
            out.append((doc_type, file.name, upload_to_s3(file=file, folder="recruitment/documents")))
        return out

    # ---- visibility ----
    def visible_queryset(self, request, organization):
        qs = Applicant.objects.filter(organization=organization, is_active=True).select_related(
            "designation", "department", "branch", "assigned_to", "state", "referred_by",
            "reports_to", "access_role", "employee",
        )
        if has_any_perm(request, organization, FULL_ACCESS_CODES):
            return qs
        employee = get_user_employee(request.user, organization)
        q = Q(assigned_to=request.user)
        if employee:
            q |= Q(interviews__interviewer=employee)
        return qs.filter(q).distinct()

    def get_applicant(self, request, organization):
        applicant_id = request.data.get("applicant_id")
        if not applicant_id:
            return None, self.fail("applicant_id is required.")
        applicant = self.visible_queryset(request, organization).filter(pk=applicant_id).first()
        if applicant is None:
            return None, self.fail("Applicant not found.", http_status=status.HTTP_404_NOT_FOUND)
        return applicant, None

    def detail_data(self, request, organization, applicant):
        applicant = Applicant.objects.select_related(
            "designation", "department", "branch", "assigned_to", "state", "referred_by",
            "reports_to", "access_role", "employee",
        ).get(pk=applicant.pk)
        primary, actions = allowed_actions(applicant, lambda code: has_perm(request, organization, code))
        offer = current_offer(applicant)
        checks = list(applicant.checks.all())
        return {
            "applicant": ApplicantDetailSerializer(applicant).data,
            "documents": ApplicantDocumentSerializer(applicant.documents.all(), many=True).data,
            "interviews": ApplicantInterviewSerializer(
                applicant.interviews.select_related("interviewer"), many=True).data,
            "current_offer": ApplicantOfferSerializer(offer).data if offer else None,
            "offers": ApplicantOfferSerializer(
                applicant.offers.select_related("designation", "department", "branch", "salary_structure"),
                many=True).data,
            "verification_checks": ApplicantCheckSerializer(
                [c for c in checks if c.stage == "VERIFICATION"], many=True).data,
            "onboarding_checks": ApplicantCheckSerializer(
                [c for c in checks if c.stage == "ONBOARDING"], many=True).data,
            "history": ApplicantHistorySerializer(
                applicant.history.select_related("changed_by"), many=True).data,
            "employee": (
                {"id": applicant.employee.id, "employee_code": applicant.employee.employee_code}
                if applicant.employee_id else None
            ),
            "primary_action": primary,
            "allowed_actions": actions,
        }

    def handle_recruitment_error(self, exc):
        if isinstance(exc, RecruitmentError) and exc.errors:
            return self.fail(str(exc), exc.errors)
        return self.fail(str(exc))

    def resolve_people(self, data, organization):
        """assigned_to_id (member user) and referred_by_id (employee)."""
        from app.employees.models import Employee

        out, errors = {}, {}
        if "assigned_to_id" in data:
            value = data.get("assigned_to_id")
            if value in (None, "", "null"):
                out["assigned_to"] = None
            else:
                user = get_user_model().objects.filter(
                    pk=value, is_active=True,
                    organization_memberships__organization=organization,
                    organization_memberships__is_active=True,
                ).first()
                if user is None:
                    errors["assigned_to_id"] = ["User is not an active member of this organization."]
                out["assigned_to"] = user
        if "referred_by_id" in data:
            value = data.get("referred_by_id")
            if value in (None, "", "null"):
                out["referred_by"] = None
            else:
                emp = Employee.objects.filter(pk=value, organization=organization, is_active=True).first()
                if emp is None:
                    errors["referred_by_id"] = ["Active employee not found."]
                out["referred_by"] = emp
        if errors:
            raise RecruitmentError("Validation failed.", errors)
        return out

    def interview_rows(self, data, organization):
        from app.employees.models import Employee

        rows = self.json_field(data, "interviews")
        if rows is None:
            return None
        serializer = InterviewInputSerializer(data=rows, many=True)
        if not serializer.is_valid():
            raise RecruitmentError("Validation failed.", {"interviews": serializer.errors})
        out = []
        for row in serializer.validated_data:
            row = dict(row)
            if "interviewer_id" in row:
                value = row.pop("interviewer_id")
                interviewer = None
                if value:
                    interviewer = Employee.objects.filter(pk=value, organization=organization, is_active=True).first()
                    if interviewer is None:
                        raise RecruitmentError("Validation failed.", {"interviews": [f"Interviewer {value} not found."]})
                row["interviewer"] = interviewer
            out.append(row)
        return out

    def audit(self, request, applicant, action, description):
        try:
            log_activity(request=request, action=action, module="RECRUITMENT", object_type="Applicant",
                         object_id=applicant.id, description=description)
        except Exception:
            pass


# =========================================================
# CREATE
# =========================================================
class ApplicantCreateAPIView(ApplicantBaseAPIView):
    required_perms = ("applicant.create",)

    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        data = self.plain(request.data)
        try:
            for key in ("education", "experience"):
                if key in data:
                    data[key] = self.json_field(data, key, [])
            serializer = ApplicantWriteSerializer(data=data)
            if not serializer.is_valid():
                return self.fail("Validation failed.", serializer.errors)
            position = resolve_position({k: data[k] for k in POSITION_KEYS if k in data}, organization)
            validated = dict(serializer.validated_data)
            validated.update(self.resolve_people(data, organization))
            applicant = create_applicant(organization, validated, position, request.user,
                                         documents=self.uploaded_documents(request))
        except ValueError as exc:
            return self.handle_recruitment_error(exc)

        self.audit(request, applicant, "CREATE", f"Applicant {applicant.applicant_code} created.")
        return self.ok("Applicant created successfully.", self.detail_data(request, organization, applicant),
                       status.HTTP_201_CREATED)


# =========================================================
# LIST
# =========================================================
class ApplicantListAPIView(ApplicantBaseAPIView):
    required_perms = ("applicant.view",)

    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        qs = self.visible_queryset(request, organization)

        search = (request.data.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(applicant_code__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(email__icontains=search)
                | Q(mobile__icontains=search) | Q(position_title__icontains=search)
                | Q(designation__name__icontains=search) | Q(skills__icontains=search)
            )
        summary_qs = qs

        for key, lookup in (("stage", "stage"), ("status", "status"), ("source", "source")):
            value = request.data.get(key)
            if value:
                qs = qs.filter(**{lookup: str(value).upper()})
        for key, lookup in (("designation_id", "designation_id"), ("department_id", "department_id"),
                            ("branch_id", "branch_id"), ("assigned_to_id", "assigned_to_id")):
            value = request.data.get(key)
            if value not in (None, ""):
                try:
                    qs = qs.filter(**{lookup: int(value)})
                except (TypeError, ValueError):
                    return self.fail(f"{key} must be a number.")
        if self.parse_bool(request.data.get("assigned_to_me")):
            qs = qs.filter(assigned_to=request.user)
        for key, lookup in (("applied_from", "applied_on__gte"), ("applied_to", "applied_on__lte")):
            value = request.data.get(key)
            if value:
                qs = qs.filter(**{lookup: value})

        by_stage = dict(summary_qs.order_by().values_list("stage").annotate(n=Count("id", distinct=True)))
        by_status = dict(summary_qs.order_by().values_list("status").annotate(n=Count("id", distinct=True)))
        body = ApplicantListSerializer(qs, many=True).data
        response = self.ok("Applicants fetched successfully.", body)
        response.data["summary"] = {
            "total": sum(by_stage.values()),
            "by_stage": {k: by_stage.get(k, 0) for k, _ in Applicant.STAGE_CHOICES},
            "by_status": {k: by_status.get(k, 0) for k, _ in Applicant.STATUS_CHOICES},
        }
        return response


# =========================================================
# DETAIL
# =========================================================
class ApplicantDetailAPIView(ApplicantBaseAPIView):
    required_perms = ("applicant.view",)

    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        applicant, error = self.get_applicant(request, organization)
        if error:
            return error
        return self.ok("Applicant fetched successfully.", self.detail_data(request, organization, applicant))


# =========================================================
# UPDATE (only changed fields; interviews upsert; documents add/remove)
# =========================================================
class ApplicantUpdateAPIView(ApplicantBaseAPIView):
    required_perms = ("applicant.update", "applicant.view")

    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        applicant, error = self.get_applicant(request, organization)
        if error:
            return error

        full_access = has_perm(request, organization, "applicant.update")
        data = self.plain(request.data)
        try:
            interviews = self.interview_rows(data, organization)
            if full_access:
                for key in ("education", "experience"):
                    if key in data:
                        data[key] = self.json_field(data, key, [])
                serializer = ApplicantWriteSerializer(applicant, data=data, partial=True)
                if not serializer.is_valid():
                    return self.fail("Validation failed.", serializer.errors)
                validated = dict(serializer.validated_data)
                validated.update(self.resolve_people(data, organization))
                position = resolve_position({k: data[k] for k in POSITION_KEYS if k in data}, organization)
                documents = self.uploaded_documents(request)
                remove_docs = self.id_list(request.data, "remove_document_ids")
                remove_interviews = self.id_list(request.data, "remove_interview_ids")
            else:
                if not interviews:
                    return self.fail("You can only record feedback on interviews assigned to you.",
                                     http_status=status.HTTP_403_FORBIDDEN)
                validated, position, documents, remove_docs, remove_interviews = {}, {}, (), (), ()

            applicant = update_applicant(
                applicant, validated, position, request.user,
                interviews=interviews, remove_interview_ids=remove_interviews,
                documents=documents, remove_document_ids=remove_docs,
                interviewer_employee=get_user_employee(request.user, organization),
                full_access=full_access,
            )
        except ValueError as exc:
            if not full_access and "assigned to you" in str(exc):
                return self.fail(str(exc), http_status=status.HTTP_403_FORBIDDEN)
            return self.handle_recruitment_error(exc)

        self.audit(request, applicant, "UPDATE", f"Applicant {applicant.applicant_code} updated.")
        return self.ok("Applicant updated successfully.", self.detail_data(request, organization, applicant))


# =========================================================
# STATUS UPDATE
# =========================================================
class ApplicantStatusUpdateAPIView(ApplicantBaseAPIView):
    required_perms = ("applicant.status_update",)

    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        applicant, error = self.get_applicant(request, organization)
        if error:
            return error
        new_status = str(request.data.get("status") or "").strip().upper()
        if new_status not in dict(Applicant.STATUS_CHOICES):
            return self.fail("status must be PENDING, SHORTLISTED, SELECTED, REJECTED or WITHDRAWN.")
        try:
            applicant = change_status(applicant, new_status, request.user, request.data.get("note"))
        except ValueError as exc:
            return self.handle_recruitment_error(exc)

        self.audit(request, applicant, "UPDATE", f"Applicant {applicant.applicant_code} -> {new_status}.")
        return self.ok("Applicant status updated successfully.", self.detail_data(request, organization, applicant))


# =========================================================
# VERIFICATION (checks, offer, complete)
# =========================================================
class ApplicantVerificationAPIView(ApplicantBaseAPIView):
    required_perms = ("verification.update",)

    def post(self, request):
        from app.payroll.models import SalaryStructure

        organization, error = get_user_organization(request)
        if error:
            return error
        applicant, error = self.get_applicant(request, organization)
        if error:
            return error
        data = request.data
        try:
            checks = self.json_field(data, "checks")
            if checks is not None:
                cs = CheckInputSerializer(data=checks, many=True)
                if not cs.is_valid():
                    return self.fail("Validation failed.", {"checks": cs.errors})
                checks = cs.validated_data

            offer_terms = None
            offer = self.json_field(data, "offer")
            if offer:
                os_ = OfferInputSerializer(data=offer)
                if not os_.is_valid():
                    return self.fail("Validation failed.", {"offer": os_.errors})
                v = dict(os_.validated_data)
                structure = SalaryStructure.objects.filter(
                    pk=v.pop("salary_structure_id"), organization=organization, is_active=True).first()
                if structure is None:
                    return self.fail("Validation failed.", {"offer": {"salary_structure_id": ["Active salary structure not found."]}})
                position = resolve_position({k: v.pop(k) for k in POSITION_KEYS if k in v}, organization)
                offer_terms = {**v, **position, "salary_structure": structure}

            applicant = update_verification(
                applicant, request.user,
                checks=checks,
                offer_terms=offer_terms,
                offer_action=data.get("offer_action"),
                offer_note=data.get("offer_note"),
                complete=bool(self.parse_bool(data.get("complete"))),
            )
        except ValueError as exc:
            return self.handle_recruitment_error(exc)

        self.audit(request, applicant, "UPDATE", f"Applicant {applicant.applicant_code} verification updated.")
        return self.ok("Verification updated successfully.", self.detail_data(request, organization, applicant))


# =========================================================
# ONBOARDING (joining details + checklist)
# =========================================================
class ApplicantOnboardingAPIView(ApplicantBaseAPIView):
    required_perms = ("onboarding.complete",)

    def post(self, request):
        from rest_framework import serializers as drf

        organization, error = get_user_organization(request)
        if error:
            return error
        applicant, error = self.get_applicant(request, organization)
        if error:
            return error
        data = request.data
        try:
            keys = POSITION_KEYS + ("reports_to_id", "access_role_id")
            position = resolve_position(
                {k: data[k] for k in keys if k in data}, organization,
                can_assign_access=has_perm(request, organization, "access.manage"),
            )
            joining_date = None
            if data.get("joining_date"):
                try:
                    joining_date = drf.DateField().to_internal_value(data.get("joining_date"))
                except drf.ValidationError:
                    return self.fail("Validation failed.", {"joining_date": ["Use YYYY-MM-DD."]})
            checks = self.json_field(data, "checks")
            if checks is not None:
                cs = CheckInputSerializer(data=checks, many=True)
                if not cs.is_valid():
                    return self.fail("Validation failed.", {"checks": cs.errors})
                checks = cs.validated_data
            applicant = update_onboarding(
                applicant, request.user, position=position, joining_date=joining_date,
                onboarding_data=self.json_field(data, "onboarding_data"), checks=checks,
            )
        except ValueError as exc:
            return self.handle_recruitment_error(exc)

        self.audit(request, applicant, "UPDATE", f"Applicant {applicant.applicant_code} onboarding updated.")
        return self.ok("Onboarding updated successfully.", self.detail_data(request, organization, applicant))


# =========================================================
# CONVERT
# =========================================================
class ApplicantConvertAPIView(ApplicantBaseAPIView):
    required_perms = ("onboarding.complete",)

    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        applicant, error = self.get_applicant(request, organization)
        if error:
            return error
        # Default: create the login when the caller may create user accounts.
        create_user = self.parse_bool(request.data.get("create_user"))
        if create_user is None:
            create_user = has_perm(request, organization, "employee.create_user")
        if create_user and not has_perm(request, organization, "employee.create_user"):
            return self.fail("You do not have permission to create user accounts.",
                             http_status=status.HTTP_403_FORBIDDEN)
        try:
            result = convert_applicant(applicant, request.user, create_user=bool(create_user))
        except ValueError as exc:
            return self.handle_recruitment_error(exc)

        employee, assignment, account = result["employee"], result["salary_assignment"], result["user"]
        self.audit(request, applicant, "CREATE",
                   f"Applicant {applicant.applicant_code} converted to {employee.employee_code}.")
        data = self.detail_data(request, organization, result["applicant"])
        data["employee"] = {"id": employee.id, "employee_code": employee.employee_code}
        data["salary_assignment"] = {
            "id": assignment.id, "effective_from": str(assignment.effective_from),
            "annual_ctc": str(assignment.annual_ctc), "monthly_gross": str(assignment.monthly_gross),
            "salary_structure_id": assignment.salary_structure_id,
        }
        data["user_account"] = (
            {"user_id": account.id, "username": account.username, "email": account.email}
            if account else None
        )
        message = "Applicant converted to employee."
        if account:
            message += " Account credentials will be sent by email."
        return self.ok(message, data, status.HTTP_201_CREATED)
