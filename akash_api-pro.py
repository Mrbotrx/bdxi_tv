#!/usr/bin/env python3

import json
import re
import time
from pathlib import Path

import requests


# ============================================================
# AKASH → KB AUTO M3U + MOD JSON
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
# OUTPUT
# ============================================================

M3U_FILE = Path("akash_DTH.m3u")
JSON_FILE = Path("akash_DTH.json")


# ============================================================
# SETTINGS
# ============================================================

TIMEOUT = 30
RETRIES = 3
DELAY = 0.20

ORIGIN = "https://akashgo.com"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 11) "
    "AppleWebKit/537.36 "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
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
# REQUEST JSON
# ============================================================

def request_json(url):

    last_error = None

    for attempt in range(1, RETRIES + 1):

        try:

            response = session.get(
                url,
                timeout=TIMEOUT,
                allow_redirects=True,
            )

            response.raise_for_status()

            # Normal JSON
            try:
                return response.json()

            except ValueError:

                # Some APIs return JSON with
                # text/html content-type.
                text = response.text.strip()

                if not text:
                    raise RuntimeError(
                        "Empty API response"
                    )

                try:
                    return json.loads(text)

                except json.JSONDecodeError:

                    raise RuntimeError(
                        "API response is not JSON: "
                        + response.headers.get(
                            "content-type",
                            "unknown"
                        )
                    )

        except Exception as error:

            last_error = error

            print(
                f"    Request failed "
                f"{attempt}/{RETRIES}: {error}"
            )

            if attempt < RETRIES:
                time.sleep(1)

    raise RuntimeError(
        f"Request failed: {last_error}"
    )


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
# CLEAN
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

    return value.strip(
        "\"' \t\r\n,;)]}"
    )


# ============================================================
# VALID URL
# ============================================================

