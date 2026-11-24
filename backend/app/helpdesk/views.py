"""
Helpdesk API (all POST, envelope {status, message, data, errors?}).

  category/create|update|deactivate/   ticket.manage
  category/list/                       ticket.manage, ticket.handle (any)
  category/options/                    any employee (active categories for the form)
  ticket/create/                       any employee (ticket.manage may raise for someone)
  ticket/my-tickets/                   any employee (raised by me / assigned to me)
  ticket/list/                         ticket.manage (all) | ticket.handle (own department + assigned)
  ticket/detail/ | status-update/ | comment/    raiser, handler, assignee or manager
  ticket/assign/ | update/             handler, assignee or manager
"""
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from app.audit.services import log_activity
from common.permissions import OrgAPIView, RequiredPermsMixin, get_user_employee, has_perm
from common.s3_utils import upload_to_s3
from common.services import get_user_organization

from .models import Ticket, TicketCategory, TicketComment
from .serializers import (
    CategoryWriteSerializer,
    TicketCategoryOptionSerializer,
    TicketCategorySerializer,
    TicketCommentSerializer,
    TicketCreateSerializer,
    TicketDetailSerializer,
    TicketListSerializer,
)
from .services import (
    HelpdeskError,
    add_comment,
    allowed,
    assign_ticket,
    change_status,
    create_ticket,
    is_staff,
    staff_queryset,
    ticket_roles,
)

TICKET_RELATED = ("category", "category__department", "raised_by", "raised_by__user", "assigned_to", "assigned_to__user")


