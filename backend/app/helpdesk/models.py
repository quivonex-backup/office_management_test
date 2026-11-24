"""
Helpdesk: employees raise tickets, the handling team answers them.

  TicketCategory  per organization (IT, HR, Payroll, Facilities ...). The
                  department handles its tickets; default_assignee (optional)
                  gets every new ticket of the category.
  Ticket          status OPEN -> IN_PROGRESS -> ON_HOLD -> RESOLVED -> CLOSED
                  (RESOLVED can be reopened; CLOSED is final).
  TicketComment   replies, internal notes (hidden from the person who raised
                  the ticket) and system lines (status / assignee changes).
"""
from django.conf import settings
from django.db import models


class TicketCategory(models.Model):
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="ticket_categories")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    department = models.ForeignKey(
        "employees.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="ticket_categories",
    )
    default_assignee = models.ForeignKey(
        "employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ticket_categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Ticket(models.Model):

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In progress"),
        ("ON_HOLD", "On hold"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    ]
    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="tickets")
    ticket_code = models.CharField(max_length=30, unique=True, db_index=True)
    category = models.ForeignKey(TicketCategory, on_delete=models.PROTECT, related_name="tickets")
    raised_by = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="raised_tickets")
    assigned_to = models.ForeignKey(
        "employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets",
    )
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="MEDIUM", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN", db_index=True)
    attachment = models.FileField(upload_to="helpdesk/attachments/", null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tickets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ticket_code} - {self.subject}"


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    message = models.TextField()
    attachment = models.FileField(upload_to="helpdesk/attachments/", null=True, blank=True)
    is_internal = models.BooleanField(default=False)   # handlers only
    is_system = models.BooleanField(default=False)     # status / assignee change line
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_comments"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.ticket.ticket_code} - comment {self.id}"
