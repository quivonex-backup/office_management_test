from decimal import Decimal
from pathlib import Path
import base64

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Sum
from email.mime.image import MIMEImage

from weasyprint import HTML

from .models import ProjectPayment, ProjectPaymentTransaction


# =========================================================
# GENERATE PROJECT PAYMENT EMAIL
# =========================================================
def send_project_payment_reminder_emails(projects, include_transaction_history=False):
    """
    Send payment reminder emails grouped by client.
    Returns summary dict with totals and per-client results.
    """
    today = timezone.localdate()

    # Group projects by client
    clients_projects = {}
    for project in projects:
        client = project.client
        if client.id not in clients_projects:
            clients_projects[client.id] = {"client": client, "projects": []}
        clients_projects[client.id]["projects"].append(project)

    # Overall tracking
    total_clients = 0
    total_emails_sent = 0
    total_projects = 0
    successful_clients = []
    failed_clients = []
    overall_total_amount = Decimal("0.00")
    overall_total_paid = Decimal("0.00")
    overall_total_outstanding = Decimal("0.00")
    overall_total_overdue = Decimal("0.00")

    # Process each client
    for client_data in clients_projects.values():
        client = client_data["client"]
        client_projects = client_data["projects"]
        total_clients += 1

        if not client.email:
            failed_clients.append({
                "client_id": client.id,
                "client_name": client.client_name,
                "email": None,
                "reason": "Client does not have an email address.",
                "project_ids": [p.id for p in client_projects],
            })
            continue

        project_data = []
        client_total_amount = Decimal("0.00")
        client_total_paid = Decimal("0.00")
        client_total_outstanding = Decimal("0.00")
        client_total_overdue = Decimal("0.00")
        client_total_transaction_amount = Decimal("0.00")

        for project in client_projects:
            payments = (
                ProjectPayment.objects
                .filter(project=project, is_active=True)
                .exclude(status="CANCELLED")
                .prefetch_related("transactions")
                .order_by("payment_type", "installment_number", "due_date", "created_at")
            )

            payment_rows = []
            project_total_amount = Decimal("0.00")
            project_total_paid = Decimal("0.00")
            project_total_outstanding = Decimal("0.00")
            project_total_overdue = Decimal("0.00")

            for payment in payments:
                amount = payment.amount or Decimal("0.00")
                paid_amount = payment.paid_amount or Decimal("0.00")
                outstanding_amount = max(amount - paid_amount, Decimal("0.00"))

                # Payment title
                if payment.title:
                    payment_title = payment.title
                elif payment.payment_type == "ADVANCE":
                    payment_title = "Advance"
                else:
                    payment_title = "Installment {}".format(payment.installment_number)

                # Display status
                if outstanding_amount <= Decimal("0.00"):
                    display_status = "Paid"
                elif payment.due_date and payment.due_date < today:
                    display_status = "Overdue"
                elif paid_amount > Decimal("0.00"):
                    display_status = "Partially Paid"
                else:
                    display_status = "Pending"

                overdue_amount = (
                    outstanding_amount
                    if (payment.due_date and payment.due_date < today and outstanding_amount > Decimal("0.00"))
                    else Decimal("0.00")
                )

                # Transaction history
                transaction_rows = []
                if include_transaction_history:
                    transactions = (
                        ProjectPaymentTransaction.objects
                        .filter(payment=payment, status="SUCCESS")
                        .order_by("transaction_date", "created_at")
                    )
                    for txn in transactions:
                        if txn.payment_method == "CASH":
                            ref = txn.reference_number or "-"
                        elif txn.payment_method == "UPI":
                            ref = txn.utr_number or "-"
                        elif txn.payment_method == "BANK_TRANSFER":
                            ref = txn.utr_number or "-"
                        elif txn.payment_method == "CHEQUE":
                            ref = txn.cheque_number or "-"
                        elif txn.payment_method in ["CARD", "ONLINE"]:
                            ref = txn.gateway_transaction_id or "-"
                        elif txn.payment_method == "OTHER":
                            ref = txn.reference_number or "-"
                        else:
                            ref = "-"
                        txn_amount = txn.amount or Decimal("0.00")
                        transaction_rows.append({
                            "date": txn.transaction_date,
                            "payment_for": payment_title,
                            "payment_method": txn.get_payment_method_display(),
                            "amount": txn_amount,
                            "reference_number": ref,
                        })
                        client_total_transaction_amount += txn_amount

                payment_rows.append({
                    "id": payment.id,
                    "payment_type": payment.payment_type,
                    "title": payment_title,
                    "installment_number": payment.installment_number,
                    "due_date": payment.due_date,
                    "amount": amount,
                    "paid_amount": paid_amount,
                    "outstanding_amount": outstanding_amount,
                    "overdue_amount": overdue_amount,
                    "status": display_status,
                    "transactions": transaction_rows,
                })

                project_total_amount += amount
                project_total_paid += paid_amount
                project_total_outstanding += outstanding_amount
                project_total_overdue += overdue_amount

            if not payment_rows:
                continue

            project_data.append({
                "id": project.id,
                "project_name": project.project_name,
                "project_type": project.project_type,
                "start_date": project.start_date,
                "end_date": project.end_date,
                "deadline": project.deadline,
                "total_amount": project_total_amount,
                "paid_amount": project_total_paid,
                "outstanding_amount": project_total_outstanding,
                "overdue_amount": project_total_overdue,
                "payments": payment_rows,
            })

            client_total_amount += project_total_amount
            client_total_paid += project_total_paid
            client_total_outstanding += project_total_outstanding
            client_total_overdue += project_total_overdue

        if not project_data:
            failed_clients.append({
                "client_id": client.id,
                "client_name": client.client_name,
                "email": client.email,
                "reason": "No active payment plans found for the selected projects.",
                "project_ids": [p.id for p in client_projects],
            })
            continue

        # Build email
        context = {
            "client": client,
            "projects": project_data,
            "summary": {
                "total_projects": len(project_data),
                "total_amount": client_total_amount,
                "total_paid": client_total_paid,
                "total_outstanding": client_total_outstanding,
                "total_overdue": client_total_overdue,
                "total_transaction_amount": client_total_transaction_amount,
            },
            "include_transaction_history": include_transaction_history,
            "today": today,
            "company_name": getattr(settings, "COMPANY_NAME", "Quivonex Solutions"),
            "company_email": settings.DEFAULT_FROM_EMAIL,
            "company_phone": getattr(settings, "COMPANY_PHONE", ""),
        }

        html_content = render_to_string("project_payment_reminder.html", context)

        greeting = client.client_name or client.company_name or "Client"
        text_content = """
Dear {greeting},

This is a friendly reminder regarding the payment status of your project(s).

Total Amount: ₹{total_amount:,.2f}
Total Paid: ₹{total_paid:,.2f}
Total Outstanding: ₹{total_outstanding:,.2f}
Total Overdue: ₹{total_overdue:,.2f}

Please find the detailed payment schedule in this email.

We kindly request you to arrange the pending payment(s) as per the agreed payment schedule.

If you have already made any pending payment, please disregard this reminder or share the payment details with us for confirmation.

Regards,
{company_name}
""".format(
            greeting=greeting,
            total_amount=client_total_amount,
            total_paid=client_total_paid,
            total_outstanding=client_total_outstanding,
            total_overdue=client_total_overdue,
            company_name=context["company_name"],
        )

        subject = (
            "Payment Reminder - {}".format(project_data[0]['project_name'])
            if len(project_data) == 1
            else "Payment Reminder - Pending Project Payments"
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[client.email],
        )
        email.attach_alternative(html_content, "text/html")

        # Attach company logo as inline CID using MIMEImage
        logo_path = Path(settings.MEDIA_ROOT) / "assets" / "quivonex_solutions.png"
        if logo_path.exists():
            with open(logo_path, "rb") as logo_file:
                logo_data = logo_file.read()
            logo = MIMEImage(logo_data, _subtype="png")
            logo.add_header("Content-ID", "<company_logo>")
            logo.add_header("Content-Disposition", "inline", filename="quivonex_solutions.png")
            email.attach(logo)

        try:
            email.send(fail_silently=False)
            total_emails_sent += 1
            successful_clients.append({
                "client_id": client.id,
                "client_name": client.client_name,
                "email": client.email,
                "project_ids": [p["id"] for p in project_data],
                "total_projects": len(project_data),
                "total_amount": client_total_amount,
                "total_paid": client_total_paid,
                "total_outstanding": client_total_outstanding,
                "total_overdue": client_total_overdue,
            })
            total_projects += len(project_data)
            overall_total_amount += client_total_amount
            overall_total_paid += client_total_paid
            overall_total_outstanding += client_total_outstanding
            overall_total_overdue += client_total_overdue
        except Exception as exc:
            failed_clients.append({
                "client_id": client.id,
                "client_name": client.client_name,
                "email": client.email,
                "reason": str(exc),
                "project_ids": [p["id"] for p in project_data],
            })

    return {
        "total_clients": total_clients,
        "total_emails_sent": total_emails_sent,
        "total_projects": total_projects,
        "successful_clients": successful_clients,
        "failed_clients": failed_clients,
        "total_amount": overall_total_amount,
        "total_paid": overall_total_paid,
        "total_outstanding": overall_total_outstanding,
        "total_overdue": overall_total_overdue,
        "include_transaction_history": include_transaction_history,
    }


