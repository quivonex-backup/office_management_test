"""
Helpdesk rules: who can see / act on a ticket, status moves, notifications.

Roles on one ticket (a person can have several):
  MANAGER   access role has ticket.manage (or organization owner): every ticket
  HANDLER   access role has ticket.handle and the employee's department is the
            category's department; or the ticket is assigned to them
  RAISER    the employee who raised it
"""
from django.db import transaction
from django.utils import timezone

from common.code_generators import generate_ticket_code
from common.permissions import get_user_employee, has_perm

from .models import Ticket, TicketComment


class HelpdeskError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors


# Status moves for the handling side (manager / handler).
STAFF_MOVES = {
    "OPEN": ("IN_PROGRESS", "ON_HOLD", "RESOLVED", "CLOSED"),
    "IN_PROGRESS": ("ON_HOLD", "RESOLVED", "CLOSED"),
    "ON_HOLD": ("IN_PROGRESS", "RESOLVED", "CLOSED"),
    "RESOLVED": ("IN_PROGRESS", "CLOSED"),
    "CLOSED": (),
}
# The person who raised it: withdraw (close) an open ticket, confirm (close)
# or reopen a resolved one.
RAISER_MOVES = {
    "OPEN": ("CLOSED",),
    "IN_PROGRESS": ("CLOSED",),
    "ON_HOLD": ("CLOSED",),
    "RESOLVED": ("OPEN", "CLOSED"),
    "CLOSED": (),
}


# =========================================================
# ACCESS
# =========================================================
def ticket_roles(request, organization, ticket, employee=None):
    employee = employee if employee is not None else get_user_employee(request.user, organization)
    roles = set()
    if has_perm(request, organization, "ticket.manage"):
        roles.add("MANAGER")
    if employee is not None:
        if ticket.assigned_to_id == employee.id:
            roles.add("HANDLER")
        elif (
            ticket.category.department_id
            and employee.department_ref_id == ticket.category.department_id
            and has_perm(request, organization, "ticket.handle")
        ):
            roles.add("HANDLER")
        if ticket.raised_by_id == employee.id:
            roles.add("RAISER")
    return roles


def is_staff(roles):
    return bool(roles & {"MANAGER", "HANDLER"})


def status_moves(ticket, roles):
    moves = set()
    if is_staff(roles):
        moves.update(STAFF_MOVES.get(ticket.status, ()))
    if "RAISER" in roles:
        moves.update(RAISER_MOVES.get(ticket.status, ()))
    return sorted(moves)


def allowed(ticket, roles):
    staff = is_staff(roles)
    open_ticket = ticket.status != "CLOSED"
    return {
        "status_moves": status_moves(ticket, roles),
        "assign": staff and open_ticket,
        "update": staff and open_ticket,
        "comment": open_ticket and bool(roles),
        "internal_note": staff and open_ticket,
    }


def staff_queryset(request, organization, employee):
    """Tickets on the handling side list (ticket.manage: all; ticket.handle: own department + assigned)."""
    from django.db.models import Q

    qs = Ticket.objects.filter(organization=organization, is_active=True)
    if has_perm(request, organization, "ticket.manage"):
        return qs
    if employee is None:
        return qs.none()
    condition = Q(assigned_to=employee)
    if employee.department_ref_id and has_perm(request, organization, "ticket.handle"):
        condition |= Q(category__department_id=employee.department_ref_id)
    return qs.filter(condition)


# =========================================================
# NOTIFICATIONS
# =========================================================
def _handler_users(ticket):
    """Who hears about a new / unassigned ticket."""
    from app.employees.models import Employee

    org = ticket.organization
    base = Employee.objects.filter(
        organization=org, is_active=True, user__isnull=False, user__is_active=True,
        access_role__is_active=True, access_role__organization=org,
    ).select_related("user")
    users = []
    if ticket.category.department_id:
        users = [e.user for e in base.filter(
            department_ref_id=ticket.category.department_id,
            access_role__permissions__code="ticket.handle").distinct()]
    if not users:
        users = [e.user for e in base.filter(access_role__permissions__code="ticket.manage").distinct()]
    if not users and org.owner_id:
        users = [org.owner]
    return users


def _notify(users, event_code, title, body, ticket, exclude_user=None):
    from app.communications.notification_service import notify

    seen, targets = set(), []
    for user in users:
        if user is None or user.id in seen or (exclude_user is not None and user.id == exclude_user.id):
            continue
        seen.add(user.id)
        targets.append(user)
    if not targets:
        return
    transaction.on_commit(lambda: notify(
        users=targets, event_code=event_code, title=title, body=body,
        reference_type="ticket", reference_id=ticket.id,
    ))


