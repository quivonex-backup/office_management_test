from rest_framework import serializers
from urllib.parse import quote
from .models import (
    Expense,
    ExpenseDocument,
    RecurringExpense,
    RecurringExpenseEntry,
    RecurringExpenseEntryDocument,
    EmployeeReimbursement,
    EmployeeReimbursementDocument,
)


# =========================================================
# EXPENSE DOCUMENT SERIALIZER
# =========================================================
class ExpenseDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseDocument
        fields = [
            "id",
            "title",
            "file",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# =========================================================
# RECURRING EXPENSE ENTRY DOCUMENT SERIALIZER
# =========================================================
class RecurringExpenseEntryDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringExpenseEntryDocument
        fields = [
            "id",
            "title",
            "file",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# =========================================================
# EXPENSE CREATE SERIALIZER
# =========================================================
class ExpenseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "title",
            "description",
            "expense_type",
            "amount",
            "expense_date",
            "due_date",
            "vendor",
            "project",
            "payment_status",
            "payment_date",
            "payment_method",
            "reference_number",
            "notes",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate(self, attrs):
        payment_status = attrs.get("payment_status", "unpaid")
        payment_date = attrs.get("payment_date")
        payment_method = attrs.get("payment_method")
        reference_number = attrs.get("reference_number")

        # Paid status validations
        if payment_status == "paid":
            if not payment_date:
                raise serializers.ValidationError({
                    "payment_date": "Payment date is required when status is paid."
                })
            if not payment_method:
                raise serializers.ValidationError({
                    "payment_method": "Payment method is required when status is paid."
                })

        # Unpaid status validations
        if payment_status == "unpaid":
            if payment_date:
                raise serializers.ValidationError({
                    "payment_date": "Payment date must not be provided when status is unpaid."
                })
            if payment_method:
                raise serializers.ValidationError({
                    "payment_method": "Payment method must not be provided when status is unpaid."
                })
            if reference_number:
                raise serializers.ValidationError({
                    "reference_number": "Reference number must not be provided when status is unpaid."
                })

        # Date validation
        expense_date = attrs.get("expense_date")
        due_date = attrs.get("due_date")
        if expense_date and due_date and due_date < expense_date:
            raise serializers.ValidationError({
                "due_date": "Due date cannot be before expense date."
            })

        # Vendor and project active checks
        vendor = attrs.get("vendor")
        if vendor and not vendor.is_active:
            raise serializers.ValidationError({"vendor": "Selected vendor is inactive."})

        project = attrs.get("project")
        if project and not project.is_active:
            raise serializers.ValidationError({"project": "Selected project is inactive."})

        return attrs


# =========================================================
# EXPENSE LIST SERIALIZER
# =========================================================
class ExpenseListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True)
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    expense_type_display = serializers.CharField(source="get_expense_type_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    documents = ExpenseDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "expense_number",
            "title",
            "description",
            "expense_type",
            "expense_type_display",
            "amount",
            "expense_date",
            "due_date",
            "vendor",
            "vendor_name",
            "project",
            "project_name",
            "payment_status",
            "payment_status_display",
            "payment_date",
            "payment_method",
            "reference_number",
            "notes",
            "documents",
            "is_active",
            "created_at",
        ]


# =========================================================
# EXPENSE DETAIL SERIALIZER
# =========================================================
class ExpenseDetailSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True)
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    expense_type_display = serializers.CharField(source="get_expense_type_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)
    documents = ExpenseDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "expense_number",
            "title",
            "description",
            "expense_type",
            "expense_type_display",
            "amount",
            "expense_date",
            "due_date",
            "vendor",
            "vendor_name",
            "project",
            "project_name",
            "payment_status",
            "payment_status_display",
            "payment_date",
            "payment_method",
            "payment_method_display",
            "reference_number",
            "notes",
            "documents",
            "is_active",
            "created_at",
            "updated_at",
        ]


