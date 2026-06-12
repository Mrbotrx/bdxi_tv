import os
import asyncio
import aiohttp
from datetime import datetime

LIVE_API = os.getenv("LIVE_API")
DETAIL_API = os.getenv("DETAIL_API")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}


# ---------- EXTRACT ----------
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


# ---------- STREAMS ----------
def get_streams(ch):
    return [
        ch.get("protectedHlsConsumerUrl"),
        ch.get("protectedDashWidevineConsumerUrl")
    ]


# ---------- CATEGORY ----------
def get_category(ch):
    g = ch.get("genre")
    if isinstance(g, list) and g:
        return g[0]
    return "General"


# ---------- HEADER ----------
def header(total):
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")

    return f"""#EXTM3U
############################################
#        📡 BDXI SMART FALLBACK IPTV
############################################
# 📺 Total Channels : {total}
# 🔥 Engine : HLS + DASH fallback
############################################
# 🕒 Updated : {now}
############################################

"""


# ---------- FETCH ----------
async def fetch(session, sem, ch):

    pid = ch.get("providerContentId")
    name = ch.get("channelName") or ch.get("title") or "Unknown"
    logo = ch.get("logo") or ""
    category = get_category(ch)

    if not pid:
        return None

    streams = [s for s in get_streams(ch) if s]

    if not streams:
        return None

    return {
        "id": pid,
        "name": name,
        "logo": logo,
        "category": category,
        "streams": streams
    }


# ---------- MAIN ----------
async def main():

    async with aiohttp.ClientSession(headers=HEADERS) as session:

        async with session.get(LIVE_API) as r:
            data = await r.json(content_type=None)

        channels = extract_channels(data)

        sem = asyncio.Semaphore(100)

        tasks = [fetch(session, sem, ch) for ch in channels]
        results = await asyncio.gather(*tasks)

        valid = [x for x in results if x]
        seen = set()

        lines = [header(len(valid))]

        for ch in valid:

            if ch["id"] in seen:
                continue

            seen.add(ch["id"])

            streams = ch["streams"]

            # M3U EXTINF
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["category"]}",{ch["name"]}\n'
            )

            # PRIMARY + BACKUP STREAMS
            for s in streams:
                lines.append(s + "\n")

        with open("akashdth.m3u", "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"Saved {len(valid)} channels with fallback streams")


if __name__ == "__main__":
    asyncio.run(main())
