from rest_framework import serializers

from .models import Visit


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
class VisitWriteSerializer(serializers.Serializer):
    visitor_name = serializers.CharField(max_length=150)
    visitor_mobile = serializers.RegexField(r"^\+?[0-9]{7,15}$", max_length=20,
                                            error_messages={"invalid": "Enter a valid mobile number."})
    visitor_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    visitor_company = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    visitor_count = serializers.IntegerField(required=False, min_value=1, max_value=100)
    purpose = serializers.ChoiceField(choices=Visit.PURPOSE_CHOICES)
    purpose_note = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    host_id = serializers.IntegerField(required=False, allow_null=True)
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    check_in_at = serializers.DateTimeField(required=False, allow_null=True)
    check_out_at = serializers.DateTimeField(required=False, allow_null=True)
    id_proof_type = serializers.ChoiceField(choices=Visit.ID_PROOF_CHOICES, required=False, allow_blank=True, allow_null=True)
    id_proof_last4 = serializers.RegexField(r"^[A-Za-z0-9]{4}$", required=False, allow_blank=True, allow_null=True,
                                            error_messages={"invalid": "Send only the last 4 characters of the ID."})
    badge_number = serializers.CharField(max_length=30, required=False, allow_blank=True, allow_null=True)
    vehicle_number = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


# =========================================================
# OUTPUT
# =========================================================
class VisitSerializer(serializers.ModelSerializer):
    host = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    is_inside = serializers.SerializerMethodField()

    class Meta:
        model = Visit
        fields = ["id", "visit_code", "visitor_name", "visitor_mobile", "visitor_email", "visitor_company",
                  "visitor_count", "purpose", "purpose_note", "host", "branch", "check_in_at", "check_out_at",
                  "is_inside", "id_proof_type", "id_proof_last4", "photo", "badge_number", "vehicle_number",
                  "notes", "created_by", "created_at", "updated_at"]

    def get_host(self, obj):
        return _emp_ref(obj.host)

    def get_branch(self, obj):
        return _ref(obj.branch)

    def get_created_by(self, obj):
        return _user_ref(obj.created_by)

    def get_is_inside(self, obj):
        return bool(obj.check_in_at and not obj.check_out_at)


class MyVisitSerializer(serializers.ModelSerializer):
    """Host view: who came to meet me (no ID / photo)."""

    class Meta:
        model = Visit
        fields = ["id", "visit_code", "visitor_name", "visitor_mobile", "visitor_company", "visitor_count",
                  "purpose", "purpose_note", "check_in_at", "check_out_at"]
