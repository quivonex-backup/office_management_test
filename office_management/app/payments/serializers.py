from decimal import Decimal

from django.db import models
from django.utils import timezone
from rest_framework import serializers

from .models import (
    ProjectPayment,
    ProjectPaymentTransaction,
    ProjectPaymentDocument,
)
from app.clients.models import Client
from app.projects.models import Project


# =========================================================
# PROJECT PAYMENT DOCUMENT SERIALIZER
# =========================================================

class ProjectPaymentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPaymentDocument
        fields = [
            "id",
            "title",
            "file",
            "description",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]


# =========================================================
# PROJECT PAYMENT TRANSACTION SERIALIZER
# =========================================================

class ProjectPaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPaymentTransaction
        fields = [
            "id",
            "amount",
            "payment_method",
            "transaction_date",
            "reference_number",
            "utr_number",
            "bank_name",
            "cheque_number",
            "cheque_date",
            "gateway_transaction_id",
            "gateway_order_id",
            "status",
            "notes",
            "received_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "received_by",
            "created_at",
        ]


# =========================================================
# PROJECT PAYMENT TRANSACTION CREATE SERIALIZER
# =========================================================

class ProjectPaymentTransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPaymentTransaction
        fields = [
            "amount",
            "payment_method",
            "transaction_date",
            "reference_number",
            "utr_number",
            "bank_name",
            "cheque_number",
            "cheque_date",
            "gateway_transaction_id",
            "gateway_order_id",
            "notes",
        ]

    def validate(self, attrs):
        payment = self.context.get("payment")

        # Payment validation
        if not payment:
            raise serializers.ValidationError({"payment": "Payment is required."})
        if not payment.is_active:
            raise serializers.ValidationError({"payment": "This payment is inactive."})
        if payment.status == "CANCELLED":
            raise serializers.ValidationError({"payment": "Cancelled payment cannot receive a transaction."})

        # Amount validation
        amount = attrs.get("amount")
        if amount is None:
            raise serializers.ValidationError({"amount": "Transaction amount is required."})
        if amount <= Decimal("0"):
            raise serializers.ValidationError({"amount": "Transaction amount must be greater than zero."})

        # Successful transactions
        successful_amount = (
            ProjectPaymentTransaction.objects
            .filter(payment=payment, status="SUCCESS")
            .aggregate(total=models.Sum("amount"))["total"]
            or Decimal("0")
        )
        remaining_amount = payment.amount - successful_amount

        # Transaction cannot exceed outstanding
        if amount > remaining_amount:
            raise serializers.ValidationError(
                {"amount": f"Transaction amount cannot exceed the outstanding amount of {remaining_amount}."}
            )

        # Transaction date
        transaction_date = attrs.get("transaction_date")
        if not transaction_date:
            raise serializers.ValidationError({"transaction_date": "Transaction date is required."})
        if transaction_date > timezone.now().date():
            raise serializers.ValidationError({"transaction_date": "Transaction date cannot be in the future."})

        # Payment method specific validations
        payment_method = attrs.get("payment_method")

        if payment_method == "UPI":
            if not attrs.get("utr_number"):
                raise serializers.ValidationError({"utr_number": "UTR number is required for UPI payment."})

        elif payment_method == "BANK_TRANSFER":
            if not attrs.get("utr_number"):
                raise serializers.ValidationError({"utr_number": "UTR number is required for bank transfer."})
            if not attrs.get("bank_name"):
                raise serializers.ValidationError({"bank_name": "Bank name is required for bank transfer."})

        elif payment_method == "CHEQUE":
            if not attrs.get("cheque_number"):
                raise serializers.ValidationError({"cheque_number": "Cheque number is required for cheque payment."})
            if not attrs.get("cheque_date"):
                raise serializers.ValidationError({"cheque_date": "Cheque date is required for cheque payment."})
            if not attrs.get("bank_name"):
                raise serializers.ValidationError({"bank_name": "Bank name is required for cheque payment."})
            if attrs.get("cheque_date") > timezone.now().date():
                raise serializers.ValidationError({"cheque_date": "Cheque date cannot be in the future."})

        elif payment_method == "CARD":
            if not attrs.get("gateway_transaction_id"):
                raise serializers.ValidationError(
                    {"gateway_transaction_id": "Gateway transaction ID is required for card payment."}
                )

        elif payment_method == "ONLINE":
            if not attrs.get("gateway_transaction_id"):
                raise serializers.ValidationError(
                    {"gateway_transaction_id": "Gateway transaction ID is required for online payment."}
                )

        elif payment_method == "CASH":
            if not attrs.get("reference_number"):
                raise serializers.ValidationError(
                    {"reference_number": "Receipt/reference number is required for cash payment."}
                )

        elif payment_method == "OTHER":
            if not attrs.get("reference_number"):
                raise serializers.ValidationError(
                    {"reference_number": "Reference number is required for other payment."}
                )

        return attrs

    def create(self, validated_data):
        validated_data["status"] = "SUCCESS"
        return ProjectPaymentTransaction.objects.create(**validated_data)


# =========================================================
# PROJECT PAYMENT TRANSACTION UPDATE SERIALIZER
# =========================================================

class ProjectPaymentTransactionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPaymentTransaction
        fields = [
            "status",
            "notes",
        ]
        extra_kwargs = {
            "status": {"required": True},
            "notes": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        payment_transaction = self.instance
        new_status = attrs.get("status")

        if not payment_transaction:
            raise serializers.ValidationError({"transaction": "Transaction is required."})

        # Closed transactions
        if payment_transaction.status in ["REFUNDED", "CANCELLED", "FAILED"]:
            raise serializers.ValidationError(
                {"status": "This transaction is already closed and cannot be updated."}
            )

        # SUCCESS -> REFUNDED / CANCELLED
        if payment_transaction.status == "SUCCESS":
            if new_status not in ["REFUNDED", "CANCELLED"]:
                raise serializers.ValidationError(
                    {"status": "A successful transaction can only be changed to REFUNDED or CANCELLED."}
                )
        else:
            raise serializers.ValidationError(
                {"status": "This transaction cannot be updated to the requested status."}
            )

        return attrs


# =========================================================
# PROJECT PAYMENT CREATE SERIALIZER
# =========================================================

class ProjectPaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPayment
        fields = [
            "project",
            "payment_type",
            "installment_number",
            "title",
            "amount",
            "due_date",
            "notes",
        ]
        extra_kwargs = {
            "installment_number": {"required": False, "allow_null": True},
            "title": {"required": False, "allow_null": True},
            "due_date": {"required": False, "allow_null": True},
            "notes": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        project = attrs.get("project")
        payment_type = attrs.get("payment_type")
        installment_number = attrs.get("installment_number")
        amount = attrs.get("amount")

        # Project
        if not project:
            raise serializers.ValidationError({"project": "Project is required."})
        if not project.is_active:
            raise serializers.ValidationError({"project": "This project is inactive."})

        # Payment type
        if payment_type not in ["ADVANCE", "INSTALLMENT"]:
            raise serializers.ValidationError({"payment_type": "Invalid payment type."})

        # Amount
        if amount is None:
            raise serializers.ValidationError({"amount": "Amount is required."})
        if amount <= Decimal("0"):
            raise serializers.ValidationError({"amount": "Amount must be greater than zero."})

        # Advance
        if payment_type == "ADVANCE":
            if (
                ProjectPayment.objects
                .filter(project=project, payment_type="ADVANCE", is_active=True)
                .exclude(status="CANCELLED")
                .exists()
            ):
                raise serializers.ValidationError(
                    {"payment_type": "Advance payment already exists for this project."}
                )
            if installment_number is not None:
                raise serializers.ValidationError(
                    {"installment_number": "Installment number is not allowed for an advance payment."}
                )

        # Installment
        elif payment_type == "INSTALLMENT":
            if installment_number is not None:
                if installment_number <= 0:
                    raise serializers.ValidationError(
                        {"installment_number": "Installment number must be greater than zero."}
                    )
                if (
                    ProjectPayment.objects
                    .filter(
                        project=project,
                        payment_type="INSTALLMENT",
                        installment_number=installment_number,
                        is_active=True,
                    )
                    .exclude(status="CANCELLED")
                    .exists()
                ):
                    raise serializers.ValidationError(
                        {"installment_number": "This installment number already exists for this project."}
                    )

        # Project total validation
        current_total = (
            ProjectPayment.objects
            .filter(project=project, is_active=True)
            .exclude(status="CANCELLED")
            .aggregate(total=models.Sum("amount"))["total"]
            or Decimal("0")
        )
        new_total = current_total + amount

        if new_total > project.total_cost:
            remaining_amount = project.total_cost - current_total
            raise serializers.ValidationError(
                {"amount": f"Payment amount exceeds the remaining project amount. Maximum allowed amount is {remaining_amount}."}
            )

        return attrs

    def create(self, validated_data):
        amount = validated_data["amount"]
        return ProjectPayment.objects.create(
            **validated_data,
            paid_amount=Decimal("0"),
            outstanding_amount=amount,
            status="PENDING",
        )


# =========================================================
# PROJECT PAYMENT LIST SERIALIZER
# =========================================================

class ProjectPaymentListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    transactions = ProjectPaymentTransactionSerializer(many=True, read_only=True)
    documents = ProjectPaymentDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectPayment
        fields = [
            "id",
            "project",
            "project_name",
            "payment_type",
            "installment_number",
            "title",
            "amount",
            "paid_amount",
            "outstanding_amount",
            "due_date",
            "paid_date",
            "status",
            "notes",
            "transactions",
            "documents",
            "is_active",
            "created_at",
            "updated_at",
        ]


# =========================================================
# PROJECT PAYMENT DETAIL SERIALIZER
# =========================================================

class ProjectPaymentDetailSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    project_total_cost = serializers.DecimalField(
        source="project.total_cost",
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )
    transactions = ProjectPaymentTransactionSerializer(many=True, read_only=True)
    documents = ProjectPaymentDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectPayment
        fields = [
            "id",
            "project",
            "project_name",
            "project_total_cost",
            "payment_type",
            "installment_number",
            "title",
            "amount",
            "paid_amount",
            "outstanding_amount",
            "due_date",
            "paid_date",
            "status",
            "notes",
            "transactions",
            "documents",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project_total_cost",
            "paid_amount",
            "outstanding_amount",
            "paid_date",
            "status",
            "transactions",
            "documents",
            "created_at",
            "updated_at",
        ]


# =========================================================
# PROJECT PAYMENT UPDATE SERIALIZER
# =========================================================

class ProjectPaymentUpdateSerializer(serializers.ModelSerializer):
    delete_document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        write_only=True,
    )

    class Meta:
        model = ProjectPayment
        fields = [
            "installment_number",
            "title",
            "amount",
            "due_date",
            "notes",
            "delete_document_ids",
        ]
        extra_kwargs = {
            "installment_number": {"required": False, "allow_null": True},
            "title": {"required": False, "allow_null": True},
            "amount": {"required": False},
            "due_date": {"required": False, "allow_null": True},
            "notes": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        payment = self.instance

        # Payment validation
        if not payment.is_active:
            raise serializers.ValidationError({"payment": "Inactive payment cannot be updated."})
        if payment.status == "CANCELLED":
            raise serializers.ValidationError({"payment": "Cancelled payment cannot be updated."})

        # Installment validation
        if payment.payment_type == "INSTALLMENT":
            installment_number = attrs.get("installment_number", payment.installment_number)
            if installment_number is None:
                raise serializers.ValidationError({"installment_number": "Installment number is required."})
            if installment_number <= 0:
                raise serializers.ValidationError({"installment_number": "Installment number must be greater than zero."})
            duplicate_exists = (
                ProjectPayment.objects
                .filter(
                    project=payment.project,
                    payment_type="INSTALLMENT",
                    installment_number=installment_number,
                    is_active=True,
                )
                .exclude(id=payment.id)
                .exclude(status="CANCELLED")
                .exists()
            )
            if duplicate_exists:
                raise serializers.ValidationError(
                    {"installment_number": "This installment number already exists for this project."}
                )

        # Advance validation
        elif payment.payment_type == "ADVANCE":
            if "installment_number" in attrs and attrs["installment_number"] is not None:
                raise serializers.ValidationError(
                    {"installment_number": "Installment number is not allowed for an advance payment."}
                )

        # Amount
        new_amount = attrs.get("amount", payment.amount)
        if new_amount <= Decimal("0"):
            raise serializers.ValidationError({"amount": "Amount must be greater than zero."})

        # Successful transactions
        successful_amount = (
            ProjectPaymentTransaction.objects
            .filter(payment=payment, status="SUCCESS")
            .aggregate(total=models.Sum("amount"))["total"]
            or Decimal("0")
        )
        if new_amount < successful_amount:
            raise serializers.ValidationError(
                {"amount": f"Amount cannot be less than the already received amount of {successful_amount}."}
            )

        # Project total
        other_payments_total = (
            ProjectPayment.objects
            .filter(project=payment.project, is_active=True)
            .exclude(id=payment.id)
            .exclude(status="CANCELLED")
            .aggregate(total=models.Sum("amount"))["total"]
            or Decimal("0")
        )
        new_project_total = other_payments_total + new_amount
        if new_project_total > payment.project.total_cost:
            remaining_amount = payment.project.total_cost - other_payments_total
            raise serializers.ValidationError(
                {"amount": f"Payment amount exceeds the remaining project amount. Maximum allowed amount is {remaining_amount}."}
            )

        # Document delete validation
        delete_document_ids = attrs.get("delete_document_ids", [])
        if delete_document_ids:
            existing_ids = set(
                ProjectPaymentDocument.objects
                .filter(payment=payment)
                .values_list("id", flat=True)
            )
            invalid_ids = set(delete_document_ids) - existing_ids
            if invalid_ids:
                raise serializers.ValidationError(
                    {"delete_document_ids": "One or more document IDs do not belong to this payment."}
                )

        return attrs

    def update(self, instance, validated_data):
        # IMPORTANT: Do NOT handle delete_document_ids here.
        # The view handles document deletion because S3 deletion must happen there.
        validated_data.pop("delete_document_ids", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# =========================================================
# PROJECT PAYMENT REMINDER SERIALIZER
# =========================================================

class ProjectPaymentReminderSerializer(serializers.Serializer):
    project_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=True,
        allow_empty=False,
    )
    include_transaction_history = serializers.BooleanField(
        required=False,
        default=False,
    )

    def validate_project_ids(self, value):
        """
        Validate project IDs.

        Checks:
        - Duplicate project IDs are not allowed.
        - All project IDs exist and are active.

        Client validation is not done here; projects can belong to different clients.
        """
        # Duplicate check
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Duplicate project IDs are not allowed.")

        # Fetch active projects
        projects = Project.objects.filter(id__in=value, is_active=True)
        found_ids = set(projects.values_list("id", flat=True))

        # Find missing/inactive IDs
        missing = [pid for pid in value if pid not in found_ids]
        if missing:
            raise serializers.ValidationError({
                "project_ids": "The following project IDs were not found or are inactive: {}".format(missing)
            })

        return value
