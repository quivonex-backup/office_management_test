from rest_framework import serializers
from .models import Vendor


# =========================================================
# VENDOR CREATE SERIALIZER
# =========================================================
class VendorCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "vendor_name",
            "company_name",
            "email",
            "phone",
            "address_line",
            "state",
            "district",
            "taluka",
            "pincode",
            "tax_number",
            "notes",
        ]

    def validate_pincode(self, value):
        if value:
            value = value.strip()

            if not value.isdigit():
                raise serializers.ValidationError(
                    "Pincode must contain only digits."
                )

            if len(value) != 6:
                raise serializers.ValidationError(
                    "Pincode must be 6 digits."
                )

        return value


# =========================================================
# VENDOR LIST SERIALIZER
# =========================================================
class VendorListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_code",
            "vendor_name",
            "company_name",
            "email",
            "phone",
            "state",
            "district",
            "taluka",
            "pincode",
            "tax_number",
            "is_active",
            "created_at",
        ]


# =========================================================
# VENDOR DETAIL SERIALIZER
# =========================================================
class VendorDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_code",
            "vendor_name",
            "company_name",
            "email",
            "phone",
            "address_line",
            "state",
            "district",
            "taluka",
            "pincode",
            "tax_number",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]


# =========================================================
# VENDOR UPDATE SERIALIZER
# =========================================================
class VendorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "vendor_name",
            "company_name",
            "email",
            "phone",
            "address_line",
            "state",
            "district",
            "taluka",
            "pincode",
            "tax_number",
            "notes",
        ]
        extra_kwargs = {
            "vendor_name": {"required": False},
        }

    def validate_pincode(self, value):
        if value:
            value = value.strip()

            if not value.isdigit():
                raise serializers.ValidationError(
                    "Pincode must contain only digits."
                )

            if len(value) != 6:
                raise serializers.ValidationError(
                    "Pincode must be 6 digits."
                )

        return value