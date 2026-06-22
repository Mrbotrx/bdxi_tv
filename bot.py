import os
from datetime import datetime
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor

# ================= SOURCES =================
SOURCE_URLS = [
    os.getenv("KBPROTV"),
    os.getenv("KBPROTV2"),
    os.getenv("ABCD")
]

OUTPUT_FILE = "kbtvpro.m3u8"

DEFAULT_LOGO = "https://raw.githubusercontent.com/Mrbotrx/bdxi_tv/main/assets/default_tv.png"


# ================= FAST LIVE CHECK =================
def check_live_stream(channel):
    info, link = channel

    if not link or not link.startswith("http"):
        return None

    try:
        r = requests.get(
            link,
            timeout=2,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if r.status_code == 200:
            return info, link

    except:
        return None

    return None


# ================= MAIN FUNCTION =================
def fetch_and_filter_playlist():

    all_lines = []

    # -------- Load Sources --------
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

    seen_links = set()
    current_info = None
    raw_priority = []

    # ================= FILTER KEYWORDS =================
    KEYWORDS = [
        # ---------- Bangladesh ----------
        "bd", "bangla", "bangladesh",
        "channel i", "ntv", "rtv",
        "ekattor", "independent",
        "somoy", "jamuna", "gtv",
        "gazi tv", "banglavision",
        "boishakhi", "desh tv", "mohona",

        # ---------- India ----------
        "india", "zee", "star", "sony", "colors",
        "star plus", "star gold",
        "zee cinema", "zee bangla",
        "sony max", "sony sab", "sony tv",
        "star jalsha", "colors bangla",
        "sun tv", "asianet", "gemini",

        # ---------- Sports + FIFA ----------
        "sport", "sports",
        "cricket", "football", "soccer",
        "fifa", "uefa", "afc",
        "champions league", "europa league",
        "premier league", "laliga",
        "serie a", "bundesliga",

        "tsports", "t sports",
        "ten sports",
        "ptv sports",
        "star sports",
        "sony sports",
        "espn",
        "fox sports",
        "sky sports",
        "bein sports",
        "bein",
        "willow",
        "supersport",
        "eurosport"
    ]

    # ================= PARSE M3U =================
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

            # skip mp4
            if ".mp4" in link.lower():
                current_info = None
                continue

            # skip promo
            if current_info and "promo" in current_info.lower():
                current_info = None
                continue

            # FAST FILTER
            if ".m3u8" not in link.lower() and "live" not in link.lower():
                current_info = None
                continue

            meta = current_info if current_info else "#EXTINF:-1,Live TV"

            # add logo if missing
            if "tvg-logo" not in meta:
                meta = meta.replace(
                    "#EXTINF:-1",
                    f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}"'
                )

            # only allowed channels
            if any(k in meta.lower() for k in KEYWORDS):
                raw_priority.append((meta, link))

            current_info = None

    print("Checking LIVE streams...")

    # ================= LIVE CHECK =================
    final = []

    with ThreadPoolExecutor(max_workers=60) as ex:
        for result in ex.map(check_live_stream, raw_priority):
            if result:
                final.append(result)

    # ================= TIME =================
    dhaka = pytz.timezone("Asia/Dhaka")
    now = datetime.now(dhaka).strftime("%I:%M %p | %d-%b-%Y")

    # ================= HEADER =================
    header = f"""#EXTM3U
############################################
#            📡 IPTV STREAM HUB
############################################
# 👨‍💻 Dev      : KB CYBER TEAM
# 🌐 Panel     : https://kbtvpro.totalh.net/
# 💻 GitHub    : https://github.com/Mrbotrx
# 📢 Telegram  : https://t.me/KBCYBERTEAM
############################################
# 📺 Total Channels : {len(final)}
# 🔥 Status          : LIVE / FILTERED
# 🧪 Engine          : BD + INDIA + SPORTS ONLY
############################################
# 🕒 Updated Time : {now}
# 📍 Region       : Bangladesh / India / Sports
############################################
"""

    # ================= WRITE FILE =================
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(header + "\n")

        for info, link in final:
            f.write(f"{info}\n{link}\n")

    print("DONE - Channels:", len(final))


if __name__ == "__main__":
    fetch_and_filter_playlist()
