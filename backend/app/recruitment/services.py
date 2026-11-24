"""
Recruitment workflow. Views stay thin; every rule lives here.

Raise ValueError (one readable message) or RecruitmentError (field errors)
for anything the caller should see as 400.
"""
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from common.code_generators import generate_applicant_code

from .models import (
    Applicant,
    ApplicantCheck,
    ApplicantDocument,
    ApplicantInterview,
    ApplicantOffer,
    ApplicantStatusHistory,
)


class RecruitmentError(ValueError):
    """ValueError with field errors: {"field": ["message"]}."""

    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or {}


# =========================================================
# CHECKLISTS
# =========================================================
# (key, label, is_system)  system lines are set by the workflow itself.
VERIFICATION_CHECKS = [
    ("PERSONAL_DETAILS", "Personal details", False),
    ("IDENTITY", "Identity documents", False),
    ("EDUCATION", "Education", False),
    ("EXPERIENCE", "Experience", False),
    ("SALARY_OFFER", "Salary offer", True),
    ("OFFER_ACCEPTANCE", "Offer acceptance", True),
]
ONBOARDING_CHECKS = [
    ("JOINING_CONFIRMED", "Joining date confirmed", False),
    ("EMPLOYEE_DETAILS", "Employee details", False),
    ("DOCUMENTS", "Joining documents collected", False),
    ("SALARY_ASSIGNMENT", "Salary assignment", True),
    ("ACCOUNT_CREATION", "User account", True),
]
FINISHED_CHECK = ("DONE", "WAIVED")

# Employee fields an HR user may fill during onboarding (copied on convert).
ONBOARDING_DATA_FIELDS = (
    "work_state_id", "district", "taluka", "pan_number", "pf_uan", "vpf_percentage", "esi_ip_number",
    "tax_regime", "bank_account_number", "bank_ifsc", "bank_name", "bank_branch",
    "upi_id", "emergency_contact_name", "emergency_contact_number",
    "emergency_contact_relation", "attendance_location_exempt",
)

OPEN_OFFER_STATUSES = ("DRAFT", "SENT")


def _history(applicant, action, user, note=None, from_stage=None, from_status=None):
    ApplicantStatusHistory.objects.create(
        applicant=applicant,
        action=action,
        from_stage=from_stage,
        to_stage=applicant.stage,
        from_status=from_status,
        to_status=applicant.status,
        note=note or None,
        changed_by=user,
    )


def ensure_checks(applicant, stage):
    spec = VERIFICATION_CHECKS if stage == "VERIFICATION" else ONBOARDING_CHECKS
    for order, (key, label, is_system) in enumerate(spec):
        ApplicantCheck.objects.get_or_create(
            applicant=applicant, stage=stage, key=key,
            defaults={"label": label, "is_system": is_system, "sort_order": order},
        )


def _set_system_check(applicant, stage, key, status, user, note=None):
    ApplicantCheck.objects.filter(applicant=applicant, stage=stage, key=key).update(
        status=status, note=note, updated_by=user, updated_at=timezone.now(),
    )


def current_offer(applicant):
    """Latest offer that is not superseded (may be accepted / declined / revoked)."""
    return applicant.offers.exclude(status="SUPERSEDED").order_by("-version").first()


# =========================================================
# CREATE / UPDATE
# =========================================================
def find_duplicate(organization, email, mobile, exclude_id=None):
    """Open applicant or active employee with the same email / mobile."""
    from app.employees.models import Employee

    q = Q()
    if email:
        q |= Q(email__iexact=email)
    if mobile:
        q |= Q(mobile=mobile)
    if not q:
        return None
    applicants = Applicant.objects.filter(organization=organization, is_active=True).filter(q).exclude(
        stage__in=("COMPLETED", "CLOSED")
    )
    if exclude_id:
        applicants = applicants.exclude(pk=exclude_id)
    hit = applicants.first()
    if hit:
        return f"An open applicant with this email or mobile already exists ({hit.applicant_code})."

    eq = Q()
    if email:
        eq |= Q(personal_email__iexact=email)
    if mobile:
        eq |= Q(mobile=mobile)
    emp = Employee.objects.filter(organization=organization, is_active=True).filter(eq).first()
    if emp:
        return f"An active employee with this email or mobile already exists ({emp.employee_code})."
    return None


