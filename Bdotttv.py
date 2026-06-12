import os
import asyncio
import aiohttp
from datetime import datetime

# 🔐 from GitHub Secrets
LIVE_API = os.getenv("LIVE_API")
DETAIL_API = os.getenv("DETAIL_API")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}


# ---------- M3U8 FIND ----------
def find_m3u8(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            r = find_m3u8(v)
            if r:
                return r

    elif isinstance(obj, list):
        for i in obj:
            r = find_m3u8(i)
            if r:
                return r

    elif isinstance(obj, str):
        if ".m3u8" in obj.lower():
            return obj

    return None


# ---------- CHANNEL EXTRACT ----------
def extract_channels(data):
    channels = []

    def walk(obj):
        if isinstance(obj, dict):
            if "contentList" in obj and isinstance(obj["contentList"], list):
                channels.extend(obj["contentList"])

            for v in obj.values():
                walk(v)

        elif isinstance(obj, list):
            for i in obj:
                walk(i)

    walk(data)
    return channels


# ---------- HEADER ----------
def header(total):
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")

    return f"""#EXTM3U
############################################
#            📡 IPTV × KB
############################################
# 👨‍💻 Dev      : KB CYBER TEAM
# 💻 GitHub    : https://github.com/Mrbotrx
# 📢 Telegram  : https://t.me/KBCYBERTEAM
############################################
# 📺 Total Channels : {total}
# 🔥 Status          : LIVE / FILTERED
# 🧪 Engine          : BD + INDIA + SPORTS
############################################
# 🕒 Updated Time : {now}
############################################

"""


# ---------- FETCH ----------
async def fetch(session, sem, ch):
    pid = ch.get("providerContentId")
    name = ch.get("channelName") or ch.get("title") or "Unknown"
    logo = ch.get("logo") or ""
    genre = ch.get("genre") or []

    category = genre[0] if isinstance(genre, list) and genre else "General"

    if not pid:
        return None

    try:
        async with sem:
            async with session.get(DETAIL_API.format(pid), timeout=20) as r:
                data = await r.json(content_type=None)

        stream = find_m3u8(data)

        if not stream:
            return None

        return {
            "id": pid,
            "name": name,
            "logo": logo,
            "category": category,
            "url": stream
        }

    except:
        return None


# ---------- MAIN ----------
async def main():

    async with aiohttp.ClientSession(headers=HEADERS) as session:

        async with session.get(LIVE_API) as r:
            data = await r.json(content_type=None)

        channels = extract_channels(data)

        sem = asyncio.Semaphore(80)

        tasks = [fetch(session, sem, ch) for ch in channels]
        results = await asyncio.gather(*tasks)

        valid = [x for x in results if x]
        seen = set()

        lines = []

        lines.append(header(len(valid)))

        for ch in valid:

            if ch["id"] in seen:
                continue

            seen.add(ch["id"])

            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["category"]}",{ch["name"]}\n'
            )

            lines.append(ch["url"] + "\n")

        with open("akashdth.m3u", "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"Saved {len(valid)} channels")


if __name__ == "__main__":
    asyncio.run(main())