# =========================================================
# EXPENSE UPDATE SERIALIZER
# =========================================================
class ExpenseUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "title",
            "description",
            "expense_type",
            "amount",
            "expense_date",
            "due_date",
            "vendor",
            "project",
            "payment_status",
            "payment_date",
            "payment_method",
            "reference_number",
            "notes",
        ]
        extra_kwargs = {
            "title": {"required": False},
            "description": {"required": False},
            "expense_type": {"required": False},
            "amount": {"required": False},
            "expense_date": {"required": False},
        }

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate(self, attrs):
        instance = self.instance

        payment_status = attrs.get("payment_status", instance.payment_status)
        payment_date = attrs.get("payment_date", instance.payment_date)
        payment_method = attrs.get("payment_method", instance.payment_method)
        reference_number = attrs.get("reference_number", instance.reference_number)

        # Paid status validations
        if payment_status == "paid":
            if not payment_date:
                raise serializers.ValidationError({
                    "payment_date": "Payment date is required when status is paid."
                })
            if not payment_method:
                raise serializers.ValidationError({
                    "payment_method": "Payment method is required when status is paid."
                })

        # Unpaid status validations
        if payment_status == "unpaid":
            if payment_date:
                raise serializers.ValidationError({
                    "payment_date": "Payment date must not be provided when status is unpaid."
                })
            if payment_method:
                raise serializers.ValidationError({
                    "payment_method": "Payment method must not be provided when status is unpaid."
                })
            if reference_number:
                raise serializers.ValidationError({
                    "reference_number": "Reference number must not be provided when status is unpaid."
                })

        # Date validation
        expense_date = attrs.get("expense_date", instance.expense_date)
        due_date = attrs.get("due_date", instance.due_date)
        if expense_date and due_date and due_date < expense_date:
            raise serializers.ValidationError({
                "due_date": "Due date cannot be before expense date."
                })

        # Vendor and project active checks
        vendor = attrs.get("vendor", instance.vendor)
        if vendor and not vendor.is_active:
            raise serializers.ValidationError({"vendor": "Selected vendor is inactive."})

        project = attrs.get("project", instance.project)
        if project and not project.is_active:
            raise serializers.ValidationError({"project": "Selected project is inactive."})

        return attrs


# =========================================================
# RECURRING EXPENSE CREATE SERIALIZER
# =========================================================
class RecurringExpenseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringExpense
        fields = [
            "title",
            "description",
            "expense_type",
            "vendor",
            "project",
            "frequency",
            "start_date",
            "end_date",
            "notes",
        ]

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })

        vendor = attrs.get("vendor")
        if vendor and not vendor.is_active:
            raise serializers.ValidationError({"vendor": "Selected vendor is inactive."})

        project = attrs.get("project")
        if project and not project.is_active:
            raise serializers.ValidationError({"project": "Selected project is inactive."})

        return attrs


# =========================================================
# RECURRING EXPENSE LIST SERIALIZER
# =========================================================
class RecurringExpenseListSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True)
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    expense_type_display = serializers.CharField(source="get_expense_type_display", read_only=True)
    frequency_display = serializers.CharField(source="get_frequency_display", read_only=True)

    class Meta:
        model = RecurringExpense
        fields = [
            "id",
            "title",
            "description",
            "expense_type",
            "expense_type_display",
            "vendor",
            "vendor_name",
            "project",
            "project_name",
            "frequency",
            "frequency_display",
            "start_date",
            "end_date",
            "is_active",
            "notes",
            "created_at",
        ]


# =========================================================
# RECURRING EXPENSE DETAIL SERIALIZER
# =========================================================
class RecurringExpenseDetailSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True)
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    expense_type_display = serializers.CharField(source="get_expense_type_display", read_only=True)
    frequency_display = serializers.CharField(source="get_frequency_display", read_only=True)
    entries = serializers.SerializerMethodField()

    class Meta:
        model = RecurringExpense
        fields = [
            "id",
            "title",
            "description",
            "expense_type",
            "expense_type_display",
            "vendor",
            "vendor_name",
            "project",
            "project_name",
            "frequency",
            "frequency_display",
            "start_date",
            "end_date",
            "is_active",
            "notes",
            "entries",
            "created_at",
            "updated_at",
        ]

    def get_entries(self, obj):
        entries = obj.entries.all().order_by("-year", "-month")
        return RecurringExpenseEntryDetailSerializer(entries, many=True, context=self.context).data


