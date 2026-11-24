"""
Visitors API (all POST, envelope {status, message, data, errors?}).

  visit/create|list|detail|update|check-out|deactivate/   visitor.manage
  visit/lookup/                                          visitor.manage (autofill by mobile)
  visit/my-visitors/                                     any employee (visits where I am the host)

The front desk adds visits; check-in / check-out are optional and nothing
is closed automatically.
"""
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from app.audit.services import log_activity
from common.code_generators import generate_visit_code
from common.permissions import OrgAPIView, RequiredPermsMixin, get_user_employee
from common.s3_utils import upload_to_s3
from common.services import get_user_organization

from .models import Visit
from .serializers import MyVisitSerializer, VisitSerializer, VisitWriteSerializer

VISIT_RELATED = ("host", "branch", "created_by")
TEXT_FIELDS = ("visitor_email", "visitor_company", "purpose_note", "id_proof_type", "id_proof_last4",
               "badge_number", "vehicle_number", "notes")


# =========================================================
# SHARED
# =========================================================
class VisitorBaseAPIView(RequiredPermsMixin, OrgAPIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_org(self, request):
        return get_user_organization(request)

    def get_visit(self, request, organization):
        visit_id = request.data.get("visit_id")
        if not visit_id:
            return None, self.fail("visit_id is required.")
        visit = (
            Visit.objects.filter(pk=visit_id, organization=organization, is_active=True)
            .select_related(*VISIT_RELATED).first()
        )
        if visit is None:
            return None, self.fail("Visit not found.", http_status=status.HTTP_404_NOT_FOUND)
        return visit, None

    def resolve_links(self, organization, data):
        """host_id (employee) and branch_id -> objects; returns (values, error_response)."""
        from app.accounts.models import Branch
        from app.employees.models import Employee

        out = {}
        if "host_id" in data:
            value = data.get("host_id")
            if value in (None, "", "null"):
                out["host"] = None
            else:
                host = Employee.objects.filter(pk=value, organization=organization, is_active=True).first()
                if host is None:
                    return None, self.fail("Validation failed.", {"host_id": ["Active employee not found."]})
                out["host"] = host
        if "branch_id" in data:
            value = data.get("branch_id")
            if value in (None, "", "null"):
                out["branch"] = None
            else:
                branch = Branch.objects.filter(pk=value, organization=organization, is_active=True).first()
                if branch is None:
                    return None, self.fail("Validation failed.", {"branch_id": ["Active branch not found."]})
                out["branch"] = branch
        return out, None

    @staticmethod
    def date_range(qs, from_date, to_date):
        # Local-day bounds as datetimes (no __date lookups: MySQL needs time
        # zone tables for those when TIME_ZONE is not UTC).
        start = timezone.make_aware(datetime.combine(from_date, time.min))
        end = timezone.make_aware(datetime.combine(to_date + timedelta(days=1), time.min))
        day = Q(check_in_at__gte=start, check_in_at__lt=end)
        no_check_in = Q(check_in_at__isnull=True, created_at__gte=start, created_at__lt=end)
        return qs.filter(day | no_check_in)

    def parse_dates(self, data, default_days=0):
        from django.utils.dateparse import parse_date

        today = timezone.localdate()
        try:
            from_date = parse_date(str(data.get("from_date"))) if data.get("from_date") else today - timedelta(days=default_days)
            to_date = parse_date(str(data.get("to_date"))) if data.get("to_date") else today
        except ValueError:
            from_date = to_date = None
        if from_date is None or to_date is None:
            return None, None, self.fail("from_date / to_date must use YYYY-MM-DD format.")
        if from_date > to_date:
            return None, None, self.fail("from_date cannot be after to_date.")
        return from_date, to_date, None


# =========================================================
# VISIT — CREATE
# =========================================================
class VisitCreateAPIView(VisitorBaseAPIView):
    required_perms = ("visitor.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        s = VisitWriteSerializer(data=request.data)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data
        links, err = self.resolve_links(organization, data)
        if err:
            return err

        check_in_at = data["check_in_at"] if "check_in_at" in data else timezone.now()
        check_out_at = data.get("check_out_at")
        if check_out_at and (check_in_at is None or check_out_at < check_in_at):
            return self.fail("Validation failed.", {"check_out_at": ["Must be after check_in_at."]})

        photo = request.FILES.get("photo")
        with transaction.atomic():
            visit = Visit.objects.create(
                organization=organization,
                visit_code=generate_visit_code(),
                visitor_name=data["visitor_name"].strip(),
                visitor_mobile=data["visitor_mobile"].strip(),
                visitor_count=data.get("visitor_count") or 1,
                purpose=data["purpose"],
                check_in_at=check_in_at,
                check_out_at=check_out_at,
                photo=upload_to_s3(file=photo, folder="visitors/photos") if photo else None,
                created_by=request.user,
                updated_by=request.user,
                **links,
                **{f: (str(data.get(f)).strip() or None) if data.get(f) else None for f in TEXT_FIELDS},
            )
            host = visit.host
            if host is not None and host.user_id and visit.check_in_at and not visit.check_out_at:
                from app.communications.notification_service import notify

                user = host.user
                company = f" ({visit.visitor_company})" if visit.visitor_company else ""
                transaction.on_commit(lambda: notify(
                    users=user, event_code="VISITOR_ARRIVED",
                    title="Your visitor has arrived",
                    body=f"{visit.visitor_name}{company} is at the front desk.",
                    reference_type="visit", reference_id=visit.id,
                ))

        log_activity(
            request=request, action="CREATE", module="VISITOR", object_type="Visit",
            object_id=visit.id, description=f"Visit {visit.visit_code} added.",
            new_data={"visitor_name": visit.visitor_name, "visitor_mobile": visit.visitor_mobile,
                      "purpose": visit.purpose, "host_id": visit.host_id},
        )
        visit = Visit.objects.select_related(*VISIT_RELATED).get(pk=visit.pk)
        return self.ok("Visit added.", VisitSerializer(visit).data, status.HTTP_201_CREATED)


# =========================================================
# VISIT — LIST
# =========================================================
class VisitListAPIView(VisitorBaseAPIView):
    required_perms = ("visitor.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        data = request.data
        qs = Visit.objects.filter(organization=organization, is_active=True).select_related(*VISIT_RELATED)

        inside_only = self.parse_bool(data.get("inside_only")) is True
        if inside_only and not data.get("from_date") and not data.get("to_date"):
            qs = qs.filter(check_in_at__isnull=False, check_out_at__isnull=True)
        else:
            from_date, to_date, err = self.parse_dates(data)
            if err:
                return err
            qs = self.date_range(qs, from_date, to_date)
            if inside_only:
                qs = qs.filter(check_in_at__isnull=False, check_out_at__isnull=True)

        search = (data.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(visit_code__icontains=search) | Q(visitor_name__icontains=search)
                | Q(visitor_mobile__icontains=search) | Q(visitor_company__icontains=search)
                | Q(badge_number__icontains=search)
            )
        if data.get("purpose"):
            qs = qs.filter(purpose=str(data.get("purpose")).upper())
        if data.get("host_id"):
            qs = qs.filter(host_id=data.get("host_id"))
        if data.get("branch_id"):
            qs = qs.filter(branch_id=data.get("branch_id"))

        return self.ok("Visits fetched.", VisitSerializer(qs, many=True).data)


# =========================================================
# VISIT — DETAIL
# =========================================================
class VisitDetailAPIView(VisitorBaseAPIView):
    required_perms = ("visitor.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        visit, err = self.get_visit(request, organization)
        if err:
            return err
        return self.ok("Visit fetched.", VisitSerializer(visit).data)


# =========================================================
# VISIT — UPDATE
# =========================================================
class VisitUpdateAPIView(VisitorBaseAPIView):
    required_perms = ("visitor.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        visit, err = self.get_visit(request, organization)
        if err:
            return err
        s = VisitWriteSerializer(data=request.data, partial=True)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data
        links, err = self.resolve_links(organization, data)
        if err:
            return err
        old = VisitSerializer(visit).data

        for field in ("visitor_name", "visitor_mobile"):
            if field in data:
                setattr(visit, field, data[field].strip())
        for field in ("purpose", "visitor_count", "check_in_at", "check_out_at"):
            if field in data:
                setattr(visit, field, data[field] if field != "visitor_count" else (data[field] or 1))
        for field in TEXT_FIELDS:
            if field in data:
                setattr(visit, field, (str(data.get(field)).strip() or None) if data.get(field) else None)
        for field, value in links.items():
            setattr(visit, field, value)
        if visit.check_out_at and (visit.check_in_at is None or visit.check_out_at < visit.check_in_at):
            return self.fail("Validation failed.", {"check_out_at": ["Must be after check_in_at."]})

        photo = request.FILES.get("photo")
        if photo:
            visit.photo = upload_to_s3(file=photo, folder="visitors/photos")
        elif self.parse_bool(request.data.get("remove_photo")) is True:
            visit.photo = None

        visit.updated_by = request.user
        visit.save()
        log_activity(
            request=request, action="UPDATE", module="VISITOR", object_type="Visit",
            object_id=visit.id, description=f"Visit {visit.visit_code} updated.",
            old_data=old, new_data=VisitSerializer(visit).data,
        )
        visit = Visit.objects.select_related(*VISIT_RELATED).get(pk=visit.pk)
        return self.ok("Visit updated.", VisitSerializer(visit).data)


# =========================================================
# VISIT — CHECK OUT
# =========================================================
class VisitCheckOutAPIView(VisitorBaseAPIView):
    required_perms = ("visitor.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        visit, err = self.get_visit(request, organization)
        if err:
            return err
        if visit.check_out_at:
            return self.fail("This visitor is already checked out.")
        s = VisitWriteSerializer(data=request.data, partial=True)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        check_out_at = s.validated_data.get("check_out_at") or timezone.now()
        if visit.check_in_at is None:
            visit.check_in_at = min(visit.created_at, check_out_at)
        if check_out_at < visit.check_in_at:
            return self.fail("Validation failed.", {"check_out_at": ["Must be after check_in_at."]})
        visit.check_out_at = check_out_at
        visit.updated_by = request.user
        visit.save(update_fields=["check_in_at", "check_out_at", "updated_by", "updated_at"])
        log_activity(
            request=request, action="UPDATE", module="VISITOR", object_type="Visit",
            object_id=visit.id, description=f"Visit {visit.visit_code} checked out.",
            new_data={"check_out_at": visit.check_out_at.isoformat()},
        )
        return self.ok("Visitor checked out.", VisitSerializer(visit).data)


# =========================================================
# VISIT — DEACTIVATE (remove a wrong entry)
# =========================================================
class VisitDeactivateAPIView(VisitorBaseAPIView):
    required_perms = ("visitor.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        visit, err = self.get_visit(request, organization)
        if err:
            return err
        visit.is_active = False
        visit.updated_by = request.user
        visit.save(update_fields=["is_active", "updated_by", "updated_at"])
        log_activity(
            request=request, action="DELETE", module="VISITOR", object_type="Visit",
            object_id=visit.id, description=f"Visit {visit.visit_code} removed.",
        )
        return self.ok("Visit removed.")


# =========================================================
# VISIT — LOOKUP BY MOBILE (autofill)
# =========================================================
class VisitLookupAPIView(VisitorBaseAPIView):
    required_perms = ("visitor.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        mobile = (request.data.get("visitor_mobile") or "").strip()
        if not mobile:
            return self.fail("visitor_mobile is required.")
        qs = Visit.objects.filter(organization=organization, is_active=True, visitor_mobile=mobile)
        last = qs.order_by("-created_at").first()
        if last is None:
            return self.ok("No earlier visit found.", {"found": False, "visit_count": 0})
        def latest(field):
            # newest non-empty value (a quick entry without company should not blank it)
            row = qs.exclude(**{f"{field}__isnull": True}).exclude(**{field: ""}).order_by("-created_at").first()
            return getattr(row, field) if row else None

        return self.ok("Earlier visit found.", {
            "found": True,
            "visit_count": qs.count(),
            "visitor_name": last.visitor_name,
            "visitor_email": latest("visitor_email"),
            "visitor_company": latest("visitor_company"),
            "last_visit_at": last.check_in_at or last.created_at,
            "last_purpose": last.purpose,
        })


# =========================================================
# VISIT — MY VISITORS (host)
# =========================================================
class MyVisitorListAPIView(VisitorBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        employee = get_user_employee(request.user, organization)
        if employee is None:
            return self.fail("No active employee profile is linked to this user.",
                             http_status=status.HTTP_404_NOT_FOUND)
        from_date, to_date, err = self.parse_dates(request.data, default_days=30)
        if err:
            return err
        qs = self.date_range(Visit.objects.filter(organization=organization, is_active=True, host=employee),
                             from_date, to_date)
        return self.ok("Your visitors fetched.", MyVisitSerializer(qs, many=True).data)
