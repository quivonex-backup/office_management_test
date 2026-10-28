import time

import requests

from django.conf import settings

GRAPH_URL = f"https://graph.facebook.com/{settings.META_API_VERSION}"


# META ERROR HANDLER
def _raise_for_meta_error(response):
    if response.ok:
        return

    try:
        data = response.json()
    except ValueError:
        data = {}

    error = data.get("error", {})
    message = error.get(
        "message",
        response.text or "Instagram API request failed.",
    )
    code = error.get("code")

    if code:
        raise RuntimeError(f"Instagram API error ({code}): {message}")

    raise RuntimeError(f"Instagram API error: {message}")

# def _raise_for_meta_error(response):
#     if response.ok:
#         return

#     try:
#         data = response.json()
#     except ValueError:
#         data = {}

#     error = data.get("error", {})

#     message = error.get(
#         "message",
#         response.text or "Meta API request failed.",
#     )

#     code = error.get("code")
#     subcode = error.get("error_subcode")
#     error_type = error.get("type")
#     fbtrace_id = error.get("fbtrace_id")

#     raise RuntimeError(
#         f"Meta API error | "
#         f"type={error_type} | "
#         f"code={code} | "
#         f"subcode={subcode} | "
#         f"message={message} | "
#         f"fbtrace_id={fbtrace_id}"
#     )


# CREATE IMAGE CONTAINER
def create_image_container(
    instagram_user_id,
    access_token,
    image_url,
    caption="",
    is_carousel_item=False,
):
    """Create an Instagram image container."""
    if not instagram_user_id:
        raise ValueError("Instagram User ID is required.")
    if not access_token:
        raise ValueError("Instagram access token is required.")
    if not image_url:
        raise ValueError("Image URL is required.")

    url = f"{GRAPH_URL}/{instagram_user_id}/media"
    payload = {
        "image_url": image_url,
        "access_token": access_token,
    }
    if caption:
        payload["caption"] = caption
    if is_carousel_item:
        payload["is_carousel_item"] = "true"

    response = requests.post(url, data=payload, timeout=60)
    _raise_for_meta_error(response)
    return response.json()


# CREATE VIDEO CONTAINER
def create_video_container(
    instagram_user_id,
    access_token,
    video_url,
    caption="",
    is_carousel_item=False,
):
    """
    Create an Instagram normal VIDEO container.

    This is NOT a Reel.
    """
    if not instagram_user_id:
        raise ValueError("Instagram User ID is required.")
    if not access_token:
        raise ValueError("Instagram access token is required.")
    if not video_url:
        raise ValueError("Video URL is required.")

    url = f"{GRAPH_URL}/{instagram_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "access_token": access_token,
    }
    if caption:
        payload["caption"] = caption
    if is_carousel_item:
        payload["is_carousel_item"] = "true"

    response = requests.post(url, data=payload, timeout=60)
    _raise_for_meta_error(response)
    return response.json()


# CREATE CAROUSEL CONTAINER
def create_carousel_container(
    instagram_user_id,
    access_token,
    children,
    caption="",
):
    """
    Create an Instagram carousel container.

    children: comma-separated container IDs
    """
    if not instagram_user_id:
        raise ValueError("Instagram User ID is required.")
    if not access_token:
        raise ValueError("Instagram access token is required.")
    if not children:
        raise ValueError("Carousel children are required.")

    url = f"{GRAPH_URL}/{instagram_user_id}/media"
    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "access_token": access_token,
    }
    if caption:
        payload["caption"] = caption

    response = requests.post(url, data=payload, timeout=60)
    _raise_for_meta_error(response)
    return response.json()


# CONTAINER STATUS
def get_container_status(creation_id, access_token):
    """Get Instagram media container status."""
    url = f"{GRAPH_URL}/{creation_id}"
    params = {
        "fields": "status_code,status",
        "access_token": access_token,
    }

    response = requests.get(url, params=params, timeout=30)
    _raise_for_meta_error(response)
    return response.json()


# WAIT FOR CONTAINER
def wait_for_container_ready(
    creation_id,
    access_token,
    max_attempts=30,
    delay_seconds=5,
):
    """Wait until an Instagram media container has finished processing."""
    for _ in range(max_attempts):
        data = get_container_status(
            creation_id=creation_id,
            access_token=access_token,
        )

        status_code = data.get("status_code")
        status = data.get("status")

        # Ready
        if status_code == "FINISHED":
            return data
        if status == "FINISHED":
            return data

        # Failed
        if status_code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram media container failed: {data}")

        time.sleep(delay_seconds)

    raise RuntimeError(
        "Instagram media container was not ready within the allowed time."
    )


# PUBLISH CONTAINER
def publish_container(instagram_user_id, access_token, creation_id):
    """Publish an Instagram media container."""
    if not creation_id:
        raise ValueError("Instagram creation ID is required.")

    url = f"{GRAPH_URL}/{instagram_user_id}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": access_token,
    }

    response = requests.post(url, data=payload, timeout=60)
    _raise_for_meta_error(response)
    return response.json()