# =========================================================
# RECURRING EXPENSE UPDATE SERIALIZER
# =========================================================
class RecurringExpenseUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringExpense
        fields = [
            "title",
            "description",
            "expense_type",
            "vendor",
            "project",
            "frequency",
            "start_date",
            "end_date",
            "notes",
        ]
        extra_kwargs = {
            "title": {"required": False},
            "description": {"required": False},
            "expense_type": {"required": False},
            "vendor": {"required": False},
            "project": {"required": False},
            "frequency": {"required": False},
            "start_date": {"required": False},
        }

    def validate(self, attrs):
        instance = self.instance

        start_date = attrs.get("start_date", instance.start_date)
        end_date = attrs.get("end_date", instance.end_date)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })

        vendor = attrs.get("vendor", instance.vendor)
        if vendor and not vendor.is_active:
            raise serializers.ValidationError({"vendor": "Selected vendor is inactive."})

        project = attrs.get("project", instance.project)
        if project and not project.is_active:
            raise serializers.ValidationError({"project": "Selected project is inactive."})

        return attrs


# =========================================================
# RECURRING EXPENSE ENTRY CREATE SERIALIZER
# =========================================================
class RecurringExpenseEntryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringExpenseEntry
        fields = [
            "recurring_expense",
            "year",
            "month",
            "amount",
            "due_date",
            "payment_status",
            "payment_date",
            "payment_method",
            "reference_number",
            "notes",
        ]

    def validate_year(self, value):
        if value < 2000 or value > 2100:
            raise serializers.ValidationError("Invalid year.")
        return value

    def validate_month(self, value):
        if value < 1 or value > 12:
            raise serializers.ValidationError("Month must be between 1 and 12.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate(self, attrs):
        recurring_expense = attrs.get("recurring_expense")
        if not recurring_expense.is_active:
            raise serializers.ValidationError({
                "recurring_expense": "Selected recurring expense is inactive."
            })

        payment_status = attrs.get("payment_status", "unpaid")
        payment_date = attrs.get("payment_date")
        payment_method = attrs.get("payment_method")
        reference_number = attrs.get("reference_number")

        if payment_status == "paid":
            if not payment_date:
                raise serializers.ValidationError({
                    "payment_date": "Payment date is required when status is paid."
                })
            if not payment_method:
                raise serializers.ValidationError({
                    "payment_method": "Payment method is required when status is paid."
                })

        if payment_status == "unpaid":
            if payment_date:
                raise serializers.ValidationError({
                    "payment_date": "Payment date must not be provided when status is unpaid."
                })
            if payment_method:
                raise serializers.ValidationError({
                    "payment_method": "Payment method must not be provided when status is unpaid."
                })
            if reference_number:
                raise serializers.ValidationError({
                    "reference_number": "Reference number must not be provided when status is unpaid."
                })

        return attrs


# =========================================================
# RECURRING EXPENSE ENTRY DETAIL SERIALIZER
# =========================================================
class RecurringExpenseEntryDetailSerializer(serializers.ModelSerializer):
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)
    recurring_expense_title = serializers.CharField(source="recurring_expense.title", read_only=True)
    documents = RecurringExpenseEntryDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = RecurringExpenseEntry
        fields = [
            "id",
            "recurring_expense",
            "recurring_expense_title",
            "year",
            "month",
            "amount",
            "due_date",
            "payment_status",
            "payment_status_display",
            "payment_date",
            "payment_method",
            "payment_method_display",
            "reference_number",
            "notes",
            "documents",
            "created_at",
            "updated_at",
        ]