def valid_url(value):

    value = clean(value)

    if value.startswith(
        "https://"
    ):
        return value

    if value.startswith(
        "http://"
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
# EXTRACT ALL URLS
# ============================================================

def extract_urls(data):

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

        if isinstance(item, str):

            for match in URL_REGEX.findall(
                item
            ):
                add(match)

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
# FIND VALUES BY KEY
# ============================================================

def find_values(data, keys):

    wanted = {
        str(key)
        .lower()
        .replace("-", "_")
        for key in keys
    }

    result = []

    for obj in walk(data):

        if not isinstance(
            obj,
            dict
        ):
            continue

        for key, value in obj.items():

            normalized = (
                str(key)
                .lower()
                .replace("-", "_")
            )

            if normalized in wanted:

                value = clean(value)

                if value:
                    result.append(value)

    return result


def find_first(data, keys):

    values = find_values(
        data,
        keys
    )

    return values[0] if values else ""


# ============================================================
# GET CHANNEL IDS
# ============================================================

def extract_ids(data):

    ids = []
    seen = set()

    # --------------------------------------------------------
    # Priority IDs
    # --------------------------------------------------------

    priority_keys = {
        "channelid",
        "channel_id",
        "contentid",
        "content_id",
    }

    for obj in walk(data):

        if not isinstance(
            obj,
            dict
        ):
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
    # Generic ID
    # --------------------------------------------------------

    for obj in walk(data):

        if not isinstance(
            obj,
            dict
        ):
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
# NAME
# ============================================================

def find_name(data):

    values = find_values(
        data,
        {
            "name",
            "channelName",
            "channel_name",
            "title",
            "displayName",
            "display_name",
        }
    )

    for value in values:

        lower = value.lower()

        if (
            "http://" not in lower
            and "https://" not in lower
            and ".m3u8" not in lower
            and ".mpd" not in lower
            and len(value) <= 200
        ):

            return value

    return ""


# ============================================================
# LOGO
# ============================================================

def find_logo(data):

    values = find_values(
        data,
        {
            "logo",
            "logoUrl",
            "logo_url",
            "image",
            "imageUrl",
            "image_url",
            "thumbnail",
            "thumbnailUrl",
            "thumbnail_url",
            "poster",
            "icon",
        }
    )

    for value in values:

        url = valid_url(value)

        if url:
            return url

    return ""


# ============================================================
# STREAM
# ============================================================

def find_stream(data):

    # --------------------------------------------------------
    # Known fields
    # --------------------------------------------------------

    values = find_values(
        data,
        {
            "link",
            "url",
            "stream",
            "streamUrl",
            "stream_url",
            "playUrl",
            "play_url",
            "playbackUrl",
            "playback_url",
            "source",
            "src",
            "manifest",
            "m3u8",
            "hls",
            "mediaUrl",
            "media_url",
            "videoUrl",
            "video_url",
        }
    )

    # --------------------------------------------------------
    # M3U8 first
    # --------------------------------------------------------

    for value in values:

        url = valid_url(value)

        if ".m3u8" in url.lower():
            return url

    # --------------------------------------------------------
    # MPD fallback
    # --------------------------------------------------------

    for value in values:

        url = valid_url(value)

        if ".mpd" in url.lower():
            return url

    # --------------------------------------------------------
    # Scan every URL
    # --------------------------------------------------------

    urls = extract_urls(data)

    for url in urls:

        if ".m3u8" in url.lower():
            return url

    for url in urls:

        if ".mpd" in url.lower():
            return url

    return ""


# ============================================================
# GET CHANNEL
# ============================================================

def get_channel(channel_id):

    api_url = CHANNEL_API.format(
        channel_id
    )

    data = request_json(
        api_url
    )

    user_agent = find_first(
        data,
        {
            "userAgent",
            "user_agent",
            "useragent",
        }
    )

    referrer = find_first(
        data,
        {
            "referrer",
            "referer",
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

        "name": find_name(
            data
        ),

        "link": find_stream(
            data
        ),

        "logo": find_logo(
            data
        ),

        # Fixed
        "origin": ORIGIN,

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
# NAME + KB
# ============================================================

def make_name(
    name,
    channel_id
):

    name = clean(name)

    if not name:

        name = (
            f"Channel {channel_id}"
        )

    # Remove existing KB
    name = re.sub(
        r"\s+KB\s*$",
        "",
        name,
        flags=re.IGNORECASE
    )

    return (
        f"{name.strip()} KB"
    )


# ============================================================
# M3U ATTRIBUTE
# ============================================================

def attr(value):

    return clean(
        value
    ).replace(
        '"',
        "'"
    )


# ============================================================
# CREATE M3U
# ============================================================

def create_m3u(channels):

    lines = [
        "#EXTM3U"
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

        user_agent = (
            channel.get(
                "userAgent"
            )
            or DEFAULT_USER_AGENT
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

        line = (
            "#EXTINF:-1 "
            f'tvg-id="{attr(channel["id"])}" '
            f'tvg-name="{attr(name)}"'
        )

        if logo:

            line += (
                f' tvg-logo="{attr(logo)}"'
            )

        line += (
            f",{name}"
        )

        lines.append(line)

        # ----------------------------------------------------
        # Origin
        # ----------------------------------------------------

        lines.append(
            "#EXTVLCOPT:http-origin="
            + ORIGIN
        )

        # ----------------------------------------------------
        # User-Agent
        # ----------------------------------------------------

        if user_agent:

            lines.append(
                "#EXTVLCOPT:http-user-agent="
                + user_agent
            )

        # ----------------------------------------------------
        # Referrer
        # ----------------------------------------------------

        if referrer:

            lines.append(
                "#EXTVLCOPT:http-referrer="
                + referrer
            )

        # ----------------------------------------------------
        # Cookie
        # ----------------------------------------------------

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

    return "\n".join(
        lines
    )


# ============================================================
# CREATE MOD JSON
# ============================================================

def create_mod_json(channels):

    output = []

    for channel in channels:

        item = {

            "name": make_name(
                channel["name"],
                channel["id"]
            ),

            "link": channel["link"],

            "logo": channel.get(
                "logo",
                ""
            ),

            "origin": ORIGIN,

            "referrer": channel.get(
                "referrer",
                ""
            ),

            "userAgent": (
                channel.get(
                    "userAgent"
                )
                or DEFAULT_USER_AGENT
            ),

            "cookie": channel.get(
                "cookie",
                ""
            ),

            "drmScheme": channel.get(
                "drmScheme",
                ""
            ),

            "drmLicense": channel.get(
                "drmLicense",
                ""
            ),
        }

        output.append(item)

    return output


# ============================================================
# SAVE FILES
# ============================================================

def save_files(channels):

    # M3U
    m3u = create_m3u(
        channels
    )

    M3U_FILE.write_text(
        m3u,
        encoding="utf-8"
    )

    # MOD JSON
    mod_data = create_mod_json(
        channels
    )

    JSON_FILE.write_text(
        json.dumps(
            mod_data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "          AKASH → KB M3U8 + MOD AUTO SYSTEM"
    )
    print("=" * 70)

    # ========================================================
    # STEP 1
    # ========================================================

    print()
    print(
        "[1/5] Loading channel IDs..."
    )

    try:

        search_data = request_json(
            SEARCH_API
        )

    except Exception as error:

        print(
            "SEARCH API ERROR:"
        )

        print(error)

        raise SystemExit(1)

    ids = extract_ids(
        search_data
    )

    print(
        f"Found IDs: {len(ids)}"
    )

    if not ids:

        raise SystemExit(
            "No channel IDs found."
        )

    # ========================================================
    # STEP 2
    # ========================================================

    print()
    print(
        "[2/5] Loading channel details..."
    )

    channels = []

    seen_links = set()

    failed = 0

    for number, channel_id in enumerate(
        ids,
        1
    ):

        print(
            f"[{number}/{len(ids)}] "
            f"ID: {channel_id}"
        )

        try:

            channel = get_channel(
                channel_id
            )

            link = channel[
                "link"
            ]

            if not link:

                failed += 1

                print(
                    "  -> SKIP: "
                    "M3U8 not found"
                )

                continue

            if link in seen_links:

                print(
                    "  -> SKIP: "
                    "duplicate"
                )

                continue

            seen_links.add(
                link
            )

            channel["name"] = make_name(
                channel["name"],
                channel_id
            )

            channel["origin"] = ORIGIN

            channels.append(
                channel
            )

            print(
                f"  -> OK: "
                f"{channel['name']}"
            )

            print(
                f"  -> M3U8: "
                f"{link}"
            )

            print(
                f"  -> ORIGIN: "
                f"{ORIGIN}"
            )

        except Exception as error:

            failed += 1

            print(
                f"  -> ERROR: {error}"
            )

        time.sleep(
            DELAY
        )

    # ========================================================
    # STEP 3
    # ========================================================

    print()
    print(
        "[3/5] Preparing M3U8..."
    )

    if not channels:

        raise SystemExit(
            "No working channels found."
        )

    # ========================================================
    # STEP 4
    # ========================================================

    print()
    print(
        "[4/5] Preparing MOD JSON..."
    )

    save_files(
        channels
    )

    # ========================================================
    # STEP 5
    # ========================================================

    print()
    print(
        "[5/5] Files created successfully."
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print(
        "                         DONE"
    )
    print("=" * 70)

    print(
        f"Total IDs       : {len(ids)}"
    )

    print(
        f"Working streams : {len(channels)}"
    )

    print(
        f"Failed          : {failed}"
    )

    print(
        f"Origin          : {ORIGIN}"
    )

    print()
    print(
        f"M3U             : {M3U_FILE}"
    )

    print(
        f"MOD JSON        : {JSON_FILE}"
    )

    print("=" * 70)
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
