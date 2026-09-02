#!/usr/bin/env python3

import json
import re
import time
from pathlib import Path

import requests


# ============================================================
# CONFIG
# ============================================================

SEARCH_API = (
    "https://kong.akash-go.com/"
    "search-connector/pub/freemium/search/livedata?id"
)

CHANNEL_API = (
    "https://kong.akash-go.com/"
    "content-detail/pub/api/v6/channels/{}"
)

M3U_FILE = Path("akash_DTH.m3u")
JSON_FILE = Path("akash_DTH.json")

TIMEOUT = 30
RETRIES = 3
DELAY = 0.15

DEFAULT_USER_AGENT = (
    "Abu-Saeeidx/5.0.6 "
    "(Linux;Android 11) AndroidXMedia"
)


# ============================================================
# SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
})


# ============================================================
# HTTP
# ============================================================

def get_json(url):

    last_error = None

    for attempt in range(1, RETRIES + 1):

        try:

            response = session.get(
                url,
                timeout=TIMEOUT,
                allow_redirects=True,
            )

            response.raise_for_status()

            return response.json()

        except Exception as error:

            last_error = error

            print(
                f"    Request attempt "
                f"{attempt}/{RETRIES} failed: {error}"
            )

            if attempt < RETRIES:
                time.sleep(1)

    raise RuntimeError(last_error)


# ============================================================
# RECURSIVE WALK
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
# STRING CLEAN
# ============================================================

def clean(value):

    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return ""

    value = str(value).strip()

    value = value.replace(
        "\\/",
        "/"
    )

    value = value.replace(
        "\\u0026",
        "&"
    )

    value = value.strip(
        "\"' \t\r\n,;)]}"
    )

    return value


# ============================================================
# URL
# ============================================================

def valid_http_url(value):

    value = clean(value)

    if value.startswith(
        ("http://", "https://")
    ):
        return value

    return ""


# ============================================================
# URL REGEX
# ============================================================

URL_REGEX = re.compile(
    r'https?://[^\s"\'<>\\]+',
    re.IGNORECASE
)


# ============================================================
# EXTRACT ALL URLS FROM ANY JSON
# ============================================================

def extract_all_urls(data):

    urls = []
    seen = set()

    def add(url):

        url = clean(url)

        if not url:
            return

        if not url.startswith(
            ("http://", "https://")
        ):
            return

        if url not in seen:

            seen.add(url)
            urls.append(url)

    for item in walk(data):

        # -----------------------------------------------
        # Direct string
        # -----------------------------------------------

        if isinstance(item, str):

            for match in URL_REGEX.findall(item):

                add(match)

        # -----------------------------------------------
        # Dictionary values
        # -----------------------------------------------

        elif isinstance(item, dict):

            for value in item.values():

                if not isinstance(
                    value,
                    str
                ):
                    continue

                for match in URL_REGEX.findall(
                    value
                ):

                    add(match)

    return urls


# ============================================================
# FIND STREAM URL
# ============================================================

def find_stream(data):

    urls = extract_all_urls(data)

    # --------------------------------------------------------
    # Highest priority: M3U8
    # --------------------------------------------------------

    for url in urls:

        if ".m3u8" in url.lower():

            return url

    # --------------------------------------------------------
    # DASH
    # --------------------------------------------------------

    for url in urls:

        if ".mpd" in url.lower():

            return url

    # --------------------------------------------------------
    # Generic live stream
    # --------------------------------------------------------

    keywords = (
        "stream",
        "live",
        "playlist",
        "manifest",
        "playback",
    )

    for url in urls:

        lower = url.lower()

        if any(
            word in lower
            for word in keywords
        ):

            return url

    return ""


# ============================================================
# FIND VALUE BY KEY
# ============================================================

def find_values_by_keys(data, wanted_keys):

    wanted = {
        str(x).lower().replace("-", "_")
        for x in wanted_keys
    }

    values = []

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            normalized = (
                str(key)
                .lower()
                .replace("-", "_")
            )

            if normalized not in wanted:
                continue

            value = clean(value)

            if value:
                values.append(value)

    return values


# ============================================================
# CHANNEL NAME
# ============================================================

def find_name(data):

    keys = {
        "name",
        "channelname",
        "channel_name",
        "title",
        "displayname",
        "display_name",
        "channelTitle",
        "channel_title",
    }

    values = find_values_by_keys(
        data,
        keys
    )

    for value in values:

        lower = value.lower()

        if (
            "http://" not in lower
            and "https://" not in lower
            and ".m3u8" not in lower
            and len(value) <= 200
        ):

            return value

    return ""


# ============================================================
# LOGO
# ============================================================

def find_logo(data):

    keys = {
        "logo",
        "logo_url",
        "logourl",
        "image",
        "image_url",
        "imageurl",
        "thumbnail",
        "thumbnail_url",
        "thumbnailurl",
        "poster",
        "icon",
    }

    values = find_values_by_keys(
        data,
        keys
    )

    for value in values:

        if value.startswith(
            ("http://", "https://")
        ):

            return value

    return ""


# ============================================================
# OTHER METADATA
# ============================================================

def find_first(data, keys):

    values = find_values_by_keys(
        data,
        keys
    )

    return values[0] if values else ""


# ============================================================
# IDS
# ============================================================