def resolve_position(data, organization, can_assign_access=False):
    """
    Validate designation_id / department_id / branch_id / reports_to_id /
    access_role_id (all optional) with the employees helper. Returns a dict of
    Applicant attribute -> object (only keys that were sent).
    """
    from app.employees.services import resolve_org_assignments

    changes, errors = resolve_org_assignments(data, organization, can_assign_access=can_assign_access)
    if errors:
        raise RecruitmentError("Validation failed.", errors)
    rename = {"department_ref": "department", "designation_ref": "designation"}
    return {rename.get(k, k): v for k, v in changes.items()}


@transaction.atomic
def create_applicant(organization, validated, position, user, documents=()):
    duplicate = find_duplicate(organization, validated.get("email"), validated.get("mobile"))
    if duplicate:
        raise RecruitmentError(duplicate, {"email": [duplicate]})

    applicant = Applicant(organization=organization, created_by=user, updated_by=user, **validated)
    for attr, obj in position.items():
        if attr in ("branch", "department", "designation"):
            setattr(applicant, attr, obj)
    applicant.applicant_code = generate_applicant_code()
    if not applicant.applied_on:
        applicant.applied_on = timezone.localdate()
    applicant.save()

    add_documents(applicant, documents, user)
    _history(applicant, "CREATED", user)
    return applicant


def add_documents(applicant, documents, user):
    """documents: iterable of (document_type, title, stored_path)."""
    for document_type, title, path in documents:
        ApplicantDocument.objects.create(
            applicant=applicant, document_type=document_type, title=title, file=path, uploaded_by=user,
        )


@transaction.atomic
def update_applicant(applicant, validated, position, user, interviews=None, remove_interview_ids=(),
                     documents=(), remove_document_ids=(), interviewer_employee=None, full_access=True):
    """
    full_access=False: the caller only has applicant.view and is an
    interviewer; they may only record result / rating / feedback on their own
    interviews.
    """
    if applicant.stage in ("COMPLETED",):
        raise ValueError("A converted applicant cannot be changed. Update the employee instead.")

    if full_access:
        if "email" in validated or "mobile" in validated:
            duplicate = find_duplicate(
                applicant.organization,
                validated.get("email", applicant.email),
                validated.get("mobile", applicant.mobile),
                exclude_id=applicant.id,
            )
            if duplicate:
                raise RecruitmentError(duplicate, {"email": [duplicate]})
        for field, value in validated.items():
            setattr(applicant, field, value)
        for attr, obj in position.items():
            if attr in ("branch", "department", "designation"):
                setattr(applicant, attr, obj)
        applicant.updated_by = user
        applicant.save()
        add_documents(applicant, documents, user)
        if remove_document_ids:
            applicant.documents.filter(id__in=remove_document_ids).delete()
        if remove_interview_ids:
            applicant.interviews.filter(id__in=remove_interview_ids).delete()

    for row in interviews or []:
        _save_interview(applicant, row, user, interviewer_employee, full_access)

    _history(applicant, "UPDATED", user)
    return applicant


INTERVIEW_FULL_FIELDS = ("round_name", "scheduled_at", "mode", "interviewer", "result", "rating", "feedback")
INTERVIEW_INTERVIEWER_FIELDS = ("result", "rating", "feedback")


def _save_interview(applicant, row, user, interviewer_employee, full_access):
    interview_id = row.get("id")
    if interview_id:
        interview = applicant.interviews.filter(id=interview_id).first()
        if interview is None:
            raise RecruitmentError("Validation failed.", {"interviews": [f"Interview {interview_id} not found."]})
    else:
        if not full_access:
            raise ValueError("You can only record feedback on interviews assigned to you.")
        interview = ApplicantInterview(applicant=applicant, created_by=user)

    if not full_access:
        if interviewer_employee is None or interview.interviewer_id != interviewer_employee.id:
            raise ValueError("You can only record feedback on interviews assigned to you.")
        fields = INTERVIEW_INTERVIEWER_FIELDS
    else:
        fields = INTERVIEW_FULL_FIELDS

    for field in fields:
        if field in row:
            setattr(interview, field, row[field])
    if not interview.round_name:
        raise RecruitmentError("Validation failed.", {"interviews": ["round_name is required."]})
    interview.updated_by = user
    interview.save()


