#!/usr/bin/env python3

import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


# ============================================================
# AKASH API CONFIG
# ============================================================

SEARCH_API = (
    "https://kong.akash-go.com/"
    "search-connector/pub/freemium/search/livedata?id"
)

CHANNEL_API = (
    "https://kong.akash-go.com/"
    "content-detail/pub/api/v6/channels/{}"
)


# ============================================================
# OUTPUT FILES
# ============================================================

M3U_FILE = Path("akash_DTH.m3u")

JSON_FILE = Path("akash_DTH.json")


# ============================================================
# SETTINGS
# ============================================================

TIMEOUT = 30

RETRIES = 3

DELAY = 0.15

USER_AGENT = (
    "Abu-Saeeidx/5.0.6 "
    "(Linux;Android 11) AndroidXMedia"
)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "application/json,text/plain,*/*",
})


# ============================================================
# GENERIC REQUEST
# ============================================================

def request_json(url):

    last_error = None

    for attempt in range(1, RETRIES + 1):

        try:

            response = session.get(
                url,
                timeout=TIMEOUT,
            )

            response.raise_for_status()

            return response.json()

        except Exception as error:

            last_error = error

            print(
                f"  Request failed "
                f"({attempt}/{RETRIES})"
            )

            if attempt < RETRIES:
                time.sleep(1)

    raise RuntimeError(
        f"API request failed: {last_error}"
    )


# ============================================================
# RECURSIVE JSON WALKER
# ============================================================

def walk(value):

    if isinstance(value, dict):

        yield value

        for child in value.values():

            yield from walk(child)

    elif isinstance(value, list):

        for child in value:

            yield from walk(child)


# ============================================================
# TEXT CLEAN
# ============================================================

def text(value):

    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return ""

    return str(value).strip()


# ============================================================
# URL CHECK
# ============================================================

def valid_url(value):

    value = text(value)

    if not value:
        return ""

    if not value.startswith(
        ("http://", "https://")
    ):
        return ""

    return value


# ============================================================
# FIND ALL IDS
# ============================================================

def extract_ids(data):

    priority_keys = {
        "channelid",
        "channel_id",
        "channelId".lower(),
        "contentid",
        "content_id",
    }

    ids = []

    seen = set()

    # --------------------------------------------------------
    # First priority: channel-specific IDs
    # --------------------------------------------------------

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            k = str(key).lower().replace(
                "-",
                "_"
            )

            if k in priority_keys:

                value = text(value)

                if (
                    value
                    and value not in seen
                ):

                    seen.add(value)

                    ids.append(value)

    # --------------------------------------------------------
    # Second priority: generic ID
    # --------------------------------------------------------

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            if str(key).lower() != "id":
                continue

            value = text(value)

            if not value:
                continue

            if value.lower() in {
                "null",
                "none",
                "undefined",
            }:
                continue

            if value not in seen:

                seen.add(value)

                ids.append(value)

    return ids


# ============================================================
# NAME FINDER
# ============================================================

NAME_KEYS = {
    "name",
    "channelname",
    "channel_name",
    "title",
    "displayname",
    "display_name",
}


def find_name(data):

    candidates = []

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            k = str(key).lower().replace(
                "-",
                "_"
            )

            if k not in NAME_KEYS:
                continue

            value = text(value)

            if not value:
                continue

            if len(value) > 200:
                continue

            lower = value.lower()

            if (
                "http://" in lower
                or "https://" in lower
                or ".m3u8" in lower
            ):
                continue

            candidates.append(value)

    return candidates[0] if candidates else ""


# ============================================================
# LOGO FINDER
# ============================================================

LOGO_KEYS = {
    "logo",
    "logourl",
    "logo_url",
    "image",
    "imageurl",
    "image_url",
    "thumbnail",
    "thumbnailurl",
    "thumbnail_url",
    "poster",
}


def find_logo(data):

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            k = str(key).lower().replace(
                "-",
                "_"
            )

            if k not in LOGO_KEYS:
                continue

            url = valid_url(value)

            if url:
                return url

    return ""


# ============================================================
# STREAM URL FINDER
# ============================================================

STREAM_KEYS = {
    "link",
    "url",
    "stream",
    "streamurl",
    "stream_url",
    "playurl",
    "play_url",
    "playbackurl",
    "playback_url",
    "source",
    "src",
    "manifest",
    "m3u8",
    "hls",
}