def extract_ids(data):

    ids = []
    seen = set()

    priority_keys = {
        "channelid",
        "channel_id",
        "contentid",
        "content_id",
    }

    # --------------------------------------------------------
    # Priority IDs
    # --------------------------------------------------------

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            normalized = (
                str(key)
                .lower()
                .replace("-", "_")
            )

            if normalized not in priority_keys:
                continue

            value = clean(value)

            if (
                value
                and value not in seen
            ):

                seen.add(value)
                ids.append(value)

    # --------------------------------------------------------
    # Normal ID
    # --------------------------------------------------------

    for obj in walk(data):

        if not isinstance(obj, dict):
            continue

        for key, value in obj.items():

            if str(key).lower() != "id":
                continue

            value = clean(value)

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
# CHANNEL API
# ============================================================

def get_channel(channel_id):

    url = CHANNEL_API.format(
        channel_id
    )

    data = get_json(url)

    name = find_name(data)

    logo = find_logo(data)

    link = find_stream(data)

    origin = find_first(
        data,
        {
            "origin",
        }
    )

    referrer = find_first(
        data,
        {
            "referrer",
            "referer",
        }
    )

    user_agent = find_first(
        data,
        {
            "userAgent",
            "user_agent",
            "useragent",
        }
    )

    cookie = find_first(
        data,
        {
            "cookie",
        }
    )

    drm_scheme = find_first(
        data,
        {
            "drmScheme",
            "drm_scheme",
        }
    )

    drm_license = find_first(
        data,
        {
            "drmLicense",
            "drm_license",
        }
    )

    return {
        "id": channel_id,
        "name": name,
        "link": link,
        "logo": logo,
        "origin": origin,
        "referrer": referrer,
        "userAgent": (
            user_agent
            or DEFAULT_USER_AGENT
        ),
        "cookie": cookie,
        "drmScheme": drm_scheme,
        "drmLicense": drm_license,
    }


# ============================================================
# NAME
# ============================================================

def final_name(name, channel_id):

    name = clean(name)

    if not name:

        name = f"Channel {channel_id}"

    # Remove existing KB
    name = re.sub(
        r"\s+KB\s*$",
        "",
        name,
        flags=re.IGNORECASE,
    )

    return f"{name} KB"


# ============================================================
# M3U ATTRIBUTE ESCAPE
# ============================================================

def attr(value):

    value = clean(value)

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
        "",
    ]

    for channel in channels:

        name = final_name(
            channel["name"],
            channel["id"]
        )

        link = channel["link"]

        logo = channel.get(
            "logo",
            ""
        )

        user_agent = channel.get(
            "userAgent",
            ""
        )

        referrer = channel.get(
            "referrer",
            ""
        )

        cookie = channel.get(
            "cookie",
            ""
        )

        # ----------------------------------------------------
        # EXTINF
        # ----------------------------------------------------

        info = (
            '#EXTINF:-1 '
            f'tvg-id="{attr(channel["id"])}" '
            f'tvg-name="{attr(name)}"'
        )

        if logo:

            info += (
                f' tvg-logo="{attr(logo)}"'
            )

        info += f",{name}"

        lines.append(info)

        # ----------------------------------------------------
        # Headers
        # ----------------------------------------------------

        if user_agent:

            lines.append(
                "#EXTVLCOPT:http-user-agent="
                + user_agent
            )

        if referrer:

            lines.append(
                "#EXTVLCOPT:http-referrer="
                + referrer
            )

        if cookie:

            lines.append(
                "#EXTVLCOPT:http-cookie="
                + cookie
            )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

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
    print("=" * 70)
    print("             AKASH → KB AUTO PLAYLIST")
    print("=" * 70)

    # ========================================================
    # STEP 1
    # ========================================================

    print()
    print("[1/4] Loading channel IDs...")

    try:

        search_data = get_json(
            SEARCH_API
        )

    except Exception as error:

        print()
        print("SEARCH API ERROR:")
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

    # ========================================================
    # STEP 2
    # ========================================================

    print()
    print("[2/4] Loading channel details...")

    channels = []

    seen_links = set()

    success = 0
    failed = 0

    for index, channel_id in enumerate(
        ids,
        start=1
    ):

        print(
            f"[{index}/{len(ids)}] ID: {channel_id}"
        )

        try:

            channel = get_channel(
                channel_id
            )

            link = channel["link"]

            if not link:

                failed += 1

                print(
                    "  -> SKIP: stream URL not found"
                )

                continue

            # ------------------------------------------------
            # Duplicate
            # ------------------------------------------------

            if link in seen_links:

                print(
                    "  -> SKIP: duplicate URL"
                )

                continue

            seen_links.add(link)

            # ------------------------------------------------
            # Name
            # ------------------------------------------------

            channel["name"] = final_name(
                channel["name"],
                channel_id
            )

            channels.append(
                channel
            )

            success += 1

            print(
                f"  -> OK: {channel['name']}"
            )

            print(
                f"  -> M3U8: {link}"
            )

        except Exception as error:

            failed += 1

            print(
                f"  -> ERROR: {error}"
            )

        time.sleep(DELAY)

    # ========================================================
    # STEP 3
    # ========================================================

    print()
    print("[3/4] Building playlist...")

    if not channels:

        print()
        print(
            "ERROR: 0 valid channels."
        )

        print(
            "The API response format may have changed."
        )

        raise SystemExit(1)

    m3u = create_m3u(
        channels
    )

    # ========================================================
    # STEP 4
    # ========================================================

    print()
    print("[4/4] Saving files...")

    M3U_FILE.write_text(
        m3u,
        encoding="utf-8"
    )

    save_json(
        channels
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("                         DONE")
    print("=" * 70)

    print(
        f"Total IDs      : {len(ids)}"
    )

    print(
        f"Working streams: {success}"
    )

    print(
        f"Failed         : {failed}"
    )

    print(
        f"M3U file       : {M3U_FILE}"
    )

    print(
        f"JSON file      : {JSON_FILE}"
    )

    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