# =========================================================
# STATUS (applicant stage decisions)
# =========================================================
ALLOWED_STATUS_MOVES = {
    # (stage, from_status) -> allowed new statuses
    ("APPLICANT", "PENDING"): {"SHORTLISTED", "SELECTED", "REJECTED", "WITHDRAWN"},
    ("APPLICANT", "SHORTLISTED"): {"PENDING", "SELECTED", "REJECTED", "WITHDRAWN"},
    ("VERIFICATION", "SELECTED"): {"REJECTED", "WITHDRAWN"},
    ("ONBOARDING", "SELECTED"): {"REJECTED", "WITHDRAWN"},
    ("CLOSED", "REJECTED"): {"PENDING"},
    ("CLOSED", "WITHDRAWN"): {"PENDING"},
}


@transaction.atomic
def change_status(applicant, new_status, user, note=None):
    applicant = Applicant.objects.select_for_update().get(pk=applicant.pk)
    allowed = ALLOWED_STATUS_MOVES.get((applicant.stage, applicant.status), set())
    if new_status not in allowed:
        raise ValueError(
            f"Cannot change status from {applicant.status} to {new_status} "
            f"while the applicant is in {applicant.stage}."
        )
    from_stage, from_status = applicant.stage, applicant.status

    applicant.status = new_status
    if new_status == "SELECTED":
        applicant.stage = "VERIFICATION"
    elif new_status in ("REJECTED", "WITHDRAWN"):
        applicant.stage = "CLOSED"
        applicant.offers.filter(status__in=OPEN_OFFER_STATUSES).update(
            status="REVOKED", status_changed_by=user, responded_at=timezone.now(),
        )
    elif new_status == "PENDING" and from_stage == "CLOSED":
        applicant.stage = "APPLICANT"
    applicant.updated_by = user
    applicant.save(update_fields=["status", "stage", "updated_by", "updated_at"])

    if applicant.stage == "VERIFICATION":
        ensure_checks(applicant, "VERIFICATION")
    _history(applicant, "STATUS_CHANGED", user, note, from_stage, from_status)
    return applicant


# =========================================================
# VERIFICATION (checks + offer)
# =========================================================
def _apply_checks(applicant, stage, rows, user):
    """rows: [{"key", "status", "note"?, "label"?}] ; unknown key + label = custom line."""
    for row in rows:
        key = str(row.get("key") or "").strip().upper()
        status = str(row.get("status") or "").strip().upper()
        if not key:
            raise RecruitmentError("Validation failed.", {"checks": ["key is required."]})
        if status and status not in dict(ApplicantCheck.STATUS_CHOICES):
            raise RecruitmentError("Validation failed.", {"checks": [f"Invalid status for {key}."]})
        check = ApplicantCheck.objects.filter(applicant=applicant, stage=stage, key=key).first()
        if check is None:
            label = (row.get("label") or "").strip()
            if not label:
                raise RecruitmentError("Validation failed.", {"checks": [f"Unknown check {key}; send a label to add it."]})
            check = ApplicantCheck(applicant=applicant, stage=stage, key=key, label=label, sort_order=50)
        elif check.is_system:
            raise RecruitmentError("Validation failed.", {"checks": [f"{check.label} is updated automatically."]})
        if status:
            check.status = status
        if "note" in row:
            check.note = row.get("note") or None
        check.updated_by = user
        check.save()