# =========================================================
# GENERATE PROJECT INVOICE PDF
# =========================================================
def generate_project_invoice_pdf(project):
    """
    Generate a PDF invoice for a project (any status: Pending, Partially Paid, Paid, Overdue).
    Invoice number derived from project_code: PR-260823-73914 -> INV-260823-73914.
    Returns (pdf_file, invoice_number).
    """
    client = project.client
    # invoice_number = project.project_code.replace("PR-", "INV-", 1)
    invoice_number = project.project_code.replace("PR-", "PR-", 1)
    invoice_date = timezone.localdate()

    payments = list(
        ProjectPayment.objects
        .filter(project=project, is_active=True)
        .exclude(status="CANCELLED")
        .order_by("payment_type", "installment_number", "due_date", "created_at")
    )

    transactions = list(
        ProjectPaymentTransaction.objects
        .filter(payment__project=project, payment__is_active=True, status="SUCCESS")
        .select_related("payment")
        .order_by("transaction_date", "created_at")
    )

    total_paid = (
        ProjectPaymentTransaction.objects
        .filter(payment__project=project, payment__is_active=True, status="SUCCESS")
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    project_total = project.total_cost or Decimal("0.00")
    outstanding_amount = max(project_total - total_paid, Decimal("0.00"))

    # Payment status
    if project_total > Decimal("0.00") and total_paid >= project_total:
        payment_status = "PAID"
    elif total_paid > Decimal("0.00"):
        payment_status = "PARTIALLY PAID"
    else:
        payment_status = "PENDING"

    payment_notes = "\n".join([p.notes for p in payments if p.notes])

    # Load company logo as base64
    logo_path = Path(settings.MEDIA_ROOT) / "assets" / "quivonex_solutions.png"
    logo_data = None
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_data = base64.b64encode(f.read()).decode("utf-8")

    company_name = getattr(settings, "COMPANY_NAME", "Quivonex Solutions")
    company_address = getattr(settings, "COMPANY_ADDRESS", "")
    company_email = getattr(settings, "COMPANY_EMAIL", settings.DEFAULT_FROM_EMAIL)
    company_phone = getattr(settings, "COMPANY_PHONE", "")
    company_gst = getattr(settings, "COMPANY_GST", "")

    context = {
        "project": project,
        "client": client,
        "payments": payments,
        "transactions": transactions,
        "project_total": project_total,
        "total_paid": total_paid,
        "outstanding_amount": outstanding_amount,
        "payment_status": payment_status,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "payment_notes": payment_notes,
        "logo_data": logo_data,
        "company_name": company_name,
        "company_address": company_address,
        "company_email": company_email,
        "company_phone": company_phone,
        "company_gst": company_gst,
        "generated_at": timezone.localtime().strftime("%d-%m-%Y %I:%M %p"),
    }

    html_string = render_to_string("project_invoice.html", context)
    pdf_file = HTML(string=html_string).write_pdf()
    return pdf_file, invoice_number