# =========================================================
# RECURRING EXPENSE ENTRY UPDATE SERIALIZER
# =========================================================
class RecurringExpenseEntryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringExpenseEntry
        fields = [
            "year",
            "month",
            "amount",
            "due_date",
            "payment_status",
            "payment_date",
            "payment_method",
            "reference_number",
            "notes",
        ]
        extra_kwargs = {
            "year": {"required": False},
            "month": {"required": False},
            "amount": {"required": False},
        }

    def validate_year(self, value):
        if value < 2000 or value > 2100:
            raise serializers.ValidationError("Invalid year.")
        return value

    def validate_month(self, value):
        if value < 1 or value > 12:
            raise serializers.ValidationError("Month must be between 1 and 12.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return value

    def validate(self, attrs):
        instance = self.instance

        payment_status = attrs.get("payment_status", instance.payment_status)
        payment_date = attrs.get("payment_date", instance.payment_date)
        payment_method = attrs.get("payment_method", instance.payment_method)
        reference_number = attrs.get("reference_number", instance.reference_number)

        if payment_status == "paid":
            if not payment_date:
                raise serializers.ValidationError({
                    "payment_date": "Payment date is required when status is paid."
                })
            if not payment_method:
                raise serializers.ValidationError({
                    "payment_method": "Payment method is required when status is paid."
                })

        if payment_status == "unpaid":
            if payment_date:
                raise serializers.ValidationError({
                    "payment_date": "Payment date must not be provided when status is unpaid."
                })
            if payment_method:
                raise serializers.ValidationError({
                    "payment_method": "Payment method must not be provided when status is unpaid."
                })
            if reference_number:
                raise serializers.ValidationError({
                    "reference_number": "Reference number must not be provided when status is unpaid."
                })

        return attrs


# =========================================================
# REIMBURSEMENT SHARED HELPERS
# =========================================================
def _employee_full_name(employee):
    if not employee:
        return None
    parts = [
        employee.first_name,
        employee.middle_name,
        employee.last_name,
    ]
    name = " ".join(p for p in parts if p).strip()
    return name or employee.employee_code


def _user_display_name(user):
    if not user:
        return None
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.username


def _build_reimbursement_upi_link(reimbursement):
    """
    Build a UPI deep link for an APPROVED reimbursement.
    Returns None if status != APPROVED or payee UPI is missing.
    """
    if reimbursement.status != "APPROVED":
        return None

    payee_upi = None

    if reimbursement.payee_upi_id:
        payee_upi = reimbursement.payee_upi_id.strip()
    elif reimbursement.employee and reimbursement.employee.upi_id:
        payee_upi = reimbursement.employee.upi_id.strip()

    if not payee_upi:
        return None

    payee_name = _employee_full_name(reimbursement.employee) or "Employee"
    note = f"{reimbursement.reimbursement_number} - {reimbursement.title}"

    return (
        f"upi://pay?"
        f"pa={quote(payee_upi)}"
        f"&pn={quote(payee_name)}"
        f"&am={reimbursement.amount}"
        f"&cu=INR"
        f"&tn={quote(note)}"
    )


# =========================================================
# EMPLOYEE REIMBURSEMENT DOCUMENT SERIALIZER
# =========================================================
class EmployeeReimbursementDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeReimbursementDocument
        fields = [
            "id",
            "title",
            "file",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# =========================================================
# EMPLOYEE REIMBURSEMENT CREATE SERIALIZER
# =========================================================
class EmployeeReimbursementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeReimbursement
        fields = [
            "title",
            "description",
            "expense_type",
            "amount",
            "expense_date",
            "project",
            "payee_upi_id",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Amount must be greater than 0."
            )
        return value

    def validate(self, attrs):
        organization = self.context.get("organization")
        project = attrs.get("project")

        if project and organization:
            if project.organization_id != organization.id:
                raise serializers.ValidationError({
                    "project": (
                        "Selected project does not belong to "
                        "this organization."
                    )
                })

        if project and not project.is_active:
            raise serializers.ValidationError({
                "project": "Selected project is inactive."
            })

        return attrs


# =========================================================
# EMPLOYEE REIMBURSEMENT LIST SERIALIZER
# =========================================================
class EmployeeReimbursementListSerializer(serializers.ModelSerializer):

    employee_code = serializers.CharField(
        source="employee.employee_code", read_only=True
    )
    employee_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(
        source="project.project_name", read_only=True
    )
    project_code = serializers.CharField(
        source="project.project_code", read_only=True
    )
    expense_type_display = serializers.CharField(
        source="get_expense_type_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    payee_name = serializers.SerializerMethodField()
    upi_link = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeReimbursement
        fields = [
            "id",
            "reimbursement_number",
            "title",
            "description",
            "expense_type",
            "expense_type_display",
            "amount",
            "expense_date",
            "employee",
            "employee_code",
            "employee_name",
            "project",
            "project_name",
            "project_code",
            "payee_upi_id",
            "payee_name",
            "upi_link",
            "status",
            "payment_date",
            "payment_method",
            "payment_method_display",
            "payment_reference",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return _employee_full_name(obj.employee)

    def get_payee_name(self, obj):
        return _employee_full_name(obj.employee)

    def get_upi_link(self, obj):
        return _build_reimbursement_upi_link(obj)


# =========================================================
# EMPLOYEE REIMBURSEMENT DETAIL SERIALIZER
# =========================================================
class EmployeeReimbursementDetailSerializer(serializers.ModelSerializer):

    employee_code = serializers.CharField(
        source="employee.employee_code", read_only=True
    )
    employee_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(
        source="project.project_name", read_only=True
    )
    project_code = serializers.CharField(
        source="project.project_code", read_only=True
    )
    expense_type_display = serializers.CharField(
        source="get_expense_type_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    payee_name = serializers.SerializerMethodField()
    upi_link = serializers.SerializerMethodField()
    documents = EmployeeReimbursementDocumentSerializer(
        many=True, read_only=True
    )
    reviewed_by_details = serializers.SerializerMethodField()
    paid_by_details = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeReimbursement
        fields = [
            "id",
            "reimbursement_number",
            "organization",
            "title",
            "description",
            "expense_type",
            "expense_type_display",
            "amount",
            "expense_date",
            "employee",
            "employee_code",
            "employee_name",
            "project",
            "project_name",
            "project_code",
            "payee_upi_id",
            "payee_name",
            "upi_link",
            "status",
            "reviewed_by_details",
            "reviewed_at",
            "review_notes",
            "rejection_reason",
            "payment_date",
            "payment_method",
            "payment_method_display",
            "payment_reference",
            "paid_by_details",
            "documents",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return _employee_full_name(obj.employee)

    def get_payee_name(self, obj):
        return _employee_full_name(obj.employee)

    def get_upi_link(self, obj):
        return _build_reimbursement_upi_link(obj)

    def get_reviewed_by_details(self, obj):
        if not obj.reviewed_by:
            return None
        return {
            "id": obj.reviewed_by.id,
            "name": _user_display_name(obj.reviewed_by),
            "email": obj.reviewed_by.email,
        }

    def get_paid_by_details(self, obj):
        if not obj.paid_by:
            return None
        return {
            "id": obj.paid_by.id,
            "name": _user_display_name(obj.paid_by),
            "email": obj.paid_by.email,
        }


# =========================================================
# REIMBURSEMENT REVIEW SERIALIZER
# =========================================================
class EmployeeReimbursementReviewSerializer(serializers.Serializer):
    reimbursement_id = serializers.IntegerField()
    approve = serializers.BooleanField()
    review_notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    rejection_reason = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate(self, attrs):
        if not attrs.get("approve"):
            rejection_reason = (attrs.get("rejection_reason") or "").strip()
            if not rejection_reason:
                raise serializers.ValidationError({
                    "rejection_reason": (
                        "Rejection reason is required when rejecting."
                    )
                })
        return attrs


# =========================================================
# REIMBURSEMENT MARK-PAID SERIALIZER
# =========================================================
class EmployeeReimbursementMarkPaidSerializer(serializers.Serializer):
    reimbursement_id = serializers.IntegerField()
    payment_date = serializers.DateField()
    payment_method = serializers.ChoiceField(
        choices=Expense.PAYMENT_METHOD_CHOICES
    )
    payment_reference = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