def is_stream(url):

    url = valid_url(url)

    if not url:
        return False

    lower = url.lower()

    if ".m3u8" in lower:
        return True

    if ".mpd" in lower:
        return True

    for word in (
        "m3u8",
        "manifest",
        "playlist",
        "stream",
        "playback",
        "live",
    ):

        if word in lower:
            return True

    return False


def find_stream(data):

    candidates = []

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            k = str(key).lower().replace(
                "-",
                "_"
            )

            if k not in STREAM_KEYS:
                continue

            url = valid_url(value)

            if url:
                candidates.append(url)

    # Prefer HLS
    for url in candidates:

        if ".m3u8" in url.lower():

            return url

    # DASH
    for url in candidates:

        if ".mpd" in url.lower():

            return url

    # Generic stream
    for url in candidates:

        if is_stream(url):

            return url

    return ""


# ============================================================
# FALLBACK URL SEARCH
# ============================================================

URL_REGEX = re.compile(
    r'https?://[^\s"\'<>]+',
    re.IGNORECASE
)


def fallback_stream(data):

    for item in walk(data):

        if not isinstance(item, str):
            continue

        matches = URL_REGEX.findall(item)

        for url in matches:

            url = url.rstrip(
                " ,;)]}"
            )

            if ".m3u8" in url.lower():

                return url

    return ""


# ============================================================
# EXTRA METADATA
# ============================================================

def find_value(data, keys):

    keys = {
        x.lower().replace("-", "_")
        for x in keys
    }

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            k = str(key).lower().replace(
                "-",
                "_"
            )

            if k in keys:

                value = text(value)

                if value:
                    return value

    return ""


# ============================================================
# CHANNEL DETAILS
# ============================================================

def get_channel(channel_id):

    url = CHANNEL_API.format(
        channel_id
    )

    data = request_json(url)

    name = find_name(data)

    logo = find_logo(data)

    stream = find_stream(data)

    if not stream:

        stream = fallback_stream(data)

    origin = find_value(
        data,
        {
            "origin",
        }
    )

    referrer = find_value(
        data,
        {
            "referrer",
            "referer",
        }
    )

    user_agent = find_value(
        data,
        {
            "userAgent",
            "user_agent",
            "useragent",
        }
    )

    cookie = find_value(
        data,
        {
            "cookie",
        }
    )

    drm_scheme = find_value(
        data,
        {
            "drmScheme",
            "drm_scheme",
        }
    )

    drm_license = find_value(
        data,
        {
            "drmLicense",
            "drm_license",
        }
    )

    return {
        "id": channel_id,
        "name": name,
        "link": stream,
        "logo": logo,
        "origin": origin,
        "referrer": referrer,
        "userAgent": (
            user_agent
            or USER_AGENT
        ),
        "cookie": cookie,
        "drmScheme": drm_scheme,
        "drmLicense": drm_license,
    }


# ============================================================
# CHANNEL NAME
# ============================================================

