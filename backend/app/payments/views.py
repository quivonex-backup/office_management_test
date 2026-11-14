from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    ProjectPayment,
    ProjectPaymentTransaction,
    ProjectPaymentDocument,
)
from app.clients.models import Client
from app.projects.models import Project
from .serializers import (
    ProjectPaymentCreateSerializer,
    ProjectPaymentListSerializer,
    ProjectPaymentDetailSerializer,
    ProjectPaymentUpdateSerializer,
    ProjectPaymentTransactionCreateSerializer,
    ProjectPaymentTransactionUpdateSerializer,
    ProjectPaymentReminderSerializer,
)
from common.services import get_user_organization
from .utils import recalculate_project_payment
from app.projects.models import Project
from common.s3_utils import upload_to_s3, delete_from_s3
from app.audit.services import log_activity

from .services import send_project_payment_reminder_emails, generate_project_invoice_pdf




# =========================================================
# CREATE PROJECT PAYMENT
# =========================================================

class ProjectPaymentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        project_id = request.data.get("project")

        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = (
            Project.objects
            .select_for_update()
            .filter(
                id=project_id,
                organization=organization,
                is_active=True,
            )
            .first()
        )

        if not project:
            return Response(
                {
                    "status": False,
                    "message": "Project not found in the selected organization.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Do not allow the client to choose or override the organization.
        serializer_data = request.data.copy()
        serializer_data.pop("organization_id", None)
        serializer_data.pop("organization", None)

        serializer = ProjectPaymentCreateSerializer(
            data=serializer_data
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

        serializer.validated_data["project"] = project

        if serializer.validated_data["payment_type"] == "INSTALLMENT":
            installment_number = serializer.validated_data.get(
                "installment_number"
            )

            if installment_number is None:
                last_installment = (
                    ProjectPayment.objects
                    .filter(
                        project=project,
                        payment_type="INSTALLMENT",
                        is_active=True,
                    )
                    .exclude(status="CANCELLED")
                    .order_by("-installment_number")
                    .first()
                )

                serializer.validated_data["installment_number"] = (
                    last_installment.installment_number + 1
                    if last_installment
                    else 1
                )

        payment = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        uploaded_documents = []

        files = request.FILES.getlist("documents")

        for file in files:
            file_path = upload_to_s3(
                file=file,
                folder="projects/payments/documents",
            )

            document = ProjectPaymentDocument.objects.create(
                payment=payment,
                title=file.name,
                file=file_path,
                uploaded_by=request.user,
            )

            uploaded_documents.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "file": document.file.name if document.file else None,
                }
            )

        log_activity(
            request=request,
            action="CREATE",
            module="PROJECT_PAYMENT",
            object_type="ProjectPayment",
            object_id=payment.id,
            description=(
                f"Payment created for project {project.project_name}."
            ),
            new_data={
                "organization_id": organization.id,
                "project_id": project.id,
                "project_name": project.project_name,
                "payment_type": payment.payment_type,
                "installment_number": payment.installment_number,
                "title": payment.title,
                "amount": str(payment.amount),
                "paid_amount": str(payment.paid_amount),
                "outstanding_amount": str(payment.outstanding_amount),
                "due_date": (
                    str(payment.due_date) if payment.due_date else None
                ),
                "paid_date": (
                    str(payment.paid_date) if payment.paid_date else None
                ),
                "status": payment.status,
                "notes": payment.notes,
                "documents": uploaded_documents,
            },
        )

        payment = (
            ProjectPayment.objects
            .select_related("project", "organization")
            .prefetch_related("transactions", "documents")
            .get(id=payment.id)
        )

        response_data = ProjectPaymentDetailSerializer(
            payment,
            context={"request": request},
        ).data

        return Response(
            {
                "status": True,
                "message": "Project payment created successfully.",
                "data": response_data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# LIST PROJECT PAYMENTS
# =========================================================

class ProjectPaymentListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        payments = (
            ProjectPayment.objects
            .filter(
                project__organization=organization,
                project__is_active=True,
                is_active=True,
            )
            .select_related("project", "organization")
            .prefetch_related("transactions", "documents")
        )

        project_id = request.data.get("project_id")
        if project_id:
            payments = payments.filter(project_id=project_id)

        payment_type = request.data.get("payment_type")
        if payment_type:
            payments = payments.filter(payment_type=payment_type)

        payment_status = request.data.get("status")
        if payment_status:
            payments = payments.filter(status=payment_status)

        installment_number = request.data.get("installment_number")
        if installment_number:
            payments = payments.filter(
                installment_number=installment_number
            )

        search = request.data.get("search")
        if search:
            search = search.strip()

            if search:
                payments = payments.filter(
                    Q(project__project_name__icontains=search)
                    | Q(title__icontains=search)
                    | Q(
                        transactions__reference_number__icontains=search
                    )
                    | Q(transactions__utr_number__icontains=search)
                    | Q(transactions__cheque_number__icontains=search)
                    | Q(
                        transactions__gateway_transaction_id__icontains=search
                    )
                ).distinct()

        payments = payments.order_by(
            "project_id",
            "payment_type",
            "installment_number",
            "-created_at",
        )

        serializer = ProjectPaymentListSerializer(
            payments,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Project payments fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# PROJECT PAYMENT DETAIL
# =========================================================
class ProjectPaymentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        payment_id = request.data.get("payment_id")
        if not payment_id:
            return Response(
                {
                    "status": False,
                    "message": "payment_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = (
            ProjectPayment.objects
            .filter(
                id=payment_id,
                project__organization=organization,
                project__is_active=True,
                is_active=True,
            )
            .select_related("project")
            .prefetch_related("transactions", "documents")
            .first()
        )

        if not payment:
            return Response(
                {
                    "status": False,
                    "message": "Project payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectPaymentDetailSerializer(payment, context={"request": request})
        return Response(
            {
                "status": True,
                "message": "Project payment details fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPDATE PROJECT PAYMENT
# =========================================================
class ProjectPaymentUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        payment_id = request.data.get("payment_id")
        if not payment_id:
            return Response(
                {
                    "status": False,
                    "message": "payment_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = (
            ProjectPayment.objects
            .select_for_update()
            .filter(
                id=payment_id,
                project__organization=organization,
                project__is_active=True,
                is_active=True,
            )
            .select_related("project")
            .prefetch_related("transactions", "documents")
            .first()
        )

        if not payment:
            return Response(
                {
                    "status": False,
                    "message": "Project payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "project_id": payment.project.id,
            "project_name": payment.project.project_name,
            "payment_type": payment.payment_type,
            "installment_number": payment.installment_number,
            "title": payment.title,
            "amount": str(payment.amount),
            "paid_amount": str(payment.paid_amount),
            "outstanding_amount": str(payment.outstanding_amount),
            "due_date": str(payment.due_date) if payment.due_date else None,
            "paid_date": str(payment.paid_date) if payment.paid_date else None,
            "status": payment.status,
            "notes": payment.notes,
            "documents": [
                {"id": doc.id, "title": doc.title, "file": doc.file.name if doc.file else None}
                for doc in payment.documents.all()
            ],
        }

        delete_document_ids = request.data.getlist("delete_document_ids")

        serializer = ProjectPaymentUpdateSerializer(payment, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated_delete_ids = serializer.validated_data.get("delete_document_ids", [])
        payment = serializer.save(updated_by=request.user)

        deleted_documents = []
        if validated_delete_ids:
            documents = ProjectPaymentDocument.objects.filter(payment=payment, id__in=validated_delete_ids)
            for document in documents:
                doc_data = {
                    "id": document.id,
                    "title": document.title,
                    "file": document.file.name if document.file else None,
                }
                if document.file:
                    delete_from_s3(document.file)
                document.delete()
                deleted_documents.append(doc_data)

        uploaded_documents = []
        files = request.FILES.getlist("documents")
        for file in files:
            file_path = upload_to_s3(file=file, folder="projects/payments/documents")
            document = ProjectPaymentDocument.objects.create(
                payment=payment,
                title=file.name,
                file=file_path,
                uploaded_by=request.user,
            )
            uploaded_documents.append({
                "id": document.id,
                "title": document.title,
                "file": document.file.name if document.file else None,
            })

        payment = recalculate_project_payment(payment)
        payment.updated_by = request.user
        payment.save(update_fields=["updated_by", "updated_at"])
        payment.refresh_from_db()

        new_data = {
            "project_id": payment.project.id,
            "project_name": payment.project.project_name,
            "payment_type": payment.payment_type,
            "installment_number": payment.installment_number,
            "title": payment.title,
            "amount": str(payment.amount),
            "paid_amount": str(payment.paid_amount),
            "outstanding_amount": str(payment.outstanding_amount),
            "due_date": str(payment.due_date) if payment.due_date else None,
            "paid_date": str(payment.paid_date) if payment.paid_date else None,
            "status": payment.status,
            "notes": payment.notes,
        }
        if uploaded_documents:
            new_data["documents_added"] = uploaded_documents
        if deleted_documents:
            new_data["documents_removed"] = deleted_documents

        log_activity(
            request=request,
            action="UPDATE",
            module="PROJECT_PAYMENT",
            object_type="ProjectPayment",
            object_id=payment.id,
            description=f"Payment for project {payment.project.project_name} updated.",
            old_data=old_data,
            new_data=new_data,
        )

        payment = (
            ProjectPayment.objects
            .select_related("project")
            .prefetch_related("transactions", "documents")
            .get(id=payment.id)
        )
        response_data = ProjectPaymentDetailSerializer(payment, context={"request": request}).data

        return Response(
            {
                "status": True,
                "message": "Project payment updated successfully.",
                "data": response_data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# CREATE PAYMENT TRANSACTION
# =========================================================
class ProjectPaymentTransactionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        payment_id = request.data.get("payment_id")
        if not payment_id:
            return Response(
                {
                    "status": False,
                    "message": "payment_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = (
            ProjectPayment.objects
            .select_for_update()
            .filter(
                id=payment_id,
                project__organization=organization,
                project__is_active=True,
                is_active=True,
            )
            .select_related("project")
            .first()
        )

        if not payment:
            return Response(
                {
                    "status": False,
                    "message": "Project payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectPaymentTransactionCreateSerializer(data=request.data, context={"payment": payment})
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_transaction = serializer.save(payment=payment, received_by=request.user)

        payment = recalculate_project_payment(payment)
        payment.updated_by = request.user
        payment.save(update_fields=["updated_by", "updated_at"])

        log_activity(
            request=request,
            action="CREATE",
            module="PROJECT_PAYMENT_TRANSACTION",
            object_type="ProjectPaymentTransaction",
            object_id=payment_transaction.id,
            description=f"Payment transaction added for project {payment.project.project_name}.",
            new_data={
                "payment_id": payment.id,
                "transaction_id": payment_transaction.id,
                "amount": str(payment_transaction.amount),
                "payment_method": payment_transaction.payment_method,
                "transaction_date": str(payment_transaction.transaction_date),
                "reference_number": payment_transaction.reference_number,
                "utr_number": payment_transaction.utr_number,
                "bank_name": payment_transaction.bank_name,
                "cheque_number": payment_transaction.cheque_number,
                "cheque_date": str(payment_transaction.cheque_date) if payment_transaction.cheque_date else None,
                "gateway_transaction_id": payment_transaction.gateway_transaction_id,
                "gateway_order_id": payment_transaction.gateway_order_id,
                "status": payment_transaction.status,
                "payment_paid_amount": str(payment.paid_amount),
                "payment_outstanding_amount": str(payment.outstanding_amount),
                "payment_status": payment.status,
                "payment_paid_date": str(payment.paid_date) if payment.paid_date else None,
            },
        )

        payment = (
            ProjectPayment.objects
            .select_related("project")
            .prefetch_related("transactions", "documents")
            .get(id=payment.id)
        )
        response_data = ProjectPaymentDetailSerializer(payment, context={"request": request}).data

        return Response(
            {
                "status": True,
                "message": "Payment transaction added successfully.",
                "data": response_data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# UPDATE PAYMENT TRANSACTION
# =========================================================
class ProjectPaymentTransactionUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        transaction_id = request.data.get("transaction_id")
        if not transaction_id:
            return Response(
                {
                    "status": False,
                    "message": "transaction_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_transaction = (
            ProjectPaymentTransaction.objects
            .select_for_update()
            .select_related("payment", "payment__project")
            .filter(
                id=transaction_id,
                payment__project__organization=organization,
                payment__project__is_active=True,
                payment__is_active=True,
            )
            .first()
        )

        if not payment_transaction:
            return Response(
                {
                    "status": False,
                    "message": "Payment transaction not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = (
            ProjectPayment.objects
            .select_for_update()
            .select_related("project")
            .get(id=payment_transaction.payment_id)
        )

        old_data = {
            "transaction_id": payment_transaction.id,
            "payment_id": payment.id,
            "amount": str(payment_transaction.amount),
            "payment_method": payment_transaction.payment_method,
            "transaction_date": str(payment_transaction.transaction_date),
            "reference_number": payment_transaction.reference_number,
            "utr_number": payment_transaction.utr_number,
            "bank_name": payment_transaction.bank_name,
            "cheque_number": payment_transaction.cheque_number,
            "cheque_date": str(payment_transaction.cheque_date) if payment_transaction.cheque_date else None,
            "gateway_transaction_id": payment_transaction.gateway_transaction_id,
            "gateway_order_id": payment_transaction.gateway_order_id,
            "status": payment_transaction.status,
            "notes": payment_transaction.notes,
        }

        serializer = ProjectPaymentTransactionUpdateSerializer(payment_transaction, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_transaction = serializer.save()
        payment = recalculate_project_payment(payment)
        payment.updated_by = request.user
        payment.save(update_fields=["updated_by", "updated_at"])

        new_data = {
            "transaction_id": payment_transaction.id,
            "payment_id": payment.id,
            "amount": str(payment_transaction.amount),
            "payment_method": payment_transaction.payment_method,
            "transaction_date": str(payment_transaction.transaction_date),
            "reference_number": payment_transaction.reference_number,
            "utr_number": payment_transaction.utr_number,
            "bank_name": payment_transaction.bank_name,
            "cheque_number": payment_transaction.cheque_number,
            "cheque_date": str(payment_transaction.cheque_date) if payment_transaction.cheque_date else None,
            "gateway_transaction_id": payment_transaction.gateway_transaction_id,
            "gateway_order_id": payment_transaction.gateway_order_id,
            "status": payment_transaction.status,
            "notes": payment_transaction.notes,
            "payment_paid_amount": str(payment.paid_amount),
            "payment_outstanding_amount": str(payment.outstanding_amount),
            "payment_status": payment.status,
            "payment_paid_date": str(payment.paid_date) if payment.paid_date else None,
        }

        log_activity(
            request=request,
            action="UPDATE",
            module="PROJECT_PAYMENT_TRANSACTION",
            object_type="ProjectPaymentTransaction",
            object_id=payment_transaction.id,
            description=f"Payment transaction updated for project {payment.project.project_name}.",
            old_data=old_data,
            new_data=new_data,
        )

        payment = (
            ProjectPayment.objects
            .select_related("project")
            .prefetch_related("transactions", "documents")
            .get(id=payment.id)
        )
        response_data = ProjectPaymentDetailSerializer(payment, context={"request": request}).data

        return Response(
            {
                "status": True,
                "message": "Payment transaction updated successfully.",
                "data": response_data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# CANCEL PROJECT PAYMENT
# =========================================================
class ProjectPaymentDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        payment_id = request.data.get("payment_id")
        if not payment_id:
            return Response(
                {
                    "status": False,
                    "message": "payment_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = (
            ProjectPayment.objects
            .select_for_update()
            .filter(
                id=payment_id,
                project__organization=organization,
                project__is_active=True,
                is_active=True,
            )
            .select_related("project")
            .first()
        )

        if not payment:
            return Response(
                {
                    "status": False,
                    "message": "Project payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if payment.status == "CANCELLED":
            return Response(
                {
                    "status": False,
                    "message": "Payment is already cancelled.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = recalculate_project_payment(payment)

        if payment.paid_amount > Decimal("0"):
            return Response(
                {
                    "status": False,
                    "message": "A payment with received amount cannot be cancelled.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_data = {
            "project_id": payment.project.id,
            "project_name": payment.project.project_name,
            "payment_type": payment.payment_type,
            "installment_number": payment.installment_number,
            "amount": str(payment.amount),
            "paid_amount": str(payment.paid_amount),
            "outstanding_amount": str(payment.outstanding_amount),
            "paid_date": str(payment.paid_date) if payment.paid_date else None,
            "status": payment.status,
            "is_active": payment.is_active,
        }

        payment.is_active = False
        payment.status = "CANCELLED"
        payment.updated_by = request.user
        payment.save(update_fields=["is_active", "status", "updated_by", "updated_at"])

        log_activity(
            request=request,
            action="DELETE",
            module="PROJECT_PAYMENT",
            object_type="ProjectPayment",
            object_id=payment.id,
            description=f"Payment cancelled for project {payment.project.project_name}.",
            old_data=old_data,
            new_data={"status": "CANCELLED", "is_active": False},
        )

        return Response(
            {
                "status": True,
                "message": "Project payment cancelled successfully.",
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# PROJECT PAYMENTS WITH TRANSACTIONS
# =========================================================
class ProjectPaymentsByProjectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        project_id = request.data.get("project_id")
        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = (
            Project.objects
            .filter(
                id=project_id,
                organization=organization,
                is_active=True,
            )
            .first()
        )

        if not project:
            return Response(
                {
                    "status": False,
                    "message": "Project not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        payments = (
            ProjectPayment.objects
            .filter(
                project=project,
                is_active=True,
            )
            .select_related("project")
            .prefetch_related(
                "transactions",
                "documents",
            )
            .order_by(
                "payment_type",
                "installment_number",
                "-created_at",
            )
        )

        serializer = ProjectPaymentDetailSerializer(
            payments,
            many=True,
            context={
                "request": request,
            },
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Project payments and transactions "
                    "fetched successfully."
                ),
                "data": {
                    "project": {
                        "id": project.id,
                        "project_name": project.project_name,
                        "total_cost": str(project.total_cost),
                    },
                    "payments": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# SEND PROJECT PAYMENT REMINDER EMAIL
# =========================================================

class ProjectPaymentReminderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        serializer = ProjectPaymentReminderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Validation failed.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        project_ids = data["project_ids"]
        include_transaction_history = data.get("include_transaction_history", False)

        projects = (
            Project.objects
            .filter(
                id__in=project_ids,
                organization=organization,
                is_active=True,
            )
            .select_related("client", "organization")
            .order_by("-created_at")
        )

        accessible_ids = set(projects.values_list("id", flat=True))
        unauthorized = set(project_ids) - accessible_ids
        if unauthorized:
            return Response(
                {
                    "status": False,
                    "message": "You do not have access to one or more selected projects.",
                    "errors": {
                        "project_ids": [f"Project ID {pid} is not accessible." for pid in sorted(unauthorized)]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not projects.exists():
            return Response(
                {"status": False, "message": "No accessible active projects were found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = send_project_payment_reminder_emails(
                projects=projects,
                include_transaction_history=include_transaction_history,
            )
        except Exception as exc:
            return Response(
                {"status": False, "message": "Failed to process payment reminder emails.", "error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if result["total_emails_sent"] == 0 and result["total_clients"] > 0:
            return Response(
                {
                    "status": False,
                    "message": "No payment reminder emails were sent successfully.",
                    "data": {
                        "total_clients": result["total_clients"],
                        "total_emails_sent": 0,
                        "successful_clients": [],
                        "failed_clients": result["failed_clients"],
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        message = (
            "Payment reminder emails processed with some failures."
            if result["failed_clients"]
            else "Payment reminder emails sent successfully."
        )

        return Response(
            {
                "status": True,
                "message": message,
                "data": {
                    "total_clients": result["total_clients"],
                    "total_emails_sent": result["total_emails_sent"],
                    "total_projects": result["total_projects"],
                    "include_transaction_history": result["include_transaction_history"],
                    "summary": {
                        "total_amount": str(result["total_amount"]),
                        "total_paid": str(result["total_paid"]),
                        "total_outstanding": str(result["total_outstanding"]),
                        "total_overdue": str(result["total_overdue"]),
                    },
                    "successful_clients": [
                        {
                            "organization_id": item.get("organization_id"),
                            "organization_name": item.get("organization_name"),
                            "client_id": item["client_id"],
                            "client_name": item["client_name"],
                            "email": item["email"],
                            "project_ids": item["project_ids"],
                            "total_projects": item["total_projects"],
                            "total_amount": str(item["total_amount"]),
                            "total_paid": str(item["total_paid"]),
                            "total_outstanding": str(item["total_outstanding"]),
                            "total_overdue": str(item["total_overdue"]),
                        }
                        for item in result["successful_clients"]
                    ],
                    "failed_clients": result["failed_clients"],
                },
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# GENERATE PROJECT INVOICE PDF
# =========================================================
class ProjectInvoicePDFAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        project_id = request.data.get("project_id")

        if project_id is None:
            return Response(
                {"status": False, "message": "The 'project_id' field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project_id = int(project_id)
        except (ValueError, TypeError):
            return Response(
                {"status": False, "message": "project_id must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = (
            Project.objects
            .filter(
                id=project_id,
                organization=organization,
                is_active=True,
            )
            .select_related("client", "organization")
            .first()
        )

        if not project:
            return Response(
                {
                    "status": False,
                    "message": "Project not found or you do not have permission to access it.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            pdf_file, invoice_number = generate_project_invoice_pdf(project)
        except Exception as error:
            return Response(
                {
                    "status": False,
                    "message": "An error occurred while generating the invoice PDF.",
                    "error": str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = HttpResponse(pdf_file, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice_number}.pdf"'
        return response
