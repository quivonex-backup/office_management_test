
from decimal import Decimal
from io import BytesIO
import logging

from django.template.loader import render_to_string
from django.http import HttpResponse
from django.utils.text import slugify
from rest_framework import status

from xhtml2pdf import pisa

from common.branding import (
    get_organization_branding,
    load_organization_logo,
)

from ..models import PayrollSettings

logger = logging.getLogger(__name__)


ONES = [
    "", "One", "Two", "Three", "Four", "Five",
    "Six", "Seven", "Eight", "Nine",
]

TEENS = [
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen",
    "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen",
]

TENS = [
    "", "", "Twenty", "Thirty", "Forty",
    "Fifty", "Sixty", "Seventy", "Eighty", "Ninety",
]



def format_minutes(minutes):
    """80 -> "1 h 20 min", 45 -> "45 min", 0 -> "0 min"."""
    minutes = int(minutes or 0)
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    if hours:
        return f"{hours} h"
    return f"{rest} min"

def _two_digit_words(number):
    if number < 10:
        return ONES[number]

    if number < 20:
        return TEENS[number - 10]

    return TENS[number // 10] + (
        " " + ONES[number % 10] if number % 10 else ""
    )


def _three_digit_words(number):
    parts = []

    if number >= 100:
        parts.append(ONES[number // 100] + " Hundred")
        number %= 100

    if number:
        parts.append(_two_digit_words(number))

    return " ".join(parts)


def amount_to_words(amount):
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))

    rupees = int(amount)
    paise = int((amount - Decimal(rupees)) * 100)

    if rupees == 0:
        words = "Zero"
    else:
        parts = []

        crore = rupees // 10000000
        rupees %= 10000000

        lakh = rupees // 100000
        rupees %= 100000

        thousand = rupees // 1000
        rupees %= 1000

        if crore:
            parts.append(_three_digit_words(crore) + " Crore")

        if lakh:
            parts.append(_three_digit_words(lakh) + " Lakh")

        if thousand:
            parts.append(_three_digit_words(thousand) + " Thousand")

        if rupees:
            parts.append(_three_digit_words(rupees))

        words = " ".join(parts)

    result = f"Rupees {words}"

    if paise:
        result += f" and {_two_digit_words(paise)} Paise"

    return result + " Only"


def format_amount(value):
    value = Decimal(str(value or 0))
    return f"{value:,.2f}"