def create_offer(applicant, terms, user):
    """
    terms: salary_structure (obj), joining_date, annual_ctc | monthly_gross,
           designation / department / branch (objs, default = applicant's), notes.
    Supersedes any open offer. Returns the new ApplicantOffer.
    """
    from app.payroll.services import compute_ctc_breakup, monthly_gross_from_annual_ctc

    structure = terms["salary_structure"]
    if structure.organization_id != applicant.organization_id or not structure.is_active:
        raise RecruitmentError("Validation failed.", {"salary_structure_id": ["Active salary structure not found."]})
    annual_ctc, monthly_gross = terms.get("annual_ctc"), terms.get("monthly_gross")
    if annual_ctc is None and monthly_gross is None:
        raise RecruitmentError("Validation failed.", {"annual_ctc": ["Send annual_ctc or monthly_gross."]})

    org = applicant.organization
    as_of = terms["joining_date"]
    if monthly_gross is None:
        breakup = monthly_gross_from_annual_ctc(org, structure, annual_ctc, as_of=as_of)
        monthly_gross = breakup["monthly_gross"]
    else:
        breakup = compute_ctc_breakup(org, structure, monthly_gross, as_of=as_of)
        if annual_ctc is None:
            annual_ctc = breakup["annual_ctc"]

    from app.payroll.services.calculator import _jsonable

    previous = applicant.offers.filter(status__in=OPEN_OFFER_STATUSES)
    previous.update(status="SUPERSEDED", status_changed_by=user)
    last = applicant.offers.order_by("-version").first()

    offer = ApplicantOffer.objects.create(
        applicant=applicant,
        version=(last.version + 1) if last else 1,
        status="DRAFT",
        designation=terms.get("designation", applicant.designation),
        department=terms.get("department", applicant.department),
        branch=terms.get("branch", applicant.branch),
        joining_date=terms["joining_date"],
        salary_structure=structure,
        annual_ctc=annual_ctc,
        monthly_gross=monthly_gross,
        breakup=_jsonable(breakup),
        notes=terms.get("notes") or None,
        probation_months=terms.get("probation_months"),
        notice_period_days=terms.get("notice_period_days"),
        valid_until=terms.get("valid_until"),
        created_by=user,
    )
    _set_system_check(applicant, "VERIFICATION", "SALARY_OFFER", "DONE", user, f"Offer v{offer.version}")
    _set_system_check(applicant, "VERIFICATION", "OFFER_ACCEPTANCE", "PENDING", user)
    _history(applicant, "OFFER_CREATED", user, f"Offer v{offer.version}: CTC {annual_ctc}")
    return offer


OFFER_ACTIONS = {
    # action: (allowed from, new status)
    "SEND": (("DRAFT", "SENT"), "SENT"),       # SENT again = resend the email
    "ACCEPT": (("DRAFT", "SENT"), "ACCEPTED"),
    "DECLINE": (("DRAFT", "SENT"), "DECLINED"),
    "REVOKE": (("DRAFT", "SENT"), "REVOKED"),
}


def set_offer_status(applicant, action, user, note=None, via="HR"):
    action = str(action or "").strip().upper()
    if action not in OFFER_ACTIONS:
        raise RecruitmentError("Validation failed.", {"offer_action": ["Use SEND, ACCEPT, DECLINE or REVOKE."]})
    offer = current_offer(applicant)
    if offer is None:
        raise ValueError("Create an offer first.")
    allowed_from, new_status = OFFER_ACTIONS[action]
    if offer.status not in allowed_from:
        raise ValueError(f"Offer v{offer.version} is {offer.status}; it cannot be {new_status.lower()}.")

    if action == "SEND" and offer.status == "SENT":
        return offer  # already sent; the caller re-sends the email

    offer.status = new_status
    offer.status_changed_by = user
    now = timezone.now()
    fields = ["status", "status_changed_by", "sent_at", "responded_at"]
    if new_status == "SENT":
        offer.sent_at = now
    else:
        offer.responded_at = now
        if new_status in ("ACCEPTED", "DECLINED"):
            offer.responded_via = via
            offer.response_note = note or None
            fields += ["responded_via", "response_note"]
    offer.save(update_fields=fields)

    if new_status == "ACCEPTED":
        _set_system_check(applicant, "VERIFICATION", "OFFER_ACCEPTANCE", "DONE", user, f"Offer v{offer.version}")
    elif new_status == "DECLINED":
        _set_system_check(applicant, "VERIFICATION", "OFFER_ACCEPTANCE", "REJECTED", user, note)
    elif new_status == "REVOKED":
        _set_system_check(applicant, "VERIFICATION", "SALARY_OFFER", "PENDING", user, f"Offer v{offer.version} revoked")
        _set_system_check(applicant, "VERIFICATION", "OFFER_ACCEPTANCE", "PENDING", user)
    who = "by the candidate (email link)" if via == "CANDIDATE" else ""
    _history(applicant, f"OFFER_{new_status}", user,
             " ".join(p for p in [f"Offer v{offer.version}", who, note or ""] if p))
    return offer


def _pending_checks(applicant, stage, exclude_keys=()):
    return list(
        applicant.checks.filter(stage=stage)
        .exclude(status__in=FINISHED_CHECK)
        .exclude(key__in=exclude_keys)
        .values_list("label", flat=True)
    )


