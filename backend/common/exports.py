"""
Excel export shared by the reports app and list APIs (format "xlsx").

xlsx_response(report, organization) takes the report shape:
  {"report": key, "title": str, "filters": {...}, "columns": [{key, label, type}],
   "rows": [{...}], "totals": {...}?}
and returns an HttpResponse attachment (title, filters, generated time,
styled header with filter, frozen header, totals row, money format).
"""
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone


def xlsx_response(report, organization):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = (report["report"] or "Report")[:31]
    columns = report["columns"]
    width = max(len(columns), 1)

    ws.cell(row=1, column=1, value=f"{organization.organization_name} - {report['title']}").font = Font(bold=True, size=13)
    filter_text = ", ".join(f"{k}: {v}" for k, v in (report.get("filters") or {}).items() if v not in (None, "", []))
    ws.cell(row=2, column=1, value=f"Filters: {filter_text or 'none'}").font = Font(italic=True, size=9)
    ws.cell(row=3, column=1, value=f"Generated: {timezone.localtime().strftime('%d %b %Y %H:%M')}").font = Font(size=9)

    header_row = 5
    fill = PatternFill("solid", fgColor="1F3A5F")
    for i, c in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=i, value=c["label"])
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    r = header_row
    for row in report["rows"]:
        r += 1
        for i, c in enumerate(columns, start=1):
            value = row.get(c["key"])
            if isinstance(value, bool):
                value = "Yes" if value else "No"
            elif isinstance(value, (list, dict)):
                value = str(value)
            cell = ws.cell(row=r, column=i, value=value)
            if c["type"] == "money":
                cell.number_format = "#,##0.00"

    if report.get("totals"):
        r += 1
        ws.cell(row=r, column=1, value="Total").font = Font(bold=True)
        for i, c in enumerate(columns, start=1):
            if c["key"] in report["totals"] and i > 1:
                cell = ws.cell(row=r, column=i, value=report["totals"][c["key"]])
                cell.font = Font(bold=True)
                if c["type"] == "money":
                    cell.number_format = "#,##0.00"

    for i, c in enumerate(columns, start=1):
        longest = max([len(str(c["label"]))] + [len(str(row.get(c["key"]) or "")) for row in report["rows"][:500]])
        ws.column_dimensions[get_column_letter(i)].width = min(max(longest + 2, 10), 45)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    if width:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(width)}{max(r, header_row)}"

    buffer = BytesIO()
    wb.save(buffer)
    f = report.get("filters") or {}
    suffix = "_".join(str(f.get(k)) for k in ("from_date", "to_date", "period_start", "period_end", "month") if f.get(k)) or timezone.localdate().isoformat()
    filename = f"{report['report']}_{suffix}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