def make_name(name, channel_id):

    name = text(name)

    if not name:

        name = f"Channel {channel_id}"

    # Remove existing KB
    name = re.sub(
        r"\s+KB\s*$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    return f"{name.strip()} KB"


# ============================================================
# M3U ESCAPE
# ============================================================

def escape_attr(value):

    value = text(value)

    return value.replace(
        '"',
        "'"
    )


# ============================================================
# CREATE M3U
# ============================================================

def create_m3u(channels):

    lines = [
        "#EXTM3U",
        ""
    ]

    for channel in channels:

        name = make_name(
            channel["name"],
            channel["id"]
        )

        link = channel["link"]

        logo = channel.get(
            "logo",
            ""
        )

        origin = channel.get(
            "origin",
            ""
        )

        referrer = channel.get(
            "referrer",
            ""
        )

        user_agent = channel.get(
            "userAgent",
            ""
        )

        cookie = channel.get(
            "cookie",
            ""
        )

        drm_scheme = channel.get(
            "drmScheme",
            ""
        )

        drm_license = channel.get(
            "drmLicense",
            ""
        )

        attributes = [
            f'tvg-id="{escape_attr(channel["id"])}"',
            f'tvg-name="{escape_attr(name)}"',
        ]

        if logo:

            attributes.append(
                f'tvg-logo="{escape_attr(logo)}"'
            )

        # ----------------------------------------------------
        # M3U HTTP metadata
        # ----------------------------------------------------

        if user_agent:

            attributes.append(
                f'http-user-agent="{escape_attr(user_agent)}"'
            )

        if referrer:

            attributes.append(
                f'http-referrer="{escape_attr(referrer)}"'
            )

        if cookie:

            attributes.append(
                f'http-cookie="{escape_attr(cookie)}"'
            )

        # ----------------------------------------------------
        # EXTINF
        # ----------------------------------------------------

        extinf = (
            "#EXTINF:-1 "
            + " ".join(attributes)
            + f",{name}"
        )

        lines.append(extinf)

        # ----------------------------------------------------
        # Optional Kodi-style metadata
        # ----------------------------------------------------

        if origin:

            lines.append(
                f'#KODIPROP|inputstream.adaptive.stream_headers=Origin={origin}'
            )

        if referrer:

            lines.append(
                f'#KODIPROP|inputstream.adaptive.stream_headers=Referer={referrer}'
            )

        if drm_scheme:

            lines.append(
                f'#KODIPROP|inputstream.adaptive.license_type={drm_scheme}'
            )

        if drm_license:

            lines.append(
                f'#KODIPROP|inputstream.adaptive.license_key={drm_license}'
            )

        lines.append(link)

        lines.append("")

    return "\n".join(lines)


# ============================================================
# SAVE JSON
# ============================================================

def save_json(channels):

    JSON_FILE.write_text(
        json.dumps(
            channels,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 65)
    print("           AKASH → KB AUTO PLAYLIST")
    print("=" * 65)

    # --------------------------------------------------------
    # 1. SEARCH API
    # --------------------------------------------------------

    print()
    print("[1/4] Loading channel list...")

    try:

        search_data = request_json(
            SEARCH_API
        )

    except Exception as error:

        print()
        print("ERROR:")
        print(error)

        raise SystemExit(1)

    ids = extract_ids(
        search_data
    )

    print(
        f"Found IDs: {len(ids)}"
    )

    if not ids:

        print(
            "ERROR: No channel IDs found."
        )

        raise SystemExit(1)

    # --------------------------------------------------------
    # 2. CHANNEL DETAILS
    # --------------------------------------------------------

    print()
    print("[2/4] Loading channel details...")

    channels = []

    seen_links = set()

    for number, channel_id in enumerate(
        ids,
        start=1
    ):

        print(
            f"[{number}/{len(ids)}] "
            f"ID: {channel_id}"
        )

        try:

            channel = get_channel(
                channel_id
            )

            link = channel["link"]

            if not link:

                print(
                    "  -> SKIP: no stream URL"
                )

                continue

            # ------------------------------------------------
            # Duplicate filtering
            # ------------------------------------------------

            if link in seen_links:

                print(
                    "  -> SKIP: duplicate stream"
                )

                continue

            seen_links.add(link)

            # ------------------------------------------------
            # Final name
            # ------------------------------------------------

            channel["name"] = make_name(
                channel["name"],
                channel_id
            )

            channels.append(
                channel
            )

            print(
                f"  -> OK: {channel['name']}"
            )

        except Exception as error:

            print(
                f"  -> ERROR: {error}"
            )

        time.sleep(DELAY)

    # --------------------------------------------------------
    # 3. VALIDATION
    # --------------------------------------------------------

    print()
    print("[3/4] Validating playlist...")

    if not channels:

        print(
            "ERROR: No valid channels."
        )

        raise SystemExit(1)

    # --------------------------------------------------------
    # 4. SAVE
    # --------------------------------------------------------

    print()
    print("[4/4] Writing files...")

    playlist = create_m3u(
        channels
    )

    M3U_FILE.write_text(
        playlist,
        encoding="utf-8"
    )

    save_json(
        channels
    )

    print()
    print("=" * 65)
    print("                  COMPLETE")
    print("=" * 65)

    print(
        f"Channels : {len(channels)}"
    )

    print(
        f"M3U      : {M3U_FILE}"
    )

    print(
        f"JSON     : {JSON_FILE}"
    )

    print("=" * 65)
    print()


if __name__ == "__main__":
    main()