@transaction.atomic
def update_verification(applicant, user, checks=None, offer_terms=None, offer_action=None,
                        offer_note=None, complete=False, public_base_url=None, send_email=True,
                        email_message=None):
    applicant = Applicant.objects.select_for_update().get(pk=applicant.pk)
    if applicant.stage != "VERIFICATION":
        raise ValueError(f"The applicant is in {applicant.stage}, not VERIFICATION.")
    ensure_checks(applicant, "VERIFICATION")

    if offer_terms:
        create_offer(applicant, offer_terms, user)
    if offer_action:
        offer = set_offer_status(applicant, offer_action, user, offer_note)
        if str(offer_action).strip().upper() == "SEND" and send_email:
            send_offer_email(offer, public_base_url, user, email_message)
    if checks:
        _apply_checks(applicant, "VERIFICATION", checks, user)

    if complete:
        offer = current_offer(applicant)
        if offer is None or offer.status != "ACCEPTED":
            raise ValueError("The offer must be accepted before verification can be completed.")
        pending = _pending_checks(applicant, "VERIFICATION")
        if pending:
            raise ValueError("Verification is not complete: " + ", ".join(pending) + ".")
        from_stage = applicant.stage
        applicant.stage = "ONBOARDING"
        # Offer terms become the onboarding defaults.
        applicant.joining_date = applicant.joining_date or offer.joining_date
        applicant.designation = offer.designation or applicant.designation
        applicant.department = offer.department or applicant.department
        applicant.branch = offer.branch or applicant.branch
        applicant.updated_by = user
        applicant.save()
        ensure_checks(applicant, "ONBOARDING")
        _history(applicant, "VERIFICATION_COMPLETED", user, None, from_stage, applicant.status)
    return applicant


# =========================================================
# ONBOARDING
# =========================================================
@transaction.atomic
def update_onboarding(applicant, user, position=None, joining_date=None, onboarding_data=None, checks=None):
    applicant = Applicant.objects.select_for_update().get(pk=applicant.pk)
    if applicant.stage != "ONBOARDING":
        raise ValueError(f"The applicant is in {applicant.stage}, not ONBOARDING.")
    ensure_checks(applicant, "ONBOARDING")

    for attr, obj in (position or {}).items():
        setattr(applicant, attr, obj)
    if joining_date:
        applicant.joining_date = joining_date
    if onboarding_data:
        unknown = sorted(set(onboarding_data) - set(ONBOARDING_DATA_FIELDS))
        if unknown:
            raise RecruitmentError("Validation failed.", {"onboarding_data": [f"Unknown fields: {', '.join(unknown)}."]})
        merged = dict(applicant.onboarding_data or {})
        merged.update(onboarding_data)
        applicant.onboarding_data = merged
    applicant.updated_by = user
    applicant.save()

    if checks:
        _apply_checks(applicant, "ONBOARDING", checks, user)
    _history(applicant, "ONBOARDING_UPDATED", user)
    return applicant


# =========================================================
# CONVERT  (one transaction: employee + salary + user + leave)
# =========================================================
EMPLOYEE_COPY_FIELDS = (
    "first_name", "middle_name", "last_name", "date_of_birth", "gender",
    "mobile", "alternate_mobile", "address", "pincode",
)


