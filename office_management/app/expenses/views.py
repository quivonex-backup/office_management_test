from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import (
    Expense, ExpenseDocument, RecurringExpense, RecurringExpenseEntry, RecurringExpenseEntryDocument,
)
from .serializers import (
    ExpenseCreateSerializer, ExpenseListSerializer, ExpenseDetailSerializer, ExpenseUpdateSerializer,
    RecurringExpenseCreateSerializer, RecurringExpenseListSerializer, RecurringExpenseDetailSerializer,
    RecurringExpenseUpdateSerializer, RecurringExpenseEntryCreateSerializer,
    RecurringExpenseEntryDetailSerializer, RecurringExpenseEntryUpdateSerializer,
)
from common.services import get_user_organization
from common.s3_utils import upload_to_s3, delete_from_s3
from common.code_generators import generate_expense_code
from app.audit.services import log_activity


# =========================================================
# CREATE EXPENSE
# =========================================================
class ExpenseCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        data = request.data.copy()
        data.pop("organization_id", None)

        serializer = ExpenseCreateSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = serializer.validated_data.get("vendor")
        project = serializer.validated_data.get("project")

        if vendor and vendor.organization_id != organization.id:
            return Response(
                {
                    "status": False,
                    "message": "Selected vendor does not belong to this organization.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if project and project.organization_id != organization.id:
            return Response(
                {
                    "status": False,
                    "message": "Selected project does not belong to this organization.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        expense = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        expense.expense_number = generate_expense_code()
        expense.save(update_fields=["expense_number"])

        files = request.FILES.getlist("documents")
        uploaded_documents = []

        for file in files:
            file_path = upload_to_s3(
                file=file,
                folder="expenses/documents",
            )

            document = ExpenseDocument.objects.create(
                expense=expense,
                title=file.name,
                file=file_path,
                uploaded_by=request.user,
            )

            uploaded_documents.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "file": document.file.name,
                }
            )

        log_activity(
            request=request,
            action="CREATE",
            module="EXPENSE",
            object_type="Expense",
            object_id=expense.id,
            description=f"Expense {expense.expense_number} created.",
            new_data={
                "expense_number": expense.expense_number,
                "title": expense.title,
                "description": expense.description,
                "expense_type": expense.expense_type,
                "amount": expense.amount,
                "expense_date": expense.expense_date,
                "due_date": expense.due_date,
                "vendor": expense.vendor_id,
                "project": expense.project_id,
                "organization_id": organization.id,
                "payment_status": expense.payment_status,
                "payment_date": expense.payment_date,
                "payment_method": expense.payment_method,
                "reference_number": expense.reference_number,
                "notes": expense.notes,
                "documents": uploaded_documents,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Expense created successfully.",
                "data": ExpenseDetailSerializer(
                    expense,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# EXPENSE LIST
# =========================================================
class ExpenseListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        expenses = (
            Expense.objects.filter(
                organization=organization,
                is_active=True,
            )
            .select_related("vendor", "project")
            .prefetch_related("documents")
        )

        search = request.data.get("search")

        if search:
            search = search.strip()
            expenses = expenses.filter(
                Q(expense_number__icontains=search)
                | Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(vendor__vendor_name__icontains=search)
                | Q(project__project_name__icontains=search)
                | Q(reference_number__icontains=search)
            )

        expense_type = request.data.get("expense_type")
        payment_status = request.data.get("payment_status")
        vendor_id = request.data.get("vendor_id")
        project_id = request.data.get("project_id")
        expense_date_from = request.data.get("expense_date_from")
        expense_date_to = request.data.get("expense_date_to")

        if expense_type:
            expenses = expenses.filter(expense_type=expense_type)

        if payment_status:
            expenses = expenses.filter(payment_status=payment_status)

        if vendor_id:
            expenses = expenses.filter(vendor_id=vendor_id)

        if project_id:
            expenses = expenses.filter(project_id=project_id)

        if expense_date_from:
            expenses = expenses.filter(
                expense_date__gte=expense_date_from
            )

        if expense_date_to:
            expenses = expenses.filter(
                expense_date__lte=expense_date_to
            )

        expenses = expenses.order_by(
            "-expense_date",
            "-created_at",
        )

        serializer = ExpenseListSerializer(
            expenses,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Expenses fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# EXPENSE DETAIL
# =========================================================
class ExpenseDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        expense_id = request.data.get("expense_id")
        if not expense_id:
            return Response(
                {"status": False, "message": "expense_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        expense = (
            Expense.objects.filter(
                id=expense_id,
                organization=organization,
                is_active=True,
            )
            .select_related("vendor", "project")
            .prefetch_related("documents")
            .first()
        )
        if not expense:
            return Response(
                {"status": False, "message": "Expense not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        log_activity(
            request=request, action="VIEW", module="EXPENSE", object_type="Expense", object_id=expense.id,
            description=f"Expense {expense.expense_number} details viewed.",
        )

        return Response(
            {
                "status": True,
                "message": "Expense details fetched successfully.",
                "data": ExpenseDetailSerializer(expense, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPDATE EXPENSE
# =========================================================
class ExpenseUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        expense_id = request.data.get("expense_id")
        if not expense_id:
            return Response(
                {"status": False, "message": "expense_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        expense = (
            Expense.objects.filter(
                id=expense_id,
                organization=organization,
                is_active=True,
            )
            .select_related("vendor", "project")
            .first()
        )

        if not expense:
            return Response(
                {"status": False, "message": "Expense not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "title": expense.title,
            "description": expense.description,
            "expense_type": expense.expense_type,
            "amount": expense.amount,
            "expense_date": expense.expense_date,
            "due_date": expense.due_date,
            "vendor": expense.vendor_id,
            "project": expense.project_id,
            "payment_status": expense.payment_status,
            "payment_date": expense.payment_date,
            "payment_method": expense.payment_method,
            "reference_number": expense.reference_number,
            "notes": expense.notes,
        }

        serializer = ExpenseUpdateSerializer(expense, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Validation failed.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        expense = serializer.save(updated_by=request.user)

        remove_document_ids = request.data.getlist("remove_document_ids")
        removed_documents = []
        for document_id in remove_document_ids:
            document = ExpenseDocument.objects.filter(id=document_id, expense=expense).first()
            if not document:
                continue
            removed_documents.append({"id": document.id, "title": document.title, "file": document.file.name if document.file else None})
            if document.file:
                delete_from_s3(document.file)
            document.delete()

        files = request.FILES.getlist("documents")
        added_documents = []
        for file in files:
            file_path = upload_to_s3(file=file, folder="expenses/documents")
            document = ExpenseDocument.objects.create(
                expense=expense, title=file.name, file=file_path, uploaded_by=request.user,
            )
            added_documents.append({"id": document.id, "title": document.title, "file": document.file.name})

        new_data = {
            "title": expense.title,
            "description": expense.description,
            "expense_type": expense.expense_type,
            "amount": expense.amount,
            "expense_date": expense.expense_date,
            "due_date": expense.due_date,
            "vendor": expense.vendor_id,
            "project": expense.project_id,
            "payment_status": expense.payment_status,
            "payment_date": expense.payment_date,
            "payment_method": expense.payment_method,
            "reference_number": expense.reference_number,
            "notes": expense.notes,
        }
        if added_documents:
            new_data["documents_added"] = added_documents
        if removed_documents:
            new_data["documents_removed"] = removed_documents

        log_activity(
            request=request, action="UPDATE", module="EXPENSE", object_type="Expense", object_id=expense.id,
            description=f"Expense {expense.expense_number} updated.",
            old_data=old_data, new_data=new_data,
        )

        return Response(
            {
                "status": True,
                "message": "Expense updated successfully.",
                "data": ExpenseDetailSerializer(expense, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# DEACTIVATE EXPENSE
# =========================================================
class ExpenseDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        expense_id = request.data.get("expense_id")
        if not expense_id:
            return Response(
                {"status": False, "message": "expense_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        expense = Expense.objects.filter(
            id=expense_id,
            organization=organization,
            is_active=True,
        ).first()

        if not expense:
            return Response(
                {"status": False, "message": "Expense not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {"is_active": expense.is_active}
        expense.is_active = False
        expense.updated_by = request.user
        expense.save(update_fields=["is_active", "updated_by", "updated_at"])

        log_activity(
            request=request, action="DELETE", module="EXPENSE", object_type="Expense", object_id=expense.id,
            description=f"Expense {expense.expense_number} deactivated.",
            old_data=old_data, new_data={"is_active": False},
        )

        return Response(
            {"status": True, "message": "Expense deactivated successfully."},
            status=status.HTTP_200_OK,
        )


# =========================================================
# CREATE RECURRING EXPENSE
# =========================================================
class RecurringExpenseCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        data = request.data.copy()
        data.pop("organization_id", None)

        serializer = RecurringExpenseCreateSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        vendor = serializer.validated_data.get("vendor")
        project = serializer.validated_data.get("project")

        if vendor and vendor.organization_id != organization.id:
            return Response(
                {
                    "status": False,
                    "message": "Selected vendor does not belong to this organization.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if project and project.organization_id != organization.id:
            return Response(
                {
                    "status": False,
                    "message": "Selected project does not belong to this organization.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        recurring_expense = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        log_activity(
            request=request,
            action="CREATE",
            module="RECURRING_EXPENSE",
            object_type="RecurringExpense",
            object_id=recurring_expense.id,
            description=(
                f"Recurring expense {recurring_expense.title} created."
            ),
            new_data={
                "title": recurring_expense.title,
                "description": recurring_expense.description,
                "expense_type": recurring_expense.expense_type,
                "vendor": recurring_expense.vendor_id,
                "project": recurring_expense.project_id,
                "organization_id": organization.id,
                "frequency": recurring_expense.frequency,
                "start_date": recurring_expense.start_date,
                "end_date": recurring_expense.end_date,
                "notes": recurring_expense.notes,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Recurring expense created successfully.",
                "data": RecurringExpenseDetailSerializer(
                    recurring_expense,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# RECURRING EXPENSE LIST
# =========================================================
class RecurringExpenseListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        recurring_expenses = (
            RecurringExpense.objects.filter(
                organization=organization,
                is_active=True,
            )
            .select_related("vendor", "project")
            .prefetch_related("entries")
            .order_by("-created_at")
        )

        search = request.data.get("search")

        if search:
            search = search.strip()
            recurring_expenses = recurring_expenses.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(vendor__vendor_name__icontains=search)
                | Q(project__project_name__icontains=search)
            )

        expense_type = request.data.get("expense_type")
        frequency = request.data.get("frequency")
        vendor_id = request.data.get("vendor_id")
        project_id = request.data.get("project_id")

        if expense_type:
            recurring_expenses = recurring_expenses.filter(
                expense_type=expense_type
            )

        if frequency:
            recurring_expenses = recurring_expenses.filter(
                frequency=frequency
            )

        if vendor_id:
            recurring_expenses = recurring_expenses.filter(
                vendor_id=vendor_id
            )

        if project_id:
            recurring_expenses = recurring_expenses.filter(
                project_id=project_id
            )

        serializer = RecurringExpenseListSerializer(
            recurring_expenses,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Recurring expenses fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# RECURRING EXPENSE DETAIL
# =========================================================
class RecurringExpenseDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        recurring_expense_id = request.data.get("recurring_expense_id")
        if not recurring_expense_id:
            return Response(
                {"status": False, "message": "recurring_expense_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        recurring_expense = (
            RecurringExpense.objects.filter(
                id=recurring_expense_id,
                organization=organization,
                is_active=True,
            )
            .select_related("vendor", "project")
            .prefetch_related("entries__documents")
            .first()
        )

        if not recurring_expense:
            return Response(
                {"status": False, "message": "Recurring expense not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        log_activity(
            request=request, action="VIEW", module="RECURRING_EXPENSE", object_type="RecurringExpense",
            object_id=recurring_expense.id,
            description=f"Recurring expense {recurring_expense.title} details viewed.",
        )

        return Response(
            {
                "status": True,
                "message": "Recurring expense details fetched successfully.",
                "data": RecurringExpenseDetailSerializer(recurring_expense, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPDATE RECURRING EXPENSE
# =========================================================
class RecurringExpenseUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        recurring_expense_id = request.data.get("recurring_expense_id")
        if not recurring_expense_id:
            return Response(
                {"status": False, "message": "recurring_expense_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        recurring_expense = (
            RecurringExpense.objects.filter(
                id=recurring_expense_id,
                organization=organization,
                is_active=True,
            )
            .select_related("vendor", "project")
            .first()
        )

        if not recurring_expense:
            return Response(
                {"status": False, "message": "Recurring expense not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "title": recurring_expense.title,
            "description": recurring_expense.description,
            "expense_type": recurring_expense.expense_type,
            "vendor": recurring_expense.vendor_id,
            "project": recurring_expense.project_id,
            "frequency": recurring_expense.frequency,
            "start_date": recurring_expense.start_date,
            "end_date": recurring_expense.end_date,
            "notes": recurring_expense.notes,
        }

        serializer = RecurringExpenseUpdateSerializer(recurring_expense, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Validation failed.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        recurring_expense = serializer.save(updated_by=request.user)

        new_data = {
            "title": recurring_expense.title,
            "description": recurring_expense.description,
            "expense_type": recurring_expense.expense_type,
            "vendor": recurring_expense.vendor_id,
            "project": recurring_expense.project_id,
            "frequency": recurring_expense.frequency,
            "start_date": recurring_expense.start_date,
            "end_date": recurring_expense.end_date,
            "notes": recurring_expense.notes,
        }

        log_activity(
            request=request, action="UPDATE", module="RECURRING_EXPENSE", object_type="RecurringExpense",
            object_id=recurring_expense.id,
            description=f"Recurring expense {recurring_expense.title} updated.",
            old_data=old_data, new_data=new_data,
        )

        return Response(
            {
                "status": True,
                "message": "Recurring expense updated successfully.",
                "data": RecurringExpenseDetailSerializer(recurring_expense, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# DEACTIVATE RECURRING EXPENSE
# =========================================================
class RecurringExpenseDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        recurring_expense_id = request.data.get("recurring_expense_id")
        if not recurring_expense_id:
            return Response(
                {"status": False, "message": "recurring_expense_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        recurring_expense = RecurringExpense.objects.filter(
            id=recurring_expense_id,
            organization=organization,
            is_active=True,
        ).first()

        if not recurring_expense:
            return Response(
                {"status": False, "message": "Recurring expense not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {"is_active": recurring_expense.is_active}
        recurring_expense.is_active = False
        recurring_expense.updated_by = request.user
        recurring_expense.save(update_fields=["is_active", "updated_by", "updated_at"])

        log_activity(
            request=request, action="DELETE", module="RECURRING_EXPENSE", object_type="RecurringExpense",
            object_id=recurring_expense.id,
            description=f"Recurring expense {recurring_expense.title} deactivated.",
            old_data=old_data, new_data={"is_active": False},
        )

        return Response(
            {"status": True, "message": "Recurring expense deactivated successfully."},
            status=status.HTTP_200_OK,
        )


# =========================================================
# CREATE RECURRING EXPENSE ENTRY
# =========================================================
class RecurringExpenseEntryCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        serializer = RecurringExpenseEntryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Validation failed.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recurring_expense = serializer.validated_data["recurring_expense"]

        if recurring_expense.organization_id != organization.id:
            return Response(
                {
                    "status": False,
                    "message": "Recurring expense does not belong to this organization.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not recurring_expense.is_active:
            return Response(
                {
                    "status": False,
                    "message": "Cannot add an entry to an inactive recurring expense.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            entry = serializer.save(created_by=request.user, updated_by=request.user)
        except Exception as error:
            if "unique" in str(error).lower():
                return Response(
                    {"status": False, "message": "An entry already exists for this recurring expense and month."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise

        files = request.FILES.getlist("documents")
        uploaded_documents = []
        for file in files:
            file_path = upload_to_s3(file=file, folder="expenses/recurring_entries/documents")
            document = RecurringExpenseEntryDocument.objects.create(
                recurring_expense_entry=entry, title=file.name, file=file_path, uploaded_by=request.user,
            )
            uploaded_documents.append({"id": document.id, "title": document.title, "file": document.file.name})

        log_activity(
            request=request, action="CREATE", module="RECURRING_EXPENSE_ENTRY", object_type="RecurringExpenseEntry",
            object_id=entry.id,
            description=f"Recurring expense entry for {entry.recurring_expense.title} {entry.month}/{entry.year} created.",
            new_data={
                "recurring_expense": entry.recurring_expense_id,
                "year": entry.year,
                "month": entry.month,
                "amount": entry.amount,
                "due_date": entry.due_date,
                "payment_status": entry.payment_status,
                "payment_date": entry.payment_date,
                "payment_method": entry.payment_method,
                "reference_number": entry.reference_number,
                "notes": entry.notes,
                "documents": uploaded_documents,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Recurring expense entry created successfully.",
                "data": RecurringExpenseEntryDetailSerializer(entry, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# UPDATE RECURRING EXPENSE ENTRY
# =========================================================
class RecurringExpenseEntryUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        entry_id = request.data.get("entry_id")
        if not entry_id:
            return Response(
                {"status": False, "message": "entry_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        entry = (
            RecurringExpenseEntry.objects.filter(
                id=entry_id,
                recurring_expense__organization=organization,
                recurring_expense__is_active=True,
            )
            .select_related("recurring_expense")
            .first()
        )

        if not entry:
            return Response(
                {"status": False, "message": "Recurring expense entry not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "recurring_expense": entry.recurring_expense_id,
            "year": entry.year,
            "month": entry.month,
            "amount": entry.amount,
            "due_date": entry.due_date,
            "payment_status": entry.payment_status,
            "payment_date": entry.payment_date,
            "payment_method": entry.payment_method,
            "reference_number": entry.reference_number,
            "notes": entry.notes,
        }

        serializer = RecurringExpenseEntryUpdateSerializer(entry, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Validation failed.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            entry = serializer.save(updated_by=request.user)
        except Exception as error:
            if "unique" in str(error).lower():
                return Response(
                    {"status": False, "message": "An entry already exists for this recurring expense and month."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise

        remove_document_ids = request.data.getlist("remove_document_ids")
        removed_documents = []
        for document_id in remove_document_ids:
            document = RecurringExpenseEntryDocument.objects.filter(
                id=document_id, recurring_expense_entry=entry
            ).first()
            if not document:
                continue
            removed_documents.append({"id": document.id, "title": document.title, "file": document.file.name if document.file else None})
            if document.file:
                delete_from_s3(document.file)
            document.delete()

        files = request.FILES.getlist("documents")
        added_documents = []
        for file in files:
            file_path = upload_to_s3(file=file, folder="expenses/recurring_entries/documents")
            document = RecurringExpenseEntryDocument.objects.create(
                recurring_expense_entry=entry, title=file.name, file=file_path, uploaded_by=request.user,
            )
            added_documents.append({"id": document.id, "title": document.title, "file": document.file.name})

        new_data = {
            "recurring_expense": entry.recurring_expense_id,
            "year": entry.year,
            "month": entry.month,
            "amount": entry.amount,
            "due_date": entry.due_date,
            "payment_status": entry.payment_status,
            "payment_date": entry.payment_date,
            "payment_method": entry.payment_method,
            "reference_number": entry.reference_number,
            "notes": entry.notes,
        }
        if added_documents:
            new_data["documents_added"] = added_documents
        if removed_documents:
            new_data["documents_removed"] = removed_documents

        log_activity(
            request=request, action="UPDATE", module="RECURRING_EXPENSE_ENTRY", object_type="RecurringExpenseEntry",
            object_id=entry.id,
            description=f"Recurring expense entry {entry.id} updated.",
            old_data=old_data, new_data=new_data,
        )

        return Response(
            {
                "status": True,
                "message": "Recurring expense entry updated successfully.",
                "data": RecurringExpenseEntryDetailSerializer(entry, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# DEACTIVATE / DELETE RECURRING EXPENSE ENTRY
# =========================================================
class RecurringExpenseEntryDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        entry_id = request.data.get("entry_id")
        if not entry_id:
            return Response(
                {"status": False, "message": "entry_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        entry = (
            RecurringExpenseEntry.objects.filter(
                id=entry_id,
                recurring_expense__organization=organization,
                recurring_expense__is_active=True,
            )
            .select_related("recurring_expense")
            .first()
        )

        if not entry:
            return Response(
                {"status": False, "message": "Recurring expense entry not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "recurring_expense": entry.recurring_expense_id,
            "year": entry.year,
            "month": entry.month,
            "amount": entry.amount,
            "payment_status": entry.payment_status,
        }

        documents = RecurringExpenseEntryDocument.objects.filter(recurring_expense_entry=entry)
        deleted_documents = []
        for document in documents:
            deleted_documents.append({"id": document.id, "title": document.title, "file": document.file.name if document.file else None})
            if document.file:
                delete_from_s3(document.file)

        entry.delete()

        log_activity(
            request=request, action="DELETE", module="RECURRING_EXPENSE_ENTRY", object_type="RecurringExpenseEntry",
            object_id=entry_id,
            description=f"Recurring expense entry {entry_id} deleted.",
            old_data={**old_data, "documents": deleted_documents}, new_data=None,
        )

        return Response(
            {"status": True, "message": "Recurring expense entry deleted successfully."},
            status=status.HTTP_200_OK,
        )