# SINGLE IMAGE
def publish_image_to_instagram(
    instagram_user_id,
    access_token,
    image_url,
    caption="",
):
    """Publish one normal Instagram image post."""
    container = create_image_container(
        instagram_user_id=instagram_user_id,
        access_token=access_token,
        image_url=image_url,
        caption=caption,
    )

    creation_id = container.get("id")
    if not creation_id:
        raise ValueError("Instagram did not return a media container ID.")

    wait_for_container_ready(
        creation_id=creation_id,
        access_token=access_token,
    )

    published = publish_container(
        instagram_user_id=instagram_user_id,
        access_token=access_token,
        creation_id=creation_id,
    )

    return {
        "post_id": published.get("id"),
        "creation_id": creation_id,
        "raw_response": published,
    }


# SINGLE VIDEO
def publish_video_to_instagram(
    instagram_user_id,
    access_token,
    video_url,
    caption="",
):
    """
    Publish a video to Instagram as a Reel.
    """
    container = create_video_container(
        instagram_user_id=instagram_user_id,
        access_token=access_token,
        video_url=video_url,
        caption=caption,
    )

    creation_id = container.get("id")
    if not creation_id:
        raise ValueError("Instagram did not return a video container ID.")

    wait_for_container_ready(
        creation_id=creation_id,
        access_token=access_token,
    )

    published = publish_container(
        instagram_user_id=instagram_user_id,
        access_token=access_token,
        creation_id=creation_id,
    )

    return {
        "post_id": published.get("id"),
        "creation_id": creation_id,
        "raw_response": published,
    }


# MIXED / MULTIPLE CAROUSEL
def publish_carousel_to_instagram(
    instagram_user_id,
    access_token,
    media_items,
    caption="",
):
    """
    Publish an Instagram carousel.

    Supports:
        IMAGE + IMAGE
        VIDEO + VIDEO
        IMAGE + VIDEO
        VIDEO + IMAGE

    Maximum 10 media items.
    """
    if not media_items:
        raise ValueError("At least one media item is required.")
    if len(media_items) < 2:
        raise ValueError("Instagram carousel requires at least 2 media items.")
    if len(media_items) > 10:
        raise ValueError(
            "Instagram carousel supports a maximum of 10 media items."
        )

    child_container_ids = []

    # Create child containers
    for item in media_items:
        media_type = item.get("media_type")
        media_url = item.get("media_url")

        if not media_url:
            raise ValueError("Instagram media URL is required.")

        if media_type == "IMAGE":
            container = create_image_container(
                instagram_user_id=instagram_user_id,
                access_token=access_token,
                image_url=media_url,
                is_carousel_item=True,
            )
        elif media_type == "VIDEO":
            container = create_video_container(
                instagram_user_id=instagram_user_id,
                access_token=access_token,
                video_url=media_url,
                is_carousel_item=True,
            )
        else:
            raise ValueError(f"Unsupported media type: {media_type}")

        creation_id = container.get("id")
        if not creation_id:
            raise ValueError(
                "Instagram did not return a carousel child container ID."
            )

        # Video/image must finish processing
        # before parent carousel is created.
        wait_for_container_ready(
            creation_id=creation_id,
            access_token=access_token,
        )

        child_container_ids.append(creation_id)

    # Create parent carousel
    carousel_container = create_carousel_container(
        instagram_user_id=instagram_user_id,
        access_token=access_token,
        children=child_container_ids,
        caption=caption,
    )

    carousel_creation_id = carousel_container.get("id")
    if not carousel_creation_id:
        raise ValueError("Instagram did not return a carousel container ID.")

    # Wait for carousel
    wait_for_container_ready(
        creation_id=carousel_creation_id,
        access_token=access_token,
    )

    # Publish carousel
    published = publish_container(
        instagram_user_id=instagram_user_id,
        access_token=access_token,
        creation_id=carousel_creation_id,
    )

    return {
        "post_id": published.get("id"),
        "creation_id": carousel_creation_id,
        "child_container_ids": child_container_ids,
        "raw_response": published,
    }


# GET INSTAGRAM ACCOUNT MEDIA
def get_instagram_account_media(
    instagram_user_id,
    access_token,
    limit=25,
    after=None,
    before=None,
):
    """
    Fetch Instagram account media with cursor pagination.
    """

    if not instagram_user_id:
        raise ValueError("Instagram User ID is required.")

    if not access_token:
        raise ValueError("Instagram access token is required.")

    url = f"{GRAPH_URL}/{instagram_user_id}/media"

    params = {
        "fields": (
            "id,"
            "caption,"
            "media_type,"
            "media_product_type,"
            "media_url,"
            "thumbnail_url,"
            "permalink,"
            "timestamp"
        ),
        "limit": limit,
        "access_token": access_token,
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