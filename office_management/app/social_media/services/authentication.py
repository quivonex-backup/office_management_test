from django.contrib.auth import get_user_model
from django.core import signing

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

META_OAUTH_STATE_SALT = "meta-oauth-state"
META_OAUTH_STATE_MAX_AGE = 600  # 10 minutes


class MetaOAuthAuthentication(BaseAuthentication):
    """
    Authenticate the Meta OAuth callback using the signed OAuth state.

    The callback is opened directly by the browser after Meta redirects
    the user back to Django, so the application's normal JWT token is
    not available on this request.

    The signed state contains the Django user ID and is cryptographically
    signed by Django so that the user ID cannot be tampered with.
    """

    def authenticate(self, request):
        state = request.GET.get("state")
        if not state:
            raise AuthenticationFailed("OAuth state is missing.")

        # Verify the signed state
        try:
            user_id = signing.loads(
                state,
                salt=META_OAUTH_STATE_SALT,
                max_age=META_OAUTH_STATE_MAX_AGE,
            )
        except signing.SignatureExpired:
            raise AuthenticationFailed("OAuth state has expired.")
        except signing.BadSignature:
            raise AuthenticationFailed("Invalid OAuth state.")

        # Get the Django user
        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            raise AuthenticationFailed("OAuth user not found.")

        return (user, None)

    def authenticate_header(self, request):
        return "Meta-OAuth"