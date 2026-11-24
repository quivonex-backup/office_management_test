"""
Assets API (all POST, envelope {status, message, data, errors?}).

  category/create|update|deactivate/   asset.manage
  category/list/                       asset.manage, asset.view (any)
  asset/create|update|deactivate/      asset.manage
  asset/assign/ | asset/return/        asset.manage
  asset/list/ | asset/detail/          asset.manage, asset.view (any)
  asset/my-assets/                     any employee (what I hold)

Exit is not blocked by assets: employees/deactivate/ only reports
"assets_held" so HR knows what to collect.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response

from app.audit.services import log_activity
from common.code_generators import generate_asset_code
from common.permissions import OrgAPIView, RequiredPermsMixin, get_user_employee
from common.services import get_user_organization

from .models import Asset, AssetAssignment, AssetCategory
from .serializers import (
    AssetAssignmentSerializer,
    AssetAssignSerializer,
    AssetCategorySerializer,
    AssetCategoryWriteSerializer,
    AssetDetailSerializer,
    AssetListSerializer,
    AssetReturnSerializer,
    AssetWriteSerializer,
    MyAssetSerializer,
)

ASSET_RELATED = ("category", "branch", "current_holder")
VIEW_CODES = ("asset.manage", "asset.view")


# =========================================================
# SHARED
# =========================================================
class AssetBaseAPIView(RequiredPermsMixin, OrgAPIView):

    def get_org(self, request):
        return get_user_organization(request)

    def find_category(self, organization, category_id, active_only=True):
        qs = AssetCategory.objects.filter(organization=organization, pk=category_id)
        if active_only:
            qs = qs.filter(is_active=True)
        return qs.first()

    def get_asset(self, request, organization):
        asset_id = request.data.get("asset_id")
        if not asset_id:
            return None, self.fail("asset_id is required.")
        asset = (
            Asset.objects.filter(pk=asset_id, organization=organization, is_active=True)
            .select_related(*ASSET_RELATED).first()
        )
        if asset is None:
            return None, self.fail("Asset not found.", http_status=status.HTTP_404_NOT_FOUND)
        return asset, None

    def find_branch(self, organization, branch_id):
        from app.accounts.models import Branch

        if branch_id in (None, "", "null"):
            return None, None
        branch = Branch.objects.filter(pk=branch_id, organization=organization, is_active=True).first()
        if branch is None:
            return None, self.fail("Validation failed.", {"branch_id": ["Active branch not found."]})
        return branch, None

    def serial_taken(self, organization, serial, exclude_id=None):
        if not serial:
            return False
        qs = Asset.objects.filter(organization=organization, is_active=True, serial_number__iexact=serial)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        return qs.exists()

    def detail_data(self, asset):
        asset = Asset.objects.select_related(*ASSET_RELATED).get(pk=asset.pk)
        history = asset.assignments.select_related("employee", "assigned_by", "returned_by", "asset")
        return {
            "asset": AssetDetailSerializer(asset).data,
            "assignments": AssetAssignmentSerializer(history, many=True).data,
        }


# =========================================================
# CATEGORY — CREATE
# =========================================================
class AssetCategoryCreateAPIView(AssetBaseAPIView):
    required_perms = ("asset.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        s = AssetCategoryWriteSerializer(data=request.data)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        name = s.validated_data["name"].strip()
        if AssetCategory.objects.filter(organization=organization, name__iexact=name).exists():
            return self.fail("Validation failed.", {"name": ["A category with this name already exists."]})
        category = AssetCategory.objects.create(
            organization=organization, name=name,
            description=s.validated_data.get("description") or None,
            created_by=request.user, updated_by=request.user,
        )
        log_activity(
            request=request, action="CREATE", module="ASSET", object_type="AssetCategory",
            object_id=category.id, description=f"Asset category {category.name} created.",
            new_data={"name": category.name},
        )
        return self.ok("Category created.", AssetCategorySerializer(category).data, status.HTTP_201_CREATED)


# =========================================================
# CATEGORY — LIST
# =========================================================
class AssetCategoryListAPIView(AssetBaseAPIView):
    required_perms = VIEW_CODES

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        qs = AssetCategory.objects.filter(organization=organization)
        if self.parse_bool(request.data.get("include_inactive")) is not True:
            qs = qs.filter(is_active=True)
        qs = qs.annotate(asset_total=Count("assets", filter=Q(assets__is_active=True))).order_by("name")
        return self.ok("Categories fetched.", AssetCategorySerializer(qs, many=True).data)


# =========================================================
# CATEGORY — UPDATE
# =========================================================
class AssetCategoryUpdateAPIView(AssetBaseAPIView):
    required_perms = ("asset.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        category = self.find_category(organization, request.data.get("category_id"), active_only=False)
        if category is None:
            return self.fail("Category not found.", http_status=status.HTTP_404_NOT_FOUND)
        s = AssetCategoryWriteSerializer(data=request.data, partial=True)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data
        old = {"name": category.name, "description": category.description, "is_active": category.is_active}
        if "name" in data:
            name = data["name"].strip()
            if AssetCategory.objects.filter(organization=organization, name__iexact=name).exclude(pk=category.pk).exists():
                return self.fail("Validation failed.", {"name": ["A category with this name already exists."]})
            category.name = name
        if "description" in data:
            category.description = data.get("description") or None
        if self.parse_bool(request.data.get("is_active")) is True:
            category.is_active = True
        category.updated_by = request.user
        category.save()
        log_activity(
            request=request, action="UPDATE", module="ASSET", object_type="AssetCategory",
            object_id=category.id, description=f"Asset category {category.name} updated.",
            old_data=old, new_data={"name": category.name, "description": category.description,
                                    "is_active": category.is_active},
        )
        return self.ok("Category updated.", AssetCategorySerializer(category).data)


# =========================================================
# CATEGORY — DEACTIVATE
# =========================================================
class AssetCategoryDeactivateAPIView(AssetBaseAPIView):
    required_perms = ("asset.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        category = self.find_category(organization, request.data.get("category_id"))
        if category is None:
            return self.fail("Category not found.", http_status=status.HTTP_404_NOT_FOUND)
        category.is_active = False
        category.updated_by = request.user
        category.save(update_fields=["is_active", "updated_by", "updated_at"])
        log_activity(
            request=request, action="DELETE", module="ASSET", object_type="AssetCategory",
            object_id=category.id, description=f"Asset category {category.name} deactivated.",
        )
        return self.ok("Category deactivated. Existing assets keep it; new assets cannot use it.")


# =========================================================
# ASSET — CREATE
# =========================================================
class AssetCreateAPIView(AssetBaseAPIView):
    required_perms = ("asset.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        s = AssetWriteSerializer(data=request.data)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data

        category = self.find_category(organization, data["category_id"])
        if category is None:
            return self.fail("Validation failed.", {"category_id": ["Active category not found."]})
        branch, err = self.find_branch(organization, data.get("branch_id"))
        if err:
            return err
        serial = (data.get("serial_number") or "").strip() or None
        if self.serial_taken(organization, serial):
            return self.fail("Validation failed.", {"serial_number": ["An asset with this serial number already exists."]})

        asset = Asset.objects.create(
            organization=organization,
            asset_code=generate_asset_code(),
            category=category,
            name=data["name"].strip(),
            brand=data.get("brand") or None,
            model_number=data.get("model_number") or None,
            serial_number=serial,
            branch=branch,
            purchase_date=data.get("purchase_date"),
            purchase_cost=data.get("purchase_cost"),
            warranty_until=data.get("warranty_until"),
            notes=data.get("notes") or None,
            status=data.get("status") or "AVAILABLE",
            created_by=request.user,
            updated_by=request.user,
        )
        log_activity(
            request=request, action="CREATE", module="ASSET", object_type="Asset",
            object_id=asset.id, description=f"Asset {asset.asset_code} created.",
            new_data={"name": asset.name, "category_id": category.id, "serial_number": asset.serial_number},
        )
        return self.ok("Asset created.", self.detail_data(asset), status.HTTP_201_CREATED)


# =========================================================
# ASSET — LIST
# =========================================================
class AssetListAPIView(AssetBaseAPIView):
    required_perms = VIEW_CODES

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        data = request.data
        qs = Asset.objects.filter(organization=organization, is_active=True).select_related(*ASSET_RELATED)

        search = (data.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(asset_code__icontains=search) | Q(name__icontains=search)
                | Q(serial_number__icontains=search) | Q(brand__icontains=search)
                | Q(model_number__icontains=search)
                | Q(current_holder__first_name__icontains=search)
                | Q(current_holder__last_name__icontains=search)
                | Q(current_holder__employee_code__icontains=search)
            )
        summary_qs = qs

        if data.get("status"):
            qs = qs.filter(status=str(data.get("status")).upper())
        if data.get("category_id"):
            qs = qs.filter(category_id=data.get("category_id"))
        if data.get("branch_id"):
            qs = qs.filter(branch_id=data.get("branch_id"))
        if data.get("holder_id"):
            qs = qs.filter(current_holder_id=data.get("holder_id"))
        if data.get("warranty_due_days") not in (None, ""):
            try:
                days = int(data.get("warranty_due_days"))
            except (TypeError, ValueError):
                return self.fail("Validation failed.", {"warranty_due_days": ["Must be a number."]})
            today = timezone.localdate()
            qs = qs.filter(warranty_until__gte=today,
                           warranty_until__lte=today + timedelta(days=days))

        by_status = {code: 0 for code, _label in Asset.STATUS_CHOICES}
        for row in summary_qs.values("status").annotate(n=Count("id")):
            by_status[row["status"]] = row["n"]
        return Response(
            {
                "status": True,
                "message": "Assets fetched.",
                "data": AssetListSerializer(qs.order_by("-created_at"), many=True).data,
                "summary": {"total": sum(by_status.values()), "by_status": by_status},
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# ASSET — DETAIL
# =========================================================
class AssetDetailAPIView(AssetBaseAPIView):
    required_perms = VIEW_CODES

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        asset, err = self.get_asset(request, organization)
        if err:
            return err
        return self.ok("Asset fetched.", self.detail_data(asset))


# =========================================================
# ASSET — UPDATE
# =========================================================
class AssetUpdateAPIView(AssetBaseAPIView):
    required_perms = ("asset.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        asset, err = self.get_asset(request, organization)
        if err:
            return err
        s = AssetWriteSerializer(data=request.data, partial=True)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data
        old = AssetDetailSerializer(asset).data

        if "category_id" in data:
            category = self.find_category(organization, data["category_id"])
            if category is None:
                return self.fail("Validation failed.", {"category_id": ["Active category not found."]})
            asset.category = category
        if "branch_id" in data:
            asset.branch, err = self.find_branch(organization, data.get("branch_id"))
            if err:
                return err
        if "serial_number" in data:
            serial = (data.get("serial_number") or "").strip() or None
            if self.serial_taken(organization, serial, exclude_id=asset.pk):
                return self.fail("Validation failed.",
                                 {"serial_number": ["An asset with this serial number already exists."]})
            asset.serial_number = serial
        if "status" in data and data["status"] != asset.status:
            if asset.status == "ASSIGNED":
                return self.fail("Return the asset before changing its status.")
            asset.status = data["status"]
        if "name" in data:
            asset.name = data["name"].strip()
        for field in ("brand", "model_number", "notes"):
            if field in data:
                setattr(asset, field, (data.get(field) or "").strip() or None)
        for field in ("purchase_date", "purchase_cost", "warranty_until"):
            if field in data:
                setattr(asset, field, data.get(field))
        if asset.purchase_date and asset.warranty_until and asset.warranty_until < asset.purchase_date:
            return self.fail("Validation failed.", {"warranty_until": ["Cannot be before purchase_date."]})

        asset.updated_by = request.user
        asset.save()
        log_activity(
            request=request, action="UPDATE", module="ASSET", object_type="Asset",
            object_id=asset.id, description=f"Asset {asset.asset_code} updated.",
            old_data=old, new_data=AssetDetailSerializer(asset).data,
        )
        return self.ok("Asset updated.", self.detail_data(asset))


# =========================================================
# ASSET — ASSIGN (issue to an employee)
# =========================================================
class AssetAssignAPIView(AssetBaseAPIView):
    required_perms = ("asset.manage",)

    @transaction.atomic
    def post(self, request):
        from app.employees.models import Employee

        organization, err = self.get_org(request)
        if err:
            return err
        s = AssetAssignSerializer(data=request.data)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data

        asset = Asset.objects.select_for_update().filter(
            pk=data["asset_id"], organization=organization, is_active=True).first()
        if asset is None:
            return self.fail("Asset not found.", http_status=status.HTTP_404_NOT_FOUND)
        if asset.status != "AVAILABLE":
            return self.fail(f"Only available assets can be assigned. This asset is {asset.get_status_display()}.")
        employee = Employee.objects.filter(pk=data["employee_id"], organization=organization, is_active=True).first()
        if employee is None:
            return self.fail("Validation failed.", {"employee_id": ["Active employee not found."]})

        assigned_on = data.get("assigned_on") or timezone.localdate()
        AssetAssignment.objects.create(
            asset=asset, employee=employee, assigned_on=assigned_on,
            condition_on_issue=data.get("condition"), issue_note=data.get("note") or None,
            assigned_by=request.user,
        )
        asset.status = "ASSIGNED"
        asset.current_holder = employee
        asset.updated_by = request.user
        asset.save(update_fields=["status", "current_holder", "updated_by", "updated_at"])

        if employee.user_id:
            from app.communications.notification_service import notify

            user = employee.user
            transaction.on_commit(lambda: notify(
                users=user, event_code="ASSET_ASSIGNED",
                title=f"Asset issued: {asset.name}",
                body=f"{asset.asset_code} has been issued to you.",
                reference_type="asset", reference_id=asset.id,
            ))
        log_activity(
            request=request, action="UPDATE", module="ASSET", object_type="Asset",
            object_id=asset.id, description=f"Asset {asset.asset_code} assigned to {employee.employee_code}.",
            new_data={"employee_id": employee.id, "assigned_on": str(assigned_on)},
        )
        return self.ok("Asset assigned.", self.detail_data(asset))


# =========================================================
# ASSET — RETURN
# =========================================================
class AssetReturnAPIView(AssetBaseAPIView):
    required_perms = ("asset.manage",)

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        s = AssetReturnSerializer(data=request.data)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data

        asset = Asset.objects.select_for_update().filter(
            pk=data["asset_id"], organization=organization, is_active=True).first()
        if asset is None:
            return self.fail("Asset not found.", http_status=status.HTTP_404_NOT_FOUND)
        if asset.status != "ASSIGNED":
            return self.fail("This asset is not assigned to anyone.")

        returned_on = data.get("returned_on") or timezone.localdate()
        row = asset.assignments.filter(returned_on__isnull=True).order_by("-assigned_on", "-id").first()
        if row is not None:
            if returned_on < row.assigned_on:
                return self.fail("Validation failed.", {"returned_on": ["Cannot be before the issue date."]})
            row.returned_on = returned_on
            row.condition_on_return = data.get("condition")
            row.return_note = data.get("note") or None
            row.returned_by = request.user
            row.save(update_fields=["returned_on", "condition_on_return", "return_note", "returned_by"])

        holder_id = asset.current_holder_id
        asset.status = data.get("status_after") or "AVAILABLE"
        asset.current_holder = None
        asset.updated_by = request.user
        asset.save(update_fields=["status", "current_holder", "updated_by", "updated_at"])
        log_activity(
            request=request, action="UPDATE", module="ASSET", object_type="Asset",
            object_id=asset.id, description=f"Asset {asset.asset_code} returned.",
            old_data={"employee_id": holder_id},
            new_data={"returned_on": str(returned_on), "status": asset.status},
        )
        return self.ok("Asset returned.", self.detail_data(asset))


# =========================================================
# ASSET — DEACTIVATE (remove a wrong entry)
# =========================================================
class AssetDeactivateAPIView(AssetBaseAPIView):
    required_perms = ("asset.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        asset, err = self.get_asset(request, organization)
        if err:
            return err
        if asset.status == "ASSIGNED":
            return self.fail("Return the asset before removing it.")
        asset.is_active = False
        asset.updated_by = request.user
        asset.save(update_fields=["is_active", "updated_by", "updated_at"])
        log_activity(
            request=request, action="DELETE", module="ASSET", object_type="Asset",
            object_id=asset.id, description=f"Asset {asset.asset_code} deactivated.",
        )
        return self.ok("Asset removed.")


# =========================================================
# ASSET — MY ASSETS (employee)
# =========================================================
class MyAssetListAPIView(AssetBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        employee = get_user_employee(request.user, organization)
        if employee is None:
            return self.fail("No active employee profile is linked to this user.",
                             http_status=status.HTTP_404_NOT_FOUND)
        qs = (
            Asset.objects.filter(organization=organization, is_active=True, current_holder=employee,
                                 status="ASSIGNED")
            .select_related("category").prefetch_related("assignments").order_by("name")
        )
        return self.ok("Your assets fetched.", MyAssetSerializer(qs, many=True).data)
