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


# ⚡ FAST CHECK (optimized)
def check_live_stream(channel):
    info, link = channel

    if not link or not link.startswith("http"):
        return None

    try:
        r = requests.get(link, timeout=2, stream=True)
        if r.status_code == 200:
            return info, link
    except:
        return None

    return None


def fetch_and_filter_playlist():

    all_lines = []

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
    seen = set()
    current_info = None

    PRIORITY = [
        "bd","bangla","bangladesh","india","zee","star","sony","colors",
        "sports","cricket","football","tsports","ten sports","ptv sports",
        "espn","bein","sky sports","willow","fox sports"
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

            # ⚠️ HEADER unchanged, only logic fix
            if "tvg-logo" not in meta:
                meta = meta.replace(
                    "#EXTINF:-1",
                    f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}"'
                )

            if any(k in meta.lower() for k in PRIORITY):
                raw_priority.append((meta, line))
            else:
                raw_other.append((meta, line))

            current_info = None

    print("Checking streams...")

    final = []

    with ThreadPoolExecutor(max_workers=50) as ex:
        for result in ex.map(check_live_stream, raw_priority + raw_other):
            if result:
                final.append(result)

    dhaka = pytz.timezone("Asia/Dhaka")
    now = datetime.now(dhaka).strftime("%I:%M %p | %d-%b-%Y")

    # ✅ HEADER EXACT SAME AS YOUR ORIGINAL
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
# 🧪 Engine          : LINK CHECKER ACTIVE
############################################
# 🕒 Updated Time : {now}
# 📍 Region       : Bangladesh / India / Global
############################################
# 🚀 Powered by KB CYBER TEAM
# 📬 Support: @KBCYBERTEAM
############################################
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(header_content + "\n")

        for info, link in final:
            f.write(f"{info}\n{link}\n")

    print("DONE - Channels:", len(final))


if __name__ == "__main__":
    fetch_and_filter_playlist()
