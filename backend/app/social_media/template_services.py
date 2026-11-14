from django.shortcuts import render


def render_meta_callback_success(
    request,
    message="Meta account connected successfully.",
):
    """
    Render the successful Meta OAuth callback page.
    """

    return render(
        request,
        "meta_callback.html",
        {
            "success": True,
            "title": "Meta Account Connected",
            "message": message,
        },
    )


def render_meta_callback_error(
    request,
    message="Failed to connect Meta account.",
):
    """
    Render the failed Meta OAuth callback page.
    """

    return render(
        request,
        "meta_callback.html",
        {
            "success": False,
            "title": "Meta Connection Failed",
            "message": message,
        },
        status=400,
    )