@transaction.atomic
def convert_applicant(applicant, user, create_user=True):
    from app.accounts.models import OrganizationMembership
    from app.employees.models import Employee, EmployeeDocument
    from app.employees.services import create_employee_user
    from app.leave.models import LeaveType
    from app.leave.services import get_or_create_leave_balance
    from app.payroll.models import PayrollSettings
    from app.payroll.services import bulk_assign_salary, compute_cycle_period
    from rest_framework.exceptions import ValidationError as DRFValidationError

    applicant = Applicant.objects.select_for_update().get(pk=applicant.pk)
    if applicant.stage == "COMPLETED" or applicant.employee_id:
        raise ValueError("This applicant is already an employee.")
    if applicant.stage != "ONBOARDING" or applicant.status != "SELECTED":
        raise ValueError("Only a selected applicant in ONBOARDING can be converted.")

    offer = current_offer(applicant)
    if offer is None or offer.status != "ACCEPTED":
        raise ValueError("The applicant has no accepted offer.")
    if not applicant.joining_date:
        raise ValueError("Set the joining date first.")
    pending = _pending_checks(applicant, "ONBOARDING", exclude_keys=("SALARY_ASSIGNMENT", "ACCOUNT_CREATION"))
    if pending:
        raise ValueError("Onboarding is not complete: " + ", ".join(pending) + ".")

    organization = applicant.organization
    settings_obj = PayrollSettings.objects.filter(organization=organization).first()
    if settings_obj is None:
        raise ValueError("Payroll settings are not configured; set them before converting.")

    # ---- Employee ----
    data = applicant.onboarding_data or {}
    employee = Employee(
        organization=organization,
        employee_code=f"TMP-{applicant.applicant_code}",
        personal_email=applicant.email,
        state=applicant.state.state_name if applicant.state_id else None,
        joining_date=applicant.joining_date,
        employment_status="ACTIVE",
        branch=applicant.branch,
        department_ref=applicant.department,
        designation_ref=applicant.designation,
        department=applicant.department.name if applicant.department_id else None,
        designation=(applicant.designation.name if applicant.designation_id else applicant.position_title),
        access_role=applicant.access_role,
        reports_to=applicant.reports_to,
        created_by=user,
        updated_by=user,
        **{f: getattr(applicant, f) for f in EMPLOYEE_COPY_FIELDS},
    )
    for field in ONBOARDING_DATA_FIELDS:
        if data.get(field) not in (None, ""):
            setattr(employee, field, data[field])
    employee.save()
    employee.employee_code = f"EMP-{employee.id:06d}"
    employee.save(update_fields=["employee_code"])

    for doc in applicant.documents.all():
        EmployeeDocument.objects.create(
            employee=employee, title=doc.title or doc.get_document_type_display(),
            file=doc.file.name if doc.file else None, uploaded_by=user,
        )

    # ---- Salary assignment from the accepted offer ----
    # Assignments start on a payroll cycle start; days before the joining date
    # are unpaid through not_employed_days (attendance), as for any joiner.
    cycle_start, _ = compute_cycle_period(settings_obj.cycle_start_day, applicant.joining_date)
    assignment = bulk_assign_salary(
        organization=organization,
        employee_ids=[employee.id],
        salary_structure_id=offer.salary_structure_id,
        effective_from=cycle_start,
        reason=f"Offer v{offer.version} ({applicant.applicant_code})",
        assigned_by=user,
        annual_ctc=offer.annual_ctc,
        monthly_gross=offer.monthly_gross,
    )[0]
    _set_system_check(applicant, "ONBOARDING", "SALARY_ASSIGNMENT", "DONE", user,
                      f"From {cycle_start}, CTC {offer.annual_ctc}")

    # ---- User account ----
    account = None
    if create_user:
        try:
            account, _password = create_employee_user(employee)
        except DRFValidationError as exc:
            raise RecruitmentError("Unable to create the user account.", exc.detail)
        OrganizationMembership.objects.update_or_create(
            organization=organization, user=account, defaults={"is_active": True},
        )
        _set_system_check(applicant, "ONBOARDING", "ACCOUNT_CREATION", "DONE", user, account.username)
    else:
        _set_system_check(applicant, "ONBOARDING", "ACCOUNT_CREATION", "WAIVED", user, "Not requested")

    # ---- Leave balances for the joining year ----
    leave_year = applicant.joining_date.year
    for leave_type in LeaveType.objects.filter(organization=organization, is_active=True):
        get_or_create_leave_balance(employee, leave_type, leave_year, created_by=user)

    from_stage = applicant.stage
    applicant.stage = "COMPLETED"
    applicant.employee = employee
    applicant.converted_at = timezone.now()
    applicant.updated_by = user
    applicant.save(update_fields=["stage", "employee", "converted_at", "updated_by", "updated_at"])
    _history(applicant, "CONVERTED", user, f"Employee {employee.employee_code}", from_stage, applicant.status)

    return {"applicant": applicant, "employee": employee, "salary_assignment": assignment, "user": account}


