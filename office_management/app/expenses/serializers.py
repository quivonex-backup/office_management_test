from rest_framework import serializers
from .models import (
    Expense,
    ExpenseDocument,
    RecurringExpense,
    RecurringExpenseEntry,
    RecurringExpenseEntryDocument,
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