import os
from datetime import datetime
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor

# Sources (GitHub Secrets)
SOURCE_URLS = [
    os.getenv("KBPROTV"),
    os.getenv("KBPROTV2"),
]

OUTPUT_FILE = "kbtvpro.m3u8"

DEFAULT_LOGO = "https://raw.githubusercontent.com/Mrbotrx/bdxi_tv/main/assets/default_tv.png"


# ⚡ FAST STREAM CHECK (optimized, safe)
def check_live_stream(channel):
    info, link = channel

    if not link or not link.startswith("http"):
        return None

    try:
        r = requests.get(link, timeout=2, stream=True)

        # only valid live response
        if r.status_code == 200:
            return info, link

    except:
        return None

    return None


def fetch_and_filter_playlist():

    all_lines = []

    # Load sources
    for url in SOURCE_URLS:
        if not url:
            continue

        try:
            print("Loading:", url)
            r = requests.get(url, timeout=10)

            if r.status_code == 200:
                all_lines.extend(r.text.splitlines())

        except Exception as e:
            print("Source error:", e)

    if not all_lines:
        print("No data found")
        return

    raw_priority = []
    raw_other = []
    seen_links = set()
    current_info = None

    # PRIORITY KEYWORDS (UNCHANGED)
    PRIORITY_KEYWORDS = [
        "bd","bangla","bangladesh","india","zee","star","sony","colors",
        "sports","cricket","football","soccer",
        "tsports","ten sports","ptv sports",
        "espn","bein","sky sports","willow","fox sports"
    ]

    for line in all_lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            current_info = line

        elif line.startswith("http"):
            link = line

            # duplicate skip
            if link in seen_links:
                current_info = None
                continue

            seen_links.add(link)

            # ❌ MP4 fully ignored
            if ".mp4" in link.lower():
                current_info = None
                continue

            # ❌ promo skip
            if current_info and "promo" in current_info.lower():
                current_info = None
                continue

            # ⚡ FAST LIVE FILTER (important optimization)
            if ".m3u8" not in link and "live" not in link:
                current_info = None
                continue

            meta = current_info if current_info else "#EXTINF:-1,Live TV"

            # logo fix (UNCHANGED)
            if "tvg-logo" not in meta:
                meta = meta.replace(
                    "#EXTINF:-1",
                    f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}"'
                )

            # priority split (UNCHANGED logic)
            if any(k in meta.lower() for k in PRIORITY_KEYWORDS):
                raw_priority.append((meta, link))
            else:
                raw_other.append((meta, link))

            current_info = None

    print("Checking LIVE streams (FAST MODE)...")

    final = []

    # ⚡ FAST THREAD POOL
    with ThreadPoolExecutor(max_workers=60) as ex:
        for result in ex.map(check_live_stream, raw_priority + raw_other):
            if result:
                final.append(result)

    # timezone
    dhaka = pytz.timezone("Asia/Dhaka")
    now = datetime.now(dhaka).strftime("%I:%M %p | %d-%b-%Y")

    # HEADER (UNCHANGED EXACT AS ORIGINAL STYLE)
    header_content = f"""#EXTM3U
############################################
#            📡 IPTV STREAM HUB           #
############################################
# 👨‍💻 Dev      : KB CYBER TEAM
# 🌐 Panel     : https://kbtvpro.totalh.net/
# 💻 GitHub    : https://github.com/Mrbotrx
# 📢 Telegram  : https://t.me/KBCYBERTEAM
############################################
# 📺 Total Channels : {len(final)}
# 🔥 Status          : LIVE / AUTO VERIFIED
# 🧪 Engine          : FAST LINK FILTER
############################################
# 🕒 Updated Time : {now}
# 📍 Region       : Bangladesh / India / Global
############################################
# 🚀 Powered by KB CYBER TEAM
############################################
"""

    # write file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(header_content + "\n")

        for info, link in final:
            f.write(f"{info}\n{link}\n")

    print("DONE - Channels:", len(final))


if __name__ == "__main__":
    fetch_and_filter_playlist()
