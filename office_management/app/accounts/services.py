from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def is_super_admin(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.is_superuser
    )


def send_user_registration_email(user, plain_password):
    """
    Send account credentials to a newly registered user.

    Important:
    plain_password is used only for sending the email.
    It is never stored in the database.
    """

    site_url = settings.FRONTEND_URL

    context = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "email": user.email,
        "password": plain_password,
        "site_url": site_url,
    }

    html_content = render_to_string(
        "user_registration.html",
        context
    )

    text_content = f"""
Hello {user.first_name or user.username},

Your Project Management ERP account has been created successfully.

Login Details:

Email: {user.email}
Username: {user.username}
Password: {plain_password}

Login URL:
{site_url}

Please keep your credentials secure.

Regards,
Project Management ERP Team
"""

    email = EmailMultiAlternatives(
        subject="Your Project Management ERP Account",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )

    email.attach_alternative(
        html_content,
        "text/html"
    )

    email.send(fail_silently=False)