def generate_payslip_pdf(payroll_record):
    employee = payroll_record.employee
    organization = payroll_record.organization
    payroll_run = payroll_record.payroll_run

    payroll_settings = PayrollSettings.objects.filter(
        organization=organization,
    ).first()

    payslip_mode = (
        payroll_settings.payslip_mode
        if payroll_settings
        else "FULL"
    )

    branding = get_organization_branding(organization)

    logo_base64, logo_filename, logo_mime = (
        load_organization_logo(
            organization,
            as_base64=True,
        )
    )

    logo_data_uri = None

    if logo_base64 and logo_mime:
        logo_data_uri = (
            f"data:{logo_mime};base64,{logo_base64}"
        )

    employee_name = " ".join(
        part for part in [
            employee.first_name,
            employee.middle_name,
            employee.last_name,
        ]
        if part
    )

    line_items = list(
        payroll_record.line_items.all()
    )

    earnings = []
    deductions = []
    lop_items = []

    # Every line is shown in both modes (SIMPLE has one "Gross Salary" earning
    # plus overtime / LOP / late / manual deductions; FULL has each component
    # and the statutory lines).
    for item in line_items:
        item_data = {
            "name": item.component_name,
            "code": item.component_code,
            "amount": format_amount(item.amount),
        }

        if item.component_type == "EARNING":
            earnings.append(item_data)

        elif item.component_type == "DEDUCTION":
            deductions.append(item_data)

        elif item.component_type == "LOP":
            lop_items.append(item_data)

    employer_contributions = []

    if payslip_mode == "FULL":
        statutory_fields = [
            ("PF Employer Contribution", payroll_record.pf_employer),
            ("EPS", payroll_record.eps),
            ("EDLI", payroll_record.edli),
            ("ESI Employer Contribution", payroll_record.esi_employer),
            ("LWF Employer Contribution", payroll_record.lwf_employer),
        ]

        for name, amount in statutory_fields:
            if amount:
                employer_contributions.append({
                    "name": name,
                    "amount": format_amount(amount),
                })

    payments = []

    for payment in payroll_record.payments.all():
        payments.append({
            "date": payment.payment_date,
            "amount": format_amount(payment.amount),
            "mode": payment.get_payment_mode_display(),
            "reference": payment.transaction_reference or "-",
        })

    context = {
        **branding,

        "logo_data_uri": logo_data_uri,

        "employee": employee,
        "employee_name": employee_name,

        "payroll_record": payroll_record,
        "payroll_run": payroll_run,

        "payroll_month": payroll_run.period_start.strftime(
            "%B %Y"
        ),

        "period_start": payroll_run.period_start,
        "period_end": payroll_run.period_end,

        "payslip_mode": payslip_mode,

        "earnings": earnings,
        "deductions": deductions,
        "lop_items": lop_items,

        "employer_contributions": employer_contributions,
        "payments": payments,

        "attendance": {
            "present_days": payroll_record.present_days,
            "half_days": payroll_record.half_days,
            "absent_days": payroll_record.absent_days,
            "paid_leave_days": payroll_record.paid_leave_days,
            "unpaid_leave_days": payroll_record.unpaid_leave_days,
            "holiday_days": payroll_record.holiday_days,
            "weekly_off_days": payroll_record.weekly_off_days,
            "overtime_hours": payroll_record.overtime_hours,
            "late_minutes": getattr(payroll_record, "late_minutes", 0) or 0,
            "late_time": format_minutes(getattr(payroll_record, "late_minutes", 0) or 0),
        },

        "monthly_salary": format_amount(
            payroll_record.monthly_salary
        ),

        "gross_earnings": format_amount(
            payroll_record.gross_earnings
        ),

        "total_deductions": format_amount(
            payroll_record.total_deductions
        ),

        "net_salary": format_amount(
            payroll_record.net
        ),

        "paid_amount": format_amount(
            payroll_record.paid_amount
        ),

        "remaining_amount": format_amount(
            payroll_record.net - payroll_record.paid_amount
        ),

        "net_salary_words": amount_to_words(
            payroll_record.net
        ),

        "payment_status": payroll_record.get_payment_status_display(),

        "currency": (
            payroll_settings.currency
            if payroll_settings
            else "INR"
        ),
    }

    html = render_to_string(
        "payslip.html",
        context,
    )

    pdf_buffer = BytesIO()

    pdf_status = pisa.CreatePDF(
        html,
        dest=pdf_buffer,
        encoding="utf-8",
    )

    if pdf_status.err:
        raise RuntimeError("Unable to generate payslip PDF.")

    return pdf_buffer.getvalue()


def download_payslip_response(view, payroll_record):
    try:
        pdf_bytes = generate_payslip_pdf(payroll_record)
    except Exception:
        logger.exception(
            "Payslip PDF generation failed for payroll record %s.",
            payroll_record.id,
        )
        return view.failure(
            "Unable to generate payslip PDF.",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    employee = payroll_record.employee
    employee_name = " ".join(
        part for part in [
            employee.first_name,
            employee.middle_name,
            employee.last_name,
        ]
        if part
    )

    payroll_month = payroll_record.payroll_run.period_start.strftime("%B_%Y")
    filename = (
        f"{slugify(employee_name) or 'employee'}_"
        f"{payroll_month}_Payslip.pdf"
    )

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = len(pdf_bytes)

    return response
