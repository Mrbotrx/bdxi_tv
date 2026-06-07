import os
from datetime import datetime
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor

# Multiple Sources
SOURCE_URLS = [
    os.getenv("KBPROTV"),
    os.getenv("KBPROTV2"),
]

OUTPUT_FILE = "kbtvpro.m3u8"

DEFAULT_LOGO = "https://raw.githubusercontent.com/Mrbotrx/bdxi_tv/main/assets/default_tv.png"


def check_live_stream(channel):
    info, link = channel

    try:
        response = requests.head(link, timeout=3.0, allow_redirects=True)
        if response.status_code == 200:
            return info, link
    except:
        try:
            response = requests.get(link, timeout=3.0, stream=True)
            if response.status_code == 200:
                return info, link
        except:
            pass

    return None


def fetch_and_filter_playlist():

    all_lines = []

    # Load all sources
    for source_url in SOURCE_URLS:
        if not source_url:
            continue

        try:
            print(f"Loading: {source_url}")
            response = requests.get(source_url, timeout=15)

            if response.status_code == 200:
                all_lines.extend(response.text.splitlines())

        except Exception as e:
            print(f"Error loading source: {e}")

    if not all_lines:
        print("No data found!")
        return

    raw_bd_india_channels = []
    raw_other_channels = []

    current_info = None
    seen_links = set()

    PRIORITY_KEYWORDS = [
        "bd", "bangla", "bangladesh",
        "india", "ind ", "zee", "star", "sony", "colors",

        # Sports
        "sports", "sport", "cricket", "football", "soccer",
        "t sports", "tsports", "ten sports", "ptv sports",
        "star sports", "sony sports", "sky sports",
        "fox sports", "espn", "eurosport", "supersport",
        "bein sports", "bein", "willow",
        "astro cricket", "astro supersport",
        "premier sports", "arena sport"
    ]

    for line in all_lines:

        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            current_info = line

        elif line.startswith("http") or line.startswith("rtmp"):

            if line in seen_links:
                current_info = None
                continue

            seen_links.add(line)

            is_mp4 = ".mp4" in line.lower()
            is_promo = ("promo" in line.lower() or
                        (current_info and "promo" in current_info.lower()))
            is_m3u8 = (".m3u8" in line.lower() or "live" in line.lower())

            if is_m3u8 and not is_mp4 and not is_promo:

                channel_meta = current_info if current_info else \
                    '#EXTINF:-1 tvg-id="" tvg-name="Channel" tvg-logo="",Live Channel'

                if 'tvg-logo=""' in channel_meta or 'tvg-logo' not in channel_meta:
                    if 'tvg-logo=""' in channel_meta:
                        channel_meta = channel_meta.replace(
                            'tvg-logo=""',
                            f'tvg-logo="{DEFAULT_LOGO}"'
                        )
                    else:
                        channel_meta = channel_meta.replace(
                            "#EXTINF:-1",
                            f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}"'
                        )

                meta_lower = channel_meta.lower()

                is_priority = any(
                    keyword in meta_lower
                    for keyword in PRIORITY_KEYWORDS
                )

                if is_priority:
                    raw_bd_india_channels.append((channel_meta, line))
                else:
                    raw_other_channels.append((channel_meta, line))

            current_info = None

    print("Checking streams...")

    verified_bd_in = []
    verified_others = []

    with ThreadPoolExecutor(max_workers=20) as executor:

        bd_results = executor.map(check_live_stream, raw_bd_india_channels)
        other_results = executor.map(check_live_stream, raw_other_channels)

        for r in bd_results:
            if r:
                verified_bd_in.append(r)

        for r in other_results:
            if r:
                verified_others.append(r)

    final_playlist = verified_bd_in + verified_others

    dhaka_tz = pytz.timezone("Asia/Dhaka")
    current_time = datetime.now(dhaka_tz).strftime("%I:%M %p | %d-%b-%Y")

    header = f"""#EXTM3U
# IPTV STREAM HUB
# Channels: {len(final_playlist)}
# Time: {current_time} (BST)

"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(header)

        for info, link in final_playlist:
            f.write(f"{info}\n{link}\n")

    print(f"Done! Total channels: {len(final_playlist)}")


if __name__ == "__main__":
    fetch_and_filter_playlist()
