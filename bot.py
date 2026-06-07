import os
from datetime import datetime
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor

SOURCE_URLS = [
    os.getenv("KBPROTV"),
    os.getenv("KBPROTV2"),
]

OUTPUT_FILE = "kbtvpro.m3u8"

DEFAULT_LOGO = "https://raw.githubusercontent.com/Mrbotrx/bdxi_tv/main/assets/default_tv.png"


def check_live_stream(channel):
    info, link = channel

    try:
        r = requests.head(link, timeout=3, allow_redirects=True)
        if r.status_code == 200:
            return info, link
    except:
        pass

    try:
        r = requests.get(link, timeout=3, stream=True)
        if r.status_code == 200:
            return info, link
    except:
        pass

    return None


def fetch_and_filter_playlist():

    all_lines = []

    for url in SOURCE_URLS:
        if not url:
            continue

        try:
            print("Loading:", url)
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                all_lines.extend(r.text.splitlines())
        except Exception as e:
            print("Error:", e)

    if not all_lines:
        print("No data found")
        return

    raw_priority = []
    raw_other = []
    seen = set()
    current_info = None

    PRIORITY = [
        "bd","bangla","bangladesh","india","zee","star","sony","colors",
        "sports","cricket","football","tsports","ten sports","ptv sports",
        "espn","bein","sky sports","willow"
    ]

    for line in all_lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            current_info = line

        elif line.startswith("http"):
            if line in seen:
                continue

            seen.add(line)

            if ".mp4" in line.lower():
                continue

            if current_info and "promo" in current_info.lower():
                continue

            meta = current_info if current_info else '#EXTINF:-1,Live TV'

            if "tvg-logo" not in meta:
                meta = meta.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}"')

            if any(k in meta.lower() for k in PRIORITY):
                raw_priority.append((meta, line))
            else:
                raw_other.append((meta, line))

            current_info = None

    print("Checking streams...")

    final = []

    with ThreadPoolExecutor(max_workers=20) as ex:
        for r in ex.map(check_live_stream, raw_priority + raw_other):
            if r:
                final.append(r)

    dhaka = pytz.timezone("Asia/Dhaka")
    now = datetime.now(dhaka).strftime("%I:%M %p | %d-%b-%Y")

    header = f"""#EXTM3U
# IPTV AUTO BOT
# Updated: {now}
# Total: {len(final)}
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for i, l in final:
            f.write(f"{i}\n{l}\n")

    print("Done:", len(final))


if __name__ == "__main__":
    fetch_and_filter_playlist()

def fetch_and_filter_playlist():

    all_lines = []

    # Load sources
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
    seen_links = set()
    current_info = None

    PRIORITY_KEYWORDS = [
        "bd", "bangla", "bangladesh",
        "india", "zee", "star", "sony", "colors",

        "sports", "cricket", "football", "soccer",
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

                # Fix logo
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

    total_channels = len(final_playlist)

    # ⭐ STYLED HEADER
    header_content = f"""#EXTM3U
############################################
#            📡 IPTV STREAM HUB           #
############################################
# 👨‍💻 Dev      : KB CYBER TEAM
# 🌐 Panel     : https://kbtvpro.totalh.net/
# 💻 GitHub    : https://github.com/Mrbotrx
# 📢 Telegram  : https://t.me/KBCYBERTEAM
############################################
# 📺 Total Channels : {total_channels}
# 🔥 Status          : LIVE / AUTO VERIFIED
# 🧪 Engine          : LINK CHECKER ACTIVE
############################################
# 🕒 Updated Time : {current_time}
# 📍 Region       : Bangladesh / India / Global
############################################
# 🚀 Powered by KB CYBER TEAM
# 📬 Support: @KBCYBERTEAM
############################################
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(header_content + "\n")

        for info, link in final_playlist:
            f.write(f"{info}\n{link}\n")

    print(f"Done! Total channels: {total_channels}")


if __name__ == "__main__":
    try:
        print("Starting playlist update...")
        fetch_and_filter_playlist()
        print("Playlist update completed.")
    except Exception as e:
        print(f"Error: {e}")