# =========================================================
# UI HELPERS
# =========================================================
def allowed_actions(applicant, can):
    """
    can(code) -> bool. Returns (primary_action, [actions]) for the detail page.
    """
    actions = []
    stage, status = applicant.stage, applicant.status
    if stage != "COMPLETED" and can("applicant.update"):
        actions.append("update")
    if can("applicant.status_update") and ALLOWED_STATUS_MOVES.get((stage, status)):
        actions.append("status_update")
    if stage == "VERIFICATION" and can("verification.update"):
        actions += ["verification", "offer"]
    if stage == "ONBOARDING" and can("onboarding.complete"):
        actions += ["onboarding", "convert"]
    if stage == "COMPLETED":
        actions.append("view_employee")

    primary = {
        "APPLICANT": "status_update",
        "VERIFICATION": "verification",
        "ONBOARDING": "convert",
        "COMPLETED": "view_employee",
        "CLOSED": "status_update",
    }.get(stage)
    if primary not in actions:
        primary = actions[0] if actions else None
    return primary, actions


# =========================================================
# OFFER LETTER: PDF, EMAIL, CANDIDATE RESPONSE (batch 5)
# Templates: recruitment/templates/offer_letter.html (PDF),
#            offer_letter_email.html (email), offer_response.html (public page)
# =========================================================
def _money(value):
    """'622500.00' -> '6,22,500.00' (Indian grouping)."""
    from decimal import Decimal, InvalidOperation

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    sign = "-" if amount < 0 else ""
    whole, _, frac = f"{abs(amount):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{frac}"


def offer_letter_context(offer):
    """Everything the offer templates need (company data from the organization)."""
    from common.branding import get_organization_branding, load_organization_logo

    applicant = offer.applicant
    organization = applicant.organization
    branding = get_organization_branding(organization)
    logo_data, _name, logo_mime = load_organization_logo(organization, as_base64=True)
    breakup = offer.breakup or {}
    employer = breakup.get("employer_contributions") or {}

    earnings = [
        {"name": row.get("name") or row.get("code"), "monthly": _money(row.get("monthly")),
         "annual": _money(row.get("annual"))}
        for row in breakup.get("earnings", [])
    ]
    from decimal import Decimal

    employer_rows = [
        {"name": label, "monthly": _money(employer.get(key)),
         "annual": _money(Decimal(str(employer.get(key) or 0)) * 12)}
        for key, label in (("pf_employer", "Employer PF"), ("edli", "EDLI"),
                           ("esi_employer", "Employer ESI"), ("lwf_employer", "Employer LWF"))
        if employer.get(key) not in (None, "0", "0.00", 0)
    ]
    return {
        **branding,
        "logo_data": logo_data,
        "logo_mime": logo_mime or "image/png",
        "applicant": applicant,
        "offer": offer,
        "designation": offer.designation.name if offer.designation_id else (applicant.position_title or ""),
        "department": offer.department.name if offer.department_id else "",
        "branch": offer.branch.name if offer.branch_id else "",
        "annual_ctc": _money(offer.annual_ctc),
        "monthly_gross": _money(offer.monthly_gross),
        "monthly_ctc": _money(breakup.get("monthly_ctc")),
        "annual_gross": _money(breakup.get("annual_gross")),
        "earnings": earnings,
        "employer_rows": employer_rows,
        "ctc_includes_employer": breakup.get("ctc_includes_employer_contributions", True),
        "letter_date": timezone.localdate(offer.sent_at) if offer.sent_at else timezone.localdate(),
        "reference": f"{applicant.applicant_code}/OFFER/V{offer.version}",
    }


def render_offer_letter_pdf(offer):
    """Offer letter PDF bytes (WeasyPrint, same engine as the project invoice)."""
    from django.template.loader import render_to_string
    from weasyprint import HTML

    html = render_to_string("offer_letter.html", offer_letter_context(offer))
    return HTML(string=html).write_pdf()


def offer_letter_filename(offer):
    return f"Offer_Letter_{offer.applicant.applicant_code}_v{offer.version}.pdf"


def offer_response_url(offer, public_base_url):
    base = (public_base_url or "").rstrip("/")
    return f"{base}/recruitment/offer/{offer.response_token}/"


