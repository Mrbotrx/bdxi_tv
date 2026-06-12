import os
import asyncio
import aiohttp
from datetime import datetime

LIVE_API = os.getenv("LIVE_API")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}


# ---------- EXTRACT CHANNELS ----------
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


# ---------- GET CATEGORY ----------
def get_category(ch):
    g = ch.get("genre")
    if isinstance(g, list) and g:
        return g[0]
    return "General"


# ---------- GET STREAM ----------
def get_stream(ch):
    # priority order
    return (
        ch.get("protectedHlsConsumerUrl")
        or ch.get("nonProtectedHlsConsumerUrl")
        or ch.get("protectedDashWidevineConsumerUrl")
    )


# ---------- HEADER ----------
def make_header(total):
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")

    return f"""#EXTM3U
############################################
#        📡 BDXI ALL CHANNELS
############################################
# 📺 Total Channels : {total}
# 🔥 Status : ALL INCLUSIVE (DRM + NON-DRM)
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
    stream = get_stream(ch)

    if not pid or not stream:
        return None

    return {
        "id": pid,
        "name": name,
        "logo": logo,
        "category": category,
        "url": stream
    }


# ---------- MAIN ----------
async def main():

    async with aiohttp.ClientSession(headers=HEADERS) as session:

        async with session.get(LIVE_API) as r:
            data = await r.json(content_type=None)

        channels = extract_channels(data)

        sem = asyncio.Semaphore(120)

        tasks = [fetch(session, sem, ch) for ch in channels]
        results = await asyncio.gather(*tasks)

        valid = [x for x in results if x]
        seen = set()

        lines = [make_header(len(valid))]

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

        print(f"Saved {len(valid)} total channels")


if __name__ == "__main__":
    asyncio.run(main())
