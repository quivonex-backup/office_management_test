import json

import requests

from django.conf import settings

GRAPH_URL = f"https://graph.facebook.com/{settings.META_API_VERSION}"


def _raise_for_meta_error(response):
    """Convert Meta API errors into useful Python exceptions."""
    if response.ok:
        return

    try:
        data = response.json()
    except ValueError:
        data = {}

    error = data.get("error", {})
    message = error.get(
        "message",
        response.text or "Facebook API request failed.",
    )
    code = error.get("code")

    if code:
        raise RuntimeError(f"Facebook API error ({code}): {message}")

    raise RuntimeError(f"Facebook API error: {message}")


# TEXT POST
def publish_text_to_facebook(page_id, page_access_token, message):
    """Publish a text-only post to a Facebook Page."""
    if not page_id:
        raise ValueError("Facebook Page ID is required.")
    if not page_access_token:
        raise ValueError("Facebook Page access token is required.")
    if not message:
        raise ValueError("Message is required.")

    url = f"{GRAPH_URL}/{page_id}/feed"
    payload = {
        "message": message,
        "access_token": page_access_token,
    }

    response = requests.post(url, data=payload, timeout=60)
    _raise_for_meta_error(response)

    data = response.json()
    return {"post_id": data.get("id"), "raw_response": data}


# SINGLE PHOTO
def publish_photo_to_facebook(page_id, page_access_token, image_url, caption=""):
    """Publish one image to a Facebook Page."""
    if not page_id:
        raise ValueError("Facebook Page ID is required.")
    if not page_access_token:
        raise ValueError("Facebook Page access token is required.")
    if not image_url:
        raise ValueError("Image URL is required.")

    url = f"{GRAPH_URL}/{page_id}/photos"
    payload = {
        "url": image_url,
        "access_token": page_access_token,
    }
    if caption:
        payload["caption"] = caption

    response = requests.post(url, data=payload, timeout=60)
    _raise_for_meta_error(response)

    data = response.json()
    return {
        "post_id": data.get("post_id") or data.get("id"),
        "raw_response": data,
    }


# MULTIPLE PHOTOS
def publish_multiple_photos_to_facebook(
    page_id, page_access_token, image_urls, caption=""
):
    """
    Publish multiple images as one Facebook Page post.

    Each image is first uploaded as an unpublished photo.
    The resulting photo IDs are then attached to one feed post.
    """
    if not page_id:
        raise ValueError("Facebook Page ID is required.")
    if not page_access_token:
        raise ValueError("Facebook Page access token is required.")
    if not image_urls:
        raise ValueError("At least one image URL is required.")

    uploaded_media = []

    # Upload photos as unpublished
    for image_url in image_urls:
        if not image_url:
            continue

        url = f"{GRAPH_URL}/{page_id}/photos"
        payload = {
            "url": image_url,
            "published": "false",
            "access_token": page_access_token,
        }

        response = requests.post(url, data=payload, timeout=60)
        _raise_for_meta_error(response)

        photo_id = response.json().get("id")
        if photo_id:
            uploaded_media.append({"media_fbid": photo_id})

    if not uploaded_media:
        raise ValueError("No Facebook media was uploaded.")

    # Create feed post
    url = f"{GRAPH_URL}/{page_id}/feed"
    payload = {
        "message": caption or "",
        "access_token": page_access_token,
    }

    # Meta expects attached_media[0], attached_media[1], ...
    for index, media in enumerate(uploaded_media):
        payload[f"attached_media[{index}]"] = json.dumps(media)

    response = requests.post(url, data=payload, timeout=60)
    _raise_for_meta_error(response)

    data = response.json()
    return {"post_id": data.get("id"), "raw_response": data}


# SINGLE VIDEO
def publish_video_to_facebook(page_id, page_access_token, video_url, caption=""):
    """
    Publish one video to a Facebook Page.

    NOTE:
    This is a normal Facebook video post.
    It is NOT a Facebook Reel.
    """
    if not page_id:
        raise ValueError("Facebook Page ID is required.")
    if not page_access_token:
        raise ValueError("Facebook Page access token is required.")
    if not video_url:
        raise ValueError("Video URL is required.")

    url = f"{GRAPH_URL}/{page_id}/videos"
    payload = {
        "file_url": video_url,
        "access_token": page_access_token,
    }
    if caption:
        payload["description"] = caption

    response = requests.post(url, data=payload, timeout=120)
    _raise_for_meta_error(response)

    data = response.json()
    return {
        "post_id": data.get("post_id") or data.get("id"),
        "raw_response": data,
    }


# GET FACEBOOK PAGE MEDIA
def get_facebook_account_media(
    page_id,
    page_access_token,
    limit=25,
    after=None,
    before=None,
):
    """
    Fetch Facebook Page media/posts with cursor pagination.
    """

    if not page_id:
        raise ValueError("Facebook Page ID is required.")

    if not page_access_token:
        raise ValueError(
            "Facebook Page access token is required."
        )

    url = f"{GRAPH_URL}/{page_id}/posts"

    params = {
        "fields": (
            "id,"
            "message,"
            "created_time,"
            "permalink_url,"
            "full_picture,"
            "attachments"
        ),
        "limit": limit,
        "access_token": page_access_token,
    }

    if after:
        params["after"] = after

    if before:
        params["before"] = before

    response = requests.get(
        url,
        params=params,
        timeout=60,
    )

    _raise_for_meta_error(response)

    return response.json()