def send_offer_email(offer, public_base_url, user=None, message=None):
    """
    Email the candidate: message + offer letter PDF + Accept / Decline link.
    Can be called again while the offer is SENT (resend). The link stays the same.
    """
    import secrets

    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    if offer.status != "SENT":
        raise ValueError("Only a sent offer can be emailed.")
    applicant = offer.applicant
    if not applicant.email:
        raise ValueError("The applicant has no email address.")
    if not public_base_url:
        raise ValueError("Public link address is not available.")

    if not offer.response_token:
        offer.response_token = secrets.token_urlsafe(32)

    context = offer_letter_context(offer)
    context.update({"message": message, "response_url": offer_response_url(offer, public_base_url)})
    html_body = render_to_string("offer_letter_email.html", context)
    text_body = (
        f"Dear {applicant.full_name},\n\n"
        f"We are pleased to offer you the position of {context['designation']} at "
        f"{context['company_name']}. Your offer letter is attached.\n\n"
        + (f"{message}\n\n" if message else "")
        + f"Please accept or decline the offer here: {context['response_url']}\n"
        + (f"This offer is valid until {offer.valid_until:%d %b %Y}.\n" if offer.valid_until else "")
        + f"\nRegards,\n{context['company_name']}"
    )

    email = EmailMultiAlternatives(
        subject=f"Offer of employment - {context['designation']} - {context['company_name']}".strip(" -"),
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[applicant.email],
        reply_to=[context["company_email"]] if context.get("company_email") else None,
    )
    email.attach_alternative(html_body, "text/html")
    email.attach(offer_letter_filename(offer), render_offer_letter_pdf(offer), "application/pdf")
    try:
        email.send(fail_silently=False)
    except Exception as exc:
        raise ValueError(f"Unable to send the offer email: {exc}")

    offer.email_count += 1
    offer.last_emailed_at = timezone.now()
    offer.save(update_fields=["response_token", "email_count", "last_emailed_at"])
    _history(applicant, "OFFER_EMAILED", user,
             f"Offer v{offer.version} emailed to {applicant.email} (#{offer.email_count})")
    return offer


def offer_link_state(offer):
    """What the public page shows: OPEN, ACCEPTED, DECLINED, EXPIRED, CLOSED."""
    if offer is None:
        return "CLOSED"
    if offer.status in ("ACCEPTED", "DECLINED"):
        return offer.status
    if offer.status != "SENT" or offer.applicant.stage != "VERIFICATION":
        return "CLOSED"     # revoked, superseded, or the applicant moved on
    if offer.valid_until and timezone.localdate() > offer.valid_until:
        return "EXPIRED"
    return "OPEN"


def _offer_watchers(offer):
    """HR users told about the candidate's answer."""
    from app.employees.models import Employee

    applicant = offer.applicant
    users = {}
    for user in (offer.created_by, getattr(applicant.assigned_to, "user", None), applicant.organization.owner):
        if user is not None:
            users[user.id] = user
    holders = Employee.objects.filter(
        organization=applicant.organization, is_active=True, user__isnull=False,
        access_role__is_active=True, access_role__permissions__code="verification.update",
    ).select_related("user").distinct()
    for emp in holders:
        users[emp.user.id] = emp.user
    return list(users.values())


@transaction.atomic
def respond_to_offer(token, action, note=None):
    """
    Candidate's answer through the emailed link. Final: once accepted or
    declined it cannot be changed (by the candidate or by HR).
    """
    action = str(action or "").strip().upper()
    if action not in ("ACCEPT", "DECLINE"):
        raise ValueError("Choose Accept or Decline.")
    offer = (
        ApplicantOffer.objects.select_for_update()
        .select_related("applicant", "applicant__organization")
        .filter(response_token=token).first()
    )
    state = offer_link_state(offer)
    if state != "OPEN":
        raise ValueError({
            "ACCEPTED": "You have already accepted this offer.",
            "DECLINED": "You have already declined this offer.",
            "EXPIRED": "This offer has expired. Please contact the company.",
        }.get(state, "This offer is no longer available."))

    set_offer_status(offer.applicant, action, None, (note or "").strip()[:1000] or None, via="CANDIDATE")
    offer.refresh_from_db()

    from app.communications.notification_service import notify

    watchers = _offer_watchers(offer)
    verb = "accepted" if offer.status == "ACCEPTED" else "declined"
    transaction.on_commit(lambda: notify(
        users=watchers,
        event_code=f"OFFER_{offer.status}",
        title=f"Offer {verb}",
        body=f"{offer.applicant.full_name} ({offer.applicant.applicant_code}) {verb} offer v{offer.version}.",
        reference_type="applicant",
        reference_id=offer.applicant_id,
        priority="HIGH",
    ))
    return offer