# =========================================================
# SHARED
# =========================================================
class HelpdeskBaseAPIView(RequiredPermsMixin, OrgAPIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_org(self, request):
        return get_user_organization(request)

    def handle_helpdesk_error(self, exc):
        if exc.errors:
            return self.fail(str(exc), exc.errors)
        return self.fail(str(exc))

    def find_employee(self, organization, employee_id, field):
        from app.employees.models import Employee

        if employee_id in (None, "", "null"):
            return None, None
        emp = Employee.objects.filter(pk=employee_id, organization=organization, is_active=True).first()
        if emp is None:
            return None, self.fail("Validation failed.", {field: ["Active employee not found."]})
        return emp, None

    def find_department(self, organization, department_id):
        from app.employees.models import Department

        if department_id in (None, "", "null"):
            return None, None
        dept = Department.objects.filter(pk=department_id, organization=organization, is_active=True).first()
        if dept is None:
            return None, self.fail("Validation failed.", {"department_id": ["Active department not found."]})
        return dept, None

    def find_category(self, organization, category_id, active_only=True):
        qs = TicketCategory.objects.filter(organization=organization, pk=category_id)
        if active_only:
            qs = qs.filter(is_active=True)
        return qs.select_related("department", "default_assignee").first()

    def get_ticket(self, request, organization):
        """Ticket + caller roles; 404 when the caller has no role on it."""
        ticket_id = request.data.get("ticket_id")
        if not ticket_id:
            return None, None, self.fail("ticket_id is required.")
        ticket = (
            Ticket.objects.filter(pk=ticket_id, organization=organization, is_active=True)
            .select_related(*TICKET_RELATED).first()
        )
        roles = ticket_roles(request, organization, ticket) if ticket else set()
        if not roles:
            return None, None, self.fail("Ticket not found.", http_status=status.HTTP_404_NOT_FOUND)
        return ticket, roles, None

    def detail_data(self, ticket, roles):
        comments = ticket.comments.select_related("author")
        if not is_staff(roles):
            comments = comments.filter(is_internal=False)
        return {
            "ticket": TicketDetailSerializer(ticket).data,
            "comments": TicketCommentSerializer(comments, many=True).data,
            "my_roles": sorted(roles),
            "allowed_actions": allowed(ticket, roles),
        }

    def upload(self, request, key="attachment"):
        file = request.FILES.get(key)
        if not file:
            return None
        return upload_to_s3(file=file, folder="helpdesk/attachments")


# =========================================================
# CATEGORY — CREATE
# =========================================================
class TicketCategoryCreateAPIView(HelpdeskBaseAPIView):
    required_perms = ("ticket.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        s = CategoryWriteSerializer(data=request.data)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data

        name = data["name"].strip()
        if TicketCategory.objects.filter(organization=organization, name__iexact=name).exists():
            return self.fail("Validation failed.", {"name": ["A category with this name already exists."]})

        department, err = self.find_department(organization, data.get("department_id"))
        if err:
            return err
        assignee, err = self.find_employee(organization, data.get("default_assignee_id"), "default_assignee_id")
        if err:
            return err

        category = TicketCategory.objects.create(
            organization=organization, name=name, description=data.get("description") or None,
            department=department, default_assignee=assignee,
            created_by=request.user, updated_by=request.user,
        )
        log_activity(
            request=request, action="CREATE", module="HELPDESK", object_type="TicketCategory",
            object_id=category.id, description=f"Ticket category {category.name} created.",
            new_data={"name": category.name, "department_id": category.department_id,
                      "default_assignee_id": category.default_assignee_id},
        )
        return self.ok("Category created.", TicketCategorySerializer(category).data, status.HTTP_201_CREATED)


# =========================================================
# CATEGORY — LIST (handling side)
# =========================================================
class TicketCategoryListAPIView(HelpdeskBaseAPIView):
    required_perms = ("ticket.manage", "ticket.handle")

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        qs = TicketCategory.objects.filter(organization=organization).select_related("department", "default_assignee")
        if self.parse_bool(request.data.get("include_inactive")) is not True:
            qs = qs.filter(is_active=True)
        qs = qs.annotate(open_count=Count(
            "tickets", filter=Q(tickets__is_active=True) & ~Q(tickets__status="CLOSED")))
        return self.ok("Categories fetched.", TicketCategorySerializer(qs.order_by("name"), many=True).data)


# =========================================================
# CATEGORY — OPTIONS (raise ticket form)
# =========================================================
class TicketCategoryOptionsAPIView(HelpdeskBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        qs = TicketCategory.objects.filter(organization=organization, is_active=True).order_by("name")
        return self.ok("Categories fetched.", TicketCategoryOptionSerializer(qs, many=True).data)


# =========================================================
# CATEGORY — UPDATE
# =========================================================
class TicketCategoryUpdateAPIView(HelpdeskBaseAPIView):
    required_perms = ("ticket.manage",)

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        category = self.find_category(organization, request.data.get("category_id"), active_only=False)
        if category is None:
            return self.fail("Category not found.", http_status=status.HTTP_404_NOT_FOUND)

        s = CategoryWriteSerializer(data=request.data, partial=True)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data
        old = {"name": category.name, "department_id": category.department_id,
               "default_assignee_id": category.default_assignee_id, "is_active": category.is_active}

        if "name" in data:
            name = data["name"].strip()
            if TicketCategory.objects.filter(organization=organization, name__iexact=name).exclude(pk=category.pk).exists():
                return self.fail("Validation failed.", {"name": ["A category with this name already exists."]})
            category.name = name
        if "description" in data:
            category.description = data.get("description") or None
        if "department_id" in data:
            category.department, err = self.find_department(organization, data.get("department_id"))
            if err:
                return err
        if "default_assignee_id" in data:
            category.default_assignee, err = self.find_employee(
                organization, data.get("default_assignee_id"), "default_assignee_id")
            if err:
                return err
        if self.parse_bool(request.data.get("is_active")) is True:
            category.is_active = True
        category.updated_by = request.user
        category.save()

        log_activity(
            request=request, action="UPDATE", module="HELPDESK", object_type="TicketCategory",
            object_id=category.id, description=f"Ticket category {category.name} updated.",
            old_data=old,
            new_data={"name": category.name, "department_id": category.department_id,
                      "default_assignee_id": category.default_assignee_id, "is_active": category.is_active},
        )
        return self.ok("Category updated.", TicketCategorySerializer(category).data)


# =========================================================
# CATEGORY — DEACTIVATE
# =========================================================
class TicketCategoryDeactivateAPIView(HelpdeskBaseAPIView):
    required_perms = ("ticket.manage",)

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
            request=request, action="DELETE", module="HELPDESK", object_type="TicketCategory",
            object_id=category.id, description=f"Ticket category {category.name} deactivated.",
        )
        return self.ok("Category deactivated. Existing tickets keep it; new tickets cannot use it.")


# =========================================================
# TICKET — CREATE
# =========================================================
class TicketCreateAPIView(HelpdeskBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        s = TicketCreateSerializer(data=request.data)
        if not s.is_valid():
            return self.fail("Validation failed.", s.errors)
        data = s.validated_data

        category = self.find_category(organization, data["category_id"])
        if category is None:
            return self.fail("Validation failed.", {"category_id": ["Active category not found."]})

        if data.get("raised_by_id"):
            if not has_perm(request, organization, "ticket.manage"):
                return self.fail("Only ticket managers can raise a ticket for someone else.",
                                 http_status=status.HTTP_403_FORBIDDEN)
            raised_by, err = self.find_employee(organization, data["raised_by_id"], "raised_by_id")
            if err:
                return err
        else:
            raised_by = get_user_employee(request.user, organization)
            if raised_by is None:
                return self.fail("No active employee profile is linked to this user.",
                                 http_status=status.HTTP_404_NOT_FOUND)

        ticket = create_ticket(
            organization, category, raised_by, data["subject"].strip(), data["description"].strip(),
            data.get("priority"), request.user, attachment=self.upload(request),
        )
        log_activity(
            request=request, action="CREATE", module="HELPDESK", object_type="Ticket",
            object_id=ticket.id, description=f"Ticket {ticket.ticket_code} raised.",
            new_data={"category_id": category.id, "raised_by_id": raised_by.id, "priority": ticket.priority},
        )
        ticket = Ticket.objects.select_related(*TICKET_RELATED).get(pk=ticket.pk)
        roles = ticket_roles(request, organization, ticket)
        return self.ok("Ticket raised.", self.detail_data(ticket, roles), status.HTTP_201_CREATED)


# =========================================================
# TICKET — MY TICKETS
# =========================================================
class MyTicketListAPIView(HelpdeskBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        employee = get_user_employee(request.user, organization)
        if employee is None:
            return self.fail("No active employee profile is linked to this user.",
                             http_status=status.HTTP_404_NOT_FOUND)
        view = str(request.data.get("view") or "raised").lower()
        qs = Ticket.objects.filter(organization=organization, is_active=True).select_related(*TICKET_RELATED)
        qs = qs.filter(assigned_to=employee) if view == "assigned" else qs.filter(raised_by=employee)
        value = request.data.get("status")
        if value:
            qs = qs.filter(status=str(value).upper())
        return self.ok("Tickets fetched.", TicketListSerializer(qs.order_by("-created_at"), many=True).data)


# =========================================================
# TICKET — LIST (handling side)
# =========================================================
class TicketListAPIView(HelpdeskBaseAPIView):
    required_perms = ("ticket.manage", "ticket.handle")

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        employee = get_user_employee(request.user, organization)
        data = request.data
        qs = staff_queryset(request, organization, employee).select_related(*TICKET_RELATED)

        search = (data.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(ticket_code__icontains=search) | Q(subject__icontains=search)
                | Q(raised_by__first_name__icontains=search) | Q(raised_by__last_name__icontains=search)
                | Q(raised_by__employee_code__icontains=search)
            )
        summary_qs = qs

        for key, field in (("status", "status"), ("priority", "priority")):
            value = data.get(key)
            if value:
                qs = qs.filter(**{field: str(value).upper()})
        if data.get("category_id"):
            qs = qs.filter(category_id=data.get("category_id"))
        if data.get("assigned_to_id"):
            qs = qs.filter(assigned_to_id=data.get("assigned_to_id"))
        if self.parse_bool(data.get("assigned_to_me")) and employee is not None:
            qs = qs.filter(assigned_to=employee)
        if self.parse_bool(data.get("unassigned")):
            qs = qs.filter(assigned_to__isnull=True)
        if self.parse_bool(data.get("open_only")):
            qs = qs.exclude(status__in=("RESOLVED", "CLOSED"))
        for key in ("from_date", "to_date"):
            if not data.get(key):
                continue
            try:
                day = parse_date(str(data.get(key)))
            except ValueError:
                day = None
            if day is None:
                return self.fail(f"{key} must use YYYY-MM-DD format.")
            if key == "from_date":
                qs = qs.filter(created_at__gte=timezone.make_aware(datetime.combine(day, time.min)))
            else:
                qs = qs.filter(created_at__lt=timezone.make_aware(
                    datetime.combine(day + timedelta(days=1), time.min)))

        by_status = {code: 0 for code, _label in Ticket.STATUS_CHOICES}
        for row in summary_qs.values("status").annotate(n=Count("id")):
            by_status[row["status"]] = row["n"]
        summary = {
            "total": sum(by_status.values()),
            "by_status": by_status,
            "unassigned_open": summary_qs.filter(assigned_to__isnull=True).exclude(
                status__in=("RESOLVED", "CLOSED")).count(),
        }
        body = {
            "status": True,
            "message": "Tickets fetched.",
            "data": TicketListSerializer(qs.order_by("-created_at"), many=True).data,
            "summary": summary,
        }
        return Response(body, status=status.HTTP_200_OK)


# =========================================================
# TICKET — DETAIL
# =========================================================
class TicketDetailAPIView(HelpdeskBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        ticket, roles, err = self.get_ticket(request, organization)
        if err:
            return err
        return self.ok("Ticket fetched.", self.detail_data(ticket, roles))


# =========================================================
# TICKET — ASSIGN
# =========================================================
class TicketAssignAPIView(HelpdeskBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        ticket, roles, err = self.get_ticket(request, organization)
        if err:
            return err
        if not allowed(ticket, roles)["assign"]:
            return self.fail("You cannot assign this ticket.", http_status=status.HTTP_403_FORBIDDEN)

        assignee, err = self.find_employee(organization, request.data.get("assignee_id"), "assignee_id")
        if err:
            return err
        if assignee is not None and "MANAGER" not in roles:
            me = get_user_employee(request.user, organization)
            same_team = (
                ticket.category.department_id
                and assignee.department_ref_id == ticket.category.department_id
            )
            if not (same_team or (me and assignee.id == me.id)):
                return self.fail("Validation failed.",
                                 {"assignee_id": ["Choose someone from the category's department."]})

        assign_ticket(ticket, assignee, request.user)
        log_activity(
            request=request, action="UPDATE", module="HELPDESK", object_type="Ticket",
            object_id=ticket.id, description=f"Ticket {ticket.ticket_code} assigned.",
            new_data={"assigned_to_id": assignee.id if assignee else None},
        )
        ticket = Ticket.objects.select_related(*TICKET_RELATED).get(pk=ticket.pk)
        roles = ticket_roles(request, organization, ticket)
        if not roles:
            return self.ok("Ticket assigned.", {"ticket": TicketListSerializer(ticket).data})
        return self.ok("Ticket assigned.", self.detail_data(ticket, roles))


# =========================================================
# TICKET — UPDATE (priority / category)
# =========================================================
class TicketUpdateAPIView(HelpdeskBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        ticket, roles, err = self.get_ticket(request, organization)
        if err:
            return err
        if not allowed(ticket, roles)["update"]:
            return self.fail("You cannot update this ticket.", http_status=status.HTTP_403_FORBIDDEN)

        data = request.data
        old = {"priority": ticket.priority, "category_id": ticket.category_id}
        changes = []
        if data.get("priority"):
            value = str(data.get("priority")).upper()
            if value not in dict(Ticket.PRIORITY_CHOICES):
                return self.fail("Validation failed.", {"priority": ["Invalid priority."]})
            if value != ticket.priority:
                changes.append(f"Priority changed from {ticket.get_priority_display()} to "
                               f"{dict(Ticket.PRIORITY_CHOICES)[value]}.")
                ticket.priority = value
        if data.get("category_id"):
            category = self.find_category(organization, data.get("category_id"))
            if category is None:
                return self.fail("Validation failed.", {"category_id": ["Active category not found."]})
            if category.id != ticket.category_id:
                changes.append(f"Category changed from {ticket.category.name} to {category.name}.")
                ticket.category = category
        if not changes:
            return self.ok("Nothing to update.", self.detail_data(ticket, roles))

        ticket.save(update_fields=["priority", "category", "updated_at"])
        TicketComment.objects.create(ticket=ticket, author=request.user, message=" ".join(changes), is_system=True)
        log_activity(
            request=request, action="UPDATE", module="HELPDESK", object_type="Ticket",
            object_id=ticket.id, description=f"Ticket {ticket.ticket_code} updated.",
            old_data=old, new_data={"priority": ticket.priority, "category_id": ticket.category_id},
        )
        ticket = Ticket.objects.select_related(*TICKET_RELATED).get(pk=ticket.pk)
        roles = ticket_roles(request, organization, ticket)
        if not roles:
            return self.ok("Ticket updated.", {"ticket": TicketListSerializer(ticket).data})
        return self.ok("Ticket updated.", self.detail_data(ticket, roles))


# =========================================================
# TICKET — STATUS UPDATE
# =========================================================
class TicketStatusUpdateAPIView(HelpdeskBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        ticket, roles, err = self.get_ticket(request, organization)
        if err:
            return err
        old_status = ticket.status
        note = (request.data.get("note") or "").strip() or None
        try:
            change_status(ticket, request.data.get("status"), roles, request.user, note)
        except HelpdeskError as exc:
            return self.handle_helpdesk_error(exc)
        log_activity(
            request=request, action="UPDATE", module="HELPDESK", object_type="Ticket",
            object_id=ticket.id, description=f"Ticket {ticket.ticket_code} status changed.",
            old_data={"status": old_status}, new_data={"status": ticket.status},
        )
        ticket = Ticket.objects.select_related(*TICKET_RELATED).get(pk=ticket.pk)
        return self.ok("Ticket status updated.", self.detail_data(ticket, roles))


# =========================================================
# TICKET — COMMENT
# =========================================================
class TicketCommentAPIView(HelpdeskBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        ticket, roles, err = self.get_ticket(request, organization)
        if err:
            return err
        message = (request.data.get("message") or "").strip()
        if not message:
            return self.fail("Validation failed.", {"message": ["This field is required."]})
        try:
            add_comment(
                ticket, roles, request.user, message,
                is_internal=self.parse_bool(request.data.get("is_internal")) is True,
                attachment=self.upload(request),
            )
        except HelpdeskError as exc:
            return self.handle_helpdesk_error(exc)
        ticket = Ticket.objects.select_related(*TICKET_RELATED).get(pk=ticket.pk)
        return self.ok("Comment added.", self.detail_data(ticket, roles), status.HTTP_201_CREATED)
