import requests

from django.conf import settings

from app.social_media.models import SocialAccount


GRAPH_URL = (
    f"https://graph.facebook.com/"
    f"{settings.META_API_VERSION}"
)


# def get_meta_login_url(state):
#     """
#     Generate Meta OAuth login URL.
#     """

#     permissions = [
#         "pages_show_list",
#         "pages_read_engagement",
#         "pages_manage_posts",
#         "instagram_basic",
#         "instagram_content_publish",
#         "business_management",
#     ]

#     params = {
#         "client_id": settings.META_APP_ID,
#         "redirect_uri": settings.META_REDIRECT_URI,
#         "state": state,
#         "scope": ",".join(permissions),
#         "response_type": "code",
#     }

#     response = requests.Request(
#         "GET",
#         "https://www.facebook.com/dialog/oauth",
#         params=params,
#     ).prepare()

#     return response.url

def get_meta_login_url(state):
    """
    Generate Meta Login for Business authorization URL.
    """

    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.META_REDIRECT_URI,
        "state": state,
        "config_id": settings.META_CONFIG_ID,
        "response_type": "code",
    }

    response = requests.Request(
        "GET",
        "https://www.facebook.com/dialog/oauth",
        params=params,
    ).prepare()

    return response.url


def exchange_code_for_token(code):
    """
    Exchange OAuth authorization code
    for a short-lived user access token.
    """

    params = {
        "client_id": settings.META_APP_ID,
        "client_secret": settings.META_APP_SECRET,
        "redirect_uri": settings.META_REDIRECT_URI,
        "code": code,
    }

    response = requests.get(
        f"{GRAPH_URL}/oauth/access_token",
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_long_lived_user_token(short_token):
    """
    Exchange short-lived user token
    for long-lived user token.
    """

    params = {
        "grant_type": "fb_exchange_token",
        "client_id": settings.META_APP_ID,
        "client_secret": settings.META_APP_SECRET,
        "fb_exchange_token": short_token,
    }

    response = requests.get(
        f"{GRAPH_URL}/oauth/access_token",
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_user_pages(access_token):
    """
    Get Facebook Pages available to the connected user.

    Also requests the Instagram business account
    connected to each Facebook Page.
    """

    params = {
        "access_token": access_token,
        "fields": (
            "id,"
            "name,"
            "access_token,"
            "instagram_business_account"
        ),
    }

    response = requests.get(
        f"{GRAPH_URL}/me/accounts",
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json().get("data", [])


def save_social_accounts(user, pages):
    """
    Save Facebook Pages and connected Instagram accounts.
    """

    saved_accounts = []

    for page in pages:

        page_id = page.get("id")
        page_name = page.get(
            "name",
            "Facebook Page",
        )
        page_token = page.get("access_token")

        if not page_id or not page_token:
            continue

        # ---------------------------------------------
        # FACEBOOK
        # ---------------------------------------------

        facebook_account, _ = (
            SocialAccount.objects.update_or_create(
                platform="FACEBOOK",
                account_id=page_id,
                defaults={
                    "account_name": page_name,
                    "access_token": page_token,
                    "page_id": page_id,
                    "instagram_user_id": None,
                    "is_active": True,
                    "created_by": user,
                },
            )
        )

        saved_accounts.append(facebook_account)

        # ---------------------------------------------
        # INSTAGRAM
        # ---------------------------------------------

        instagram = page.get(
            "instagram_business_account"
        )

        if not instagram:
            continue

        instagram_id = instagram.get("id")

        if not instagram_id:
            continue

        instagram_account, _ = (
            SocialAccount.objects.update_or_create(
                platform="INSTAGRAM",
                account_id=instagram_id,
                defaults={
                    "account_name": (
                        f"Instagram - {page_name}"
                    ),
                    "access_token": page_token,
                    "page_id": page_id,
                    "instagram_user_id": instagram_id,
                    "is_active": True,
                    "created_by": user,
                },
            )
        )

        saved_accounts.append(
            instagram_account
        )

    return saved_accounts


def connect_meta_account(user, code):
    """
    Complete Meta account connection.
    """

    # ---------------------------------------------
    # STEP 1: Exchange code
    # ---------------------------------------------

    token_data = exchange_code_for_token(
        code
    )

    short_token = token_data.get(
        "access_token"
    )

    if not short_token:
        raise ValueError(
            "Meta did not return an access token."
        )

    # ---------------------------------------------
    # STEP 2: Long-lived token
    # ---------------------------------------------

    long_token_data = (
        get_long_lived_user_token(
            short_token
        )
    )

    access_token = long_token_data.get(
        "access_token",
        short_token,
    )

    expires_in = long_token_data.get(
        "expires_in"
    )

    # ---------------------------------------------
    # STEP 3: Get Pages
    # ---------------------------------------------

    pages = get_user_pages(
        access_token
    )

    # ---------------------------------------------
    # STEP 4: Save accounts
    # ---------------------------------------------

    accounts = save_social_accounts(
        user=user,
        pages=pages,
    )

    return {
        "accounts": accounts,
        "expires_in": expires_in,
        "pages_found": len(pages),
    }