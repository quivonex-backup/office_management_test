from django.db import transaction
from django.db.models import Q

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Vendor
from .serializers import (
    VendorCreateSerializer,
    VendorListSerializer,
    VendorDetailSerializer,
    VendorUpdateSerializer,
)

from common.services import get_user_organization
from common.code_generators import generate_vendor_code
from app.audit.services import log_activity


# =========================================================
# CREATE VENDOR
# =========================================================
class VendorCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        data = request.data.copy()
        data.pop("organization_id", None)

        serializer = VendorCreateSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        vendor.vendor_code = generate_vendor_code()
        vendor.save(update_fields=["vendor_code", "updated_at"])

        log_activity(
            request=request,
            action="CREATE",
            module="VENDOR",
            object_type="Vendor",
            object_id=vendor.id,
            description=f"Vendor {vendor.vendor_name} created.",
            new_data={
                "vendor_code": vendor.vendor_code,
                "vendor_name": vendor.vendor_name,
                "company_name": vendor.company_name,
                "organization_id": organization.id,
                "email": vendor.email,
                "phone": vendor.phone,
                "address_line": vendor.address_line,
                "state": vendor.state,
                "district": vendor.district,
                "taluka": vendor.taluka,
                "pincode": vendor.pincode,
                "tax_number": vendor.tax_number,
                "notes": vendor.notes,
                "is_active": vendor.is_active,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Vendor created successfully.",
                "data": VendorDetailSerializer(
                    vendor,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# VENDOR LIST
# =========================================================
class VendorListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        vendors = Vendor.objects.filter(
            organization=organization,
            is_active=True,
        ).order_by("-created_at")

        search = request.data.get("search")

        if search:
            search = search.strip()

            vendors = vendors.filter(
                Q(vendor_code__icontains=search)
                | Q(vendor_name__icontains=search)
                | Q(company_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
                | Q(state__icontains=search)
                | Q(district__icontains=search)
                | Q(taluka__icontains=search)
                | Q(pincode__icontains=search)
                | Q(tax_number__icontains=search)
            )

        state = request.data.get("state")
        district = request.data.get("district")
        taluka = request.data.get("taluka")

        if state:
            vendors = vendors.filter(state__iexact=state.strip())

        if district:
            vendors = vendors.filter(district__iexact=district.strip())

        if taluka:
            vendors = vendors.filter(taluka__iexact=taluka.strip())

        serializer = VendorListSerializer(
            vendors,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Vendors fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# VENDOR DETAIL
# =========================================================
class VendorDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        vendor_id = request.data.get("vendor_id")

        if not vendor_id:
            return Response(
                {
                    "status": False,
                    "message": "vendor_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = Vendor.objects.filter(
            id=vendor_id,
            organization=organization,
            is_active=True,
        ).first()

        if not vendor:
            return Response(
                {
                    "status": False,
                    "message": "Vendor not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VendorDetailSerializer(
            vendor,
            context={"request": request},
        )

        log_activity(
            request=request,
            action="VIEW",
            module="VENDOR",
            object_type="Vendor",
            object_id=vendor.id,
            description=(
                f"Vendor {vendor.vendor_name} "
                f"details viewed."
            ),
        )

        return Response(
            {
                "status": True,
                "message": "Vendor details fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPDATE VENDOR
# =========================================================
class VendorUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        vendor_id = request.data.get("vendor_id")

        if not vendor_id:
            return Response(
                {
                    "status": False,
                    "message": "vendor_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = Vendor.objects.filter(
            id=vendor_id,
            organization=organization,
            is_active=True,
        ).first()

        if not vendor:
            return Response(
                {
                    "status": False,
                    "message": "Vendor not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "vendor_code": vendor.vendor_code,
            "vendor_name": vendor.vendor_name,
            "company_name": vendor.company_name,
            "email": vendor.email,
            "phone": vendor.phone,
            "address_line": vendor.address_line,
            "state": vendor.state,
            "district": vendor.district,
            "taluka": vendor.taluka,
            "pincode": vendor.pincode,
            "tax_number": vendor.tax_number,
            "notes": vendor.notes,
            "is_active": vendor.is_active,
        }

        serializer = VendorUpdateSerializer(
            vendor,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = serializer.save(
            updated_by=request.user
        )

        new_data = {
            "vendor_code": vendor.vendor_code,
            "vendor_name": vendor.vendor_name,
            "company_name": vendor.company_name,
            "email": vendor.email,
            "phone": vendor.phone,
            "address_line": vendor.address_line,
            "state": vendor.state,
            "district": vendor.district,
            "taluka": vendor.taluka,
            "pincode": vendor.pincode,
            "tax_number": vendor.tax_number,
            "notes": vendor.notes,
            "is_active": vendor.is_active,
        }

        log_activity(
            request=request,
            action="UPDATE",
            module="VENDOR",
            object_type="Vendor",
            object_id=vendor.id,
            description=(
                f"Vendor {vendor.vendor_name} "
                f"updated."
            ),
            old_data=old_data,
            new_data=new_data,
        )

        return Response(
            {
                "status": True,
                "message": "Vendor updated successfully.",
                "data": VendorDetailSerializer(
                    vendor,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# DEACTIVATE VENDOR / SOFT DELETE
# =========================================================
class VendorDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        vendor_id = request.data.get("vendor_id")

        if not vendor_id:
            return Response(
                {
                    "status": False,
                    "message": "vendor_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = Vendor.objects.filter(
            id=vendor_id,
            organization=organization,
            is_active=True,
        ).first()

        if not vendor:
            return Response(
                {
                    "status": False,
                    "message": "Vendor not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "is_active": vendor.is_active,
        }

        vendor.is_active = False
        vendor.updated_by = request.user

        vendor.save(
            update_fields=[
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )

        log_activity(
            request=request,
            action="DELETE",
            module="VENDOR",
            object_type="Vendor",
            object_id=vendor.id,
            description=(
                f"Vendor {vendor.vendor_name} "
                f"deactivated."
            ),
            old_data=old_data,
            new_data={
                "is_active": False,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Vendor deactivated successfully.",
            },
            status=status.HTTP_200_OK,
        )