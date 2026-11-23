from rest_framework import serializers

from app.location_master.models import StateMaster

from .models import (
    Applicant,
    ApplicantCheck,
    ApplicantDocument,
    ApplicantInterview,
    ApplicantOffer,
    ApplicantStatusHistory,
)


def _ref(obj, attr="name"):
    return {"id": obj.id, "name": getattr(obj, attr)} if obj else None


def _emp_ref(emp):
    if not emp:
        return None
    return {"id": emp.id, "employee_code": emp.employee_code,
            "full_name": " ".join(p for p in [emp.first_name, emp.middle_name, emp.last_name] if p)}


def _user_ref(user):
    if not user:
        return None
    return {"id": user.id, "name": (f"{user.first_name} {user.last_name}".strip() or user.username)}


# =========================================================
# INPUT
# =========================================================
class EducationRowSerializer(serializers.Serializer):
    degree = serializers.CharField(max_length=150)
    institution = serializers.CharField(max_length=200, required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, allow_null=True, min_value=1950, max_value=2100)
    score = serializers.CharField(max_length=30, required=False, allow_blank=True)


class ExperienceRowSerializer(serializers.Serializer):
    company = serializers.CharField(max_length=200)
    designation = serializers.CharField(max_length=150, required=False, allow_blank=True)
    from_date = serializers.DateField(required=False, allow_null=True)
    to_date = serializers.DateField(required=False, allow_null=True)
    ctc = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    reason_for_leaving = serializers.CharField(required=False, allow_blank=True)


class ApplicantWriteSerializer(serializers.ModelSerializer):
    """Personal + profile fields. Position ids are validated separately."""

    state_id = serializers.PrimaryKeyRelatedField(
        source="state", queryset=StateMaster.objects.filter(is_active=True), required=False, allow_null=True,
    )
    education = EducationRowSerializer(many=True, required=False)
    experience = ExperienceRowSerializer(many=True, required=False)

    class Meta:
        model = Applicant
        fields = [
            "first_name", "middle_name", "last_name", "email", "mobile", "alternate_mobile",
            "date_of_birth", "gender", "address", "city", "state_id", "pincode",
            "position_title", "source", "applied_on",
            "total_experience_years", "current_company", "current_designation",
            "current_ctc", "expected_ctc", "notice_period_days", "skills",
            "education", "experience", "remarks",
        ]
        extra_kwargs = {"applied_on": {"required": False}}

    def validate_email(self, value):
        return value.strip().lower()

    def validate_mobile(self, value):
        return value.strip()

    def _jsonable_rows(self, rows):
        out = []
        for row in rows:
            out.append({k: (str(v) if v is not None and not isinstance(v, (str, int, float)) else v)
                        for k, v in row.items()})
        return out

    def validate(self, attrs):
        for key in ("education", "experience"):
            if key in attrs:
                attrs[key] = self._jsonable_rows(attrs[key])
        return attrs


class InterviewInputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    round_name = serializers.CharField(max_length=100, required=False)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    mode = serializers.ChoiceField(choices=ApplicantInterview.MODE_CHOICES, required=False)
    interviewer_id = serializers.IntegerField(required=False, allow_null=True)
    result = serializers.ChoiceField(choices=ApplicantInterview.RESULT_CHOICES, required=False)
    rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)
    feedback = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CheckInputSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=40)
    status = serializers.ChoiceField(choices=ApplicantCheck.STATUS_CHOICES, required=False)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    label = serializers.CharField(max_length=150, required=False, allow_blank=True)


class OfferInputSerializer(serializers.Serializer):
    salary_structure_id = serializers.IntegerField()
    joining_date = serializers.DateField()
    annual_ctc = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True, min_value=1)
    monthly_gross = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=1)
    designation_id = serializers.IntegerField(required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    probation_months = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=36)
    notice_period_days = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=365)
    valid_until = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        from django.utils import timezone

        if attrs.get("annual_ctc") is None and attrs.get("monthly_gross") is None:
            raise serializers.ValidationError({"annual_ctc": "Send annual_ctc or monthly_gross."})
        valid_until = attrs.get("valid_until")
        if valid_until and valid_until < timezone.localdate():
            raise serializers.ValidationError({"valid_until": "Must be today or later."})
        return attrs


# =========================================================
# OUTPUT
# =========================================================
class ApplicantListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    designation = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = [
            "id", "applicant_code", "full_name", "email", "mobile",
            "designation", "position_title", "department", "branch",
            "source", "applied_on", "total_experience_years", "expected_ctc",
            "stage", "status", "assigned_to", "joining_date", "employee", "created_at",
        ]

    def get_designation(self, obj):
        return _ref(obj.designation)

    def get_department(self, obj):
        return _ref(obj.department)

    def get_branch(self, obj):
        return _ref(obj.branch)

    def get_assigned_to(self, obj):
        return _emp_ref(obj.assigned_to)


class ApplicantDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicantDocument
        fields = ["id", "document_type", "title", "file", "created_at"]


class ApplicantInterviewSerializer(serializers.ModelSerializer):
    interviewer = serializers.SerializerMethodField()

    class Meta:
        model = ApplicantInterview
        fields = ["id", "round_name", "scheduled_at", "mode", "interviewer", "result", "rating", "feedback", "updated_at"]

    def get_interviewer(self, obj):
        return _emp_ref(obj.interviewer)


class ApplicantHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = ApplicantStatusHistory
        fields = ["id", "action", "from_stage", "to_stage", "from_status", "to_status", "note", "changed_by", "created_at"]

    def get_changed_by(self, obj):
        return _user_ref(obj.changed_by)


class ApplicantOfferSerializer(serializers.ModelSerializer):
    designation = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    salary_structure = serializers.SerializerMethodField()

    class Meta:
        model = ApplicantOffer
        fields = [
            "id", "version", "status", "designation", "department", "branch", "joining_date",
            "salary_structure", "annual_ctc", "monthly_gross", "breakup", "notes",
            "probation_months", "notice_period_days", "valid_until",
            "responded_via", "response_note", "email_count", "last_emailed_at",
            "created_at", "sent_at", "responded_at",
        ]

    def get_designation(self, obj):
        return _ref(obj.designation)

    def get_department(self, obj):
        return _ref(obj.department)

    def get_branch(self, obj):
        return _ref(obj.branch)

    def get_salary_structure(self, obj):
        return _ref(obj.salary_structure)


class ApplicantCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicantCheck
        fields = ["key", "label", "status", "is_system", "note", "updated_at"]


class ApplicantDetailSerializer(ApplicantListSerializer):
    state = serializers.SerializerMethodField()
    referred_by = serializers.SerializerMethodField()
    reports_to = serializers.SerializerMethodField()
    access_role = serializers.SerializerMethodField()

    class Meta(ApplicantListSerializer.Meta):
        fields = ApplicantListSerializer.Meta.fields + [
            "first_name", "middle_name", "last_name", "alternate_mobile", "date_of_birth", "gender",
            "address", "city", "state", "pincode", "referred_by",
            "current_company", "current_designation", "current_ctc", "notice_period_days",
            "skills", "education", "experience", "remarks",
            "reports_to", "access_role", "onboarding_data", "converted_at", "updated_at",
        ]

    def get_state(self, obj):
        return _ref(obj.state, "state_name")

    def get_referred_by(self, obj):
        return _emp_ref(obj.referred_by)

    def get_reports_to(self, obj):
        return _emp_ref(obj.reports_to)

    def get_access_role(self, obj):
        return _ref(obj.access_role)