def _assignee_or_handlers(ticket):
    if ticket.assigned_to_id and ticket.assigned_to.user_id:
        return [ticket.assigned_to.user]
    return _handler_users(ticket)


def _system_line(ticket, user, text):
    TicketComment.objects.create(ticket=ticket, author=user, message=text, is_system=True)


# =========================================================
# ACTIONS
# =========================================================
@transaction.atomic
def create_ticket(organization, category, raised_by, subject, description, priority, user, attachment=None):
    assignee = category.default_assignee if (
        category.default_assignee_id and category.default_assignee.is_active
    ) else None
    ticket = Ticket.objects.create(
        organization=organization,
        ticket_code=generate_ticket_code(),
        category=category,
        raised_by=raised_by,
        assigned_to=assignee,
        subject=subject,
        description=description,
        priority=priority or "MEDIUM",
        attachment=attachment,
        created_by=user,
    )
    if assignee is not None:
        _system_line(ticket, None, f"Assigned to {_name(assignee)} (category default).")
    _notify(
        _assignee_or_handlers(ticket), "TICKET_CREATED",
        f"New ticket {ticket.ticket_code}",
        f"{_name(raised_by)}: {subject}", ticket, exclude_user=raised_by.user,
    )
    return ticket


@transaction.atomic
def change_status(ticket, new_status, roles, user, note=None):
    new_status = str(new_status or "").strip().upper()
    if new_status not in dict(Ticket.STATUS_CHOICES):
        raise HelpdeskError("Validation failed.", {"status": ["Invalid status."]})
    if new_status not in status_moves(ticket, roles):
        raise HelpdeskError(f"Cannot change status from {ticket.status} to {new_status}.")

    old = ticket.status
    now = timezone.now()
    ticket.status = new_status
    fields = ["status", "updated_at"]
    if new_status == "RESOLVED":
        ticket.resolved_at = now
        fields.append("resolved_at")
    elif new_status in ("OPEN", "IN_PROGRESS") and old == "RESOLVED":
        ticket.resolved_at = None
        fields.append("resolved_at")
    if new_status == "CLOSED":
        ticket.closed_at = now
        fields.append("closed_at")
    ticket.save(update_fields=fields)

    label = dict(Ticket.STATUS_CHOICES)
    text = f"Status changed from {label[old]} to {label[new_status]}."
    if note:
        text = f"{text} Note: {note}"
    _system_line(ticket, user, text)

    by_raiser = ticket.raised_by.user_id == getattr(user, "id", None)
    if by_raiser:
        _notify(_assignee_or_handlers(ticket), "TICKET_STATUS",
                f"{ticket.ticket_code}: {label[new_status]}",
                f"{_name(ticket.raised_by)} set the ticket to {label[new_status]}.", ticket, exclude_user=user)
    else:
        _notify([ticket.raised_by.user], "TICKET_STATUS",
                f"{ticket.ticket_code}: {label[new_status]}",
                note or f"Your ticket \"{ticket.subject}\" is now {label[new_status]}.", ticket, exclude_user=user)
    return ticket


@transaction.atomic
def assign_ticket(ticket, employee, user):
    if employee is None:
        if ticket.assigned_to_id is None:
            return ticket
        ticket.assigned_to = None
        ticket.save(update_fields=["assigned_to", "updated_at"])
        _system_line(ticket, user, "Assignee removed.")
        return ticket
    if ticket.assigned_to_id == employee.id:
        return ticket
    ticket.assigned_to = employee
    ticket.save(update_fields=["assigned_to", "updated_at"])
    _system_line(ticket, user, f"Assigned to {_name(employee)}.")
    _notify([employee.user], "TICKET_ASSIGNED", f"Ticket {ticket.ticket_code} assigned to you",
            ticket.subject, ticket, exclude_user=user)
    return ticket


@transaction.atomic
def add_comment(ticket, roles, user, message, is_internal=False, attachment=None):
    if ticket.status == "CLOSED":
        raise HelpdeskError("This ticket is closed.")
    if is_internal and not is_staff(roles):
        raise HelpdeskError("Only the handling team can add internal notes.")
    comment = TicketComment.objects.create(
        ticket=ticket, author=user, message=message, is_internal=bool(is_internal), attachment=attachment,
    )
    ticket.save(update_fields=["updated_at"])
    if not is_internal:
        if ticket.raised_by.user_id == user.id:
            targets = _assignee_or_handlers(ticket)
        else:
            targets = [ticket.raised_by.user]
        _notify(targets, "TICKET_REPLY", f"New reply on {ticket.ticket_code}",
                message[:200], ticket, exclude_user=user)
    return comment


def _name(employee):
    return " ".join(p for p in [employee.first_name, employee.last_name] if p) or employee.employee_code
