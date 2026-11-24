from rest_framework import serializers

from .models import Asset, AssetAssignment, AssetCategory


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
class AssetCategoryWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AssetWriteSerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    name = serializers.CharField(max_length=150)
    brand = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    model_number = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    serial_number = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    purchase_date = serializers.DateField(required=False, allow_null=True)
    purchase_cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=0)
    warranty_until = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # Only these can be set by hand; ASSIGNED comes from asset/assign/.
    status = serializers.ChoiceField(
        choices=[("AVAILABLE", "Available"), ("IN_REPAIR", "In repair"), ("RETIRED", "Retired"), ("LOST", "Lost")],
        required=False,
    )

    def validate(self, attrs):
        start, end = attrs.get("purchase_date"), attrs.get("warranty_until")
        if start and end and end < start:
            raise serializers.ValidationError({"warranty_until": "Cannot be before purchase_date."})
        return attrs


class AssetAssignSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    employee_id = serializers.IntegerField()
    assigned_on = serializers.DateField(required=False)
    condition = serializers.ChoiceField(choices=AssetAssignment.CONDITION_CHOICES, required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AssetReturnSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    returned_on = serializers.DateField(required=False)
    condition = serializers.ChoiceField(choices=AssetAssignment.CONDITION_CHOICES, required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # What the asset becomes after the return (default AVAILABLE).
    status_after = serializers.ChoiceField(
        choices=[("AVAILABLE", "Available"), ("IN_REPAIR", "In repair"), ("RETIRED", "Retired"), ("LOST", "Lost")],
        required=False, default="AVAILABLE",
    )


# =========================================================
# OUTPUT
# =========================================================
class AssetCategorySerializer(serializers.ModelSerializer):
    asset_count = serializers.SerializerMethodField()

    class Meta:
        model = AssetCategory
        fields = ["id", "name", "description", "asset_count", "is_active", "created_at", "updated_at"]

    def get_asset_count(self, obj):
        value = getattr(obj, "asset_total", None)
        if value is None:
            value = obj.assets.filter(is_active=True).count()
        return value


class AssetListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    current_holder = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ["id", "asset_code", "name", "category", "brand", "model_number", "serial_number",
                  "branch", "status", "current_holder", "warranty_until", "created_at"]

    def get_category(self, obj):
        return _ref(obj.category)

    def get_branch(self, obj):
        return _ref(obj.branch)

    def get_current_holder(self, obj):
        return _emp_ref(obj.current_holder)


class AssetDetailSerializer(AssetListSerializer):
    class Meta(AssetListSerializer.Meta):
        fields = AssetListSerializer.Meta.fields + ["purchase_date", "purchase_cost", "notes", "updated_at"]


class AssetAssignmentSerializer(serializers.ModelSerializer):
    employee = serializers.SerializerMethodField()
    asset = serializers.SerializerMethodField()
    assigned_by = serializers.SerializerMethodField()
    returned_by = serializers.SerializerMethodField()

    class Meta:
        model = AssetAssignment
        fields = ["id", "asset", "employee", "assigned_on", "condition_on_issue", "issue_note",
                  "returned_on", "condition_on_return", "return_note", "assigned_by", "returned_by",
                  "created_at"]

    def get_employee(self, obj):
        return _emp_ref(obj.employee)

    def get_asset(self, obj):
        return {"id": obj.asset_id, "asset_code": obj.asset.asset_code, "name": obj.asset.name}

    def get_assigned_by(self, obj):
        return _user_ref(obj.assigned_by)

    def get_returned_by(self, obj):
        return _user_ref(obj.returned_by)


class MyAssetSerializer(serializers.ModelSerializer):
    """Employee view: what I hold, no cost."""

    category = serializers.SerializerMethodField()
    assigned_on = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ["id", "asset_code", "name", "category", "brand", "model_number", "serial_number",
                  "warranty_until", "assigned_on"]

    def get_category(self, obj):
        return _ref(obj.category)

    def get_assigned_on(self, obj):
        row = next((a for a in obj.assignments.all() if a.returned_on is None), None)
        return row.assigned_on if row else None
