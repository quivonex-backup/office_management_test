# common/branding.py
import base64
from pathlib import Path

from django.conf import settings


def get_organization_branding(organization):
    """
    Resolve branding for an organization with fallbacks to settings defaults.

    Returns a dict:
        company_name, company_address, company_email,
        company_phone, company_gst, company_website,
        logo_field  (FieldFile or None)
    """
    if organization is None:
        return {
            "company_name": getattr(settings, "COMPANY_NAME", ""),
            "company_address": getattr(settings, "COMPANY_ADDRESS", ""),
            "company_email": getattr(settings, "COMPANY_EMAIL", settings.DEFAULT_FROM_EMAIL),
            "company_phone": getattr(settings, "COMPANY_PHONE", ""),
            "company_gst": getattr(settings, "COMPANY_GST", ""),
            "company_website": "",
            "logo_field": None,
        }

    address_parts = [
        getattr(organization, "address_line_1", None),
        getattr(organization, "address_line_2", None),
        getattr(organization, "city", None),
        getattr(organization, "district", None),
        getattr(organization, "state", None),
    ]
    address_parts = [p for p in address_parts if p]
    address = ", ".join(address_parts)
    pincode = getattr(organization, "pincode", None)
    if pincode:
        address = f"{address} - {pincode}" if address else str(pincode)

    return {
        "company_name": organization.organization_name or getattr(settings, "COMPANY_NAME", ""),
        "company_address": address or getattr(settings, "COMPANY_ADDRESS", ""),
        "company_email": getattr(organization, "email", None)
                         or getattr(settings, "COMPANY_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "company_phone": getattr(organization, "phone_number", None)
                         or getattr(settings, "COMPANY_PHONE", ""),
        "company_gst": getattr(organization, "gst_number", None)
                       or getattr(settings, "COMPANY_GST", ""),
        "company_website": getattr(organization, "website", None) or "",
        "logo_field": getattr(organization, "logo", None),
    }


def load_organization_logo(organization, as_base64=False):
    """
    Load the organization's logo bytes.

    Returns (data, filename, mime_type).
    - data is bytes, or base64 str when as_base64=True
    - returns (None, None, None) if no logo / read fails
    """
    logo_field = getattr(organization, "logo", None)
    if not logo_field:
        return None, None, None

    try:
        with logo_field.open("rb") as f:
            raw = f.read()
    except Exception:
        return None, None, None

    filename = Path(logo_field.name).name
    suffix = Path(filename).suffix.lstrip(".").lower() or "png"
    if suffix in ("jpg", "jpeg"):
        mime = "image/jpeg"
    elif suffix == "svg":
        mime = "image/svg+xml"
    else:
        mime = f"image/{suffix}"

    if as_base64:
        return base64.b64encode(raw).decode("utf-8"), filename, mime

    return raw, filename, mime