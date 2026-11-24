from rest_framework import serializers

from .models import Ticket, TicketCategory, TicketComment


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
class CategoryWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    default_assignee_id = serializers.IntegerField(required=False, allow_null=True)


class TicketCreateSerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    subject = serializers.CharField(max_length=200)
    description = serializers.CharField()
    priority = serializers.ChoiceField(choices=Ticket.PRIORITY_CHOICES, required=False, default="MEDIUM")
    raised_by_id = serializers.IntegerField(required=False, allow_null=True)   # ticket.manage only


# =========================================================
# OUTPUT
# =========================================================
class TicketCategorySerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()
    default_assignee = serializers.SerializerMethodField()
    open_tickets = serializers.SerializerMethodField()

    class Meta:
        model = TicketCategory
        fields = ["id", "name", "description", "department", "default_assignee", "open_tickets",
                  "is_active", "created_at", "updated_at"]

    def get_department(self, obj):
        return _ref(obj.department)

    def get_default_assignee(self, obj):
        return _emp_ref(obj.default_assignee)

    def get_open_tickets(self, obj):
        value = getattr(obj, "open_count", None)
        if value is None:
            value = obj.tickets.filter(is_active=True).exclude(status="CLOSED").count()
        return value


class TicketCategoryOptionSerializer(serializers.ModelSerializer):
    """Short list for the employee 'raise ticket' form."""

    class Meta:
        model = TicketCategory
        fields = ["id", "name", "description"]


class TicketListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    raised_by = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = ["id", "ticket_code", "subject", "category", "priority", "status",
                  "raised_by", "assigned_to", "created_at", "updated_at", "resolved_at", "closed_at"]

    def get_category(self, obj):
        return _ref(obj.category)

    def get_raised_by(self, obj):
        return _emp_ref(obj.raised_by)

    def get_assigned_to(self, obj):
        return _emp_ref(obj.assigned_to)


class TicketDetailSerializer(TicketListSerializer):
    class Meta(TicketListSerializer.Meta):
        fields = TicketListSerializer.Meta.fields + ["description", "attachment"]


class TicketCommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = TicketComment
        fields = ["id", "author", "message", "attachment", "is_internal", "is_system", "created_at"]

    def get_author(self, obj):
        return _user_ref(obj.author)
