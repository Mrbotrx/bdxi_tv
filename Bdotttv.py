
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


# ---------- FIND ALL LINKS ----------
def extract_links(obj):
    m3u8 = []
    mpd = []
    license_links = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():

                lk = k.lower()

                if isinstance(v, str):

                    if ".m3u8" in v.lower():
                        m3u8.append(v)

                    elif ".mpd" in v.lower():
                        mpd.append(v)

                    elif "license" in lk:
                        license_links.append(v)

                else:
                    walk(v)

        elif isinstance(x, list):
            for i in x:
                walk(i)

    walk(obj)

    return {
        "m3u8": list(set(m3u8)),
        "mpd": list(set(mpd)),
        "license": list(set(license_links))
    }


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
#        📡 BDXI FULL STREAM EXTRACTOR
############################################
# 📺 Total Channels : {total}
# 🔥 Mode : ALL STREAMS + LICENSE
############################################
# 🕒 Updated : {now}
############################################

"""


# ---------- FETCH DETAIL ----------
async def fetch(session, sem, ch):

    pid = ch.get("providerContentId")
    name = ch.get("channelName") or ch.get("title") or "Unknown"
    logo = ch.get("logo") or ""
    category = get_category(ch)

    if not pid:
        return None

    try:
        async with sem:
            async with session.get(DETAIL_API.format(pid), timeout=20) as r:
                data = await r.json(content_type=None)

        links = extract_links(data)

        if not links["m3u8"] and not links["mpd"]:
            return None

        return {
            "id": pid,
            "name": name,
            "logo": logo,
            "category": category,
            "m3u8": links["m3u8"],
            "mpd": links["mpd"],
            "license": links["license"]
        }

    except:
        return None


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

            # CHANNEL INFO
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["category"]}",{ch["name"]}\n'
            )

            # M3U8 LINKS
            for u in ch["m3u8"]:
                lines.append(u + "\n")

            # MPD LINKS
            for u in ch["mpd"]:
                lines.append(u + "\n")

            # LICENSE LINKS (metadata only)
            for u in ch["license"]:
                lines.append("# License: " + u + "\n")

        with open("akashdth.m3u", "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"Saved {len(valid)} channels with full streams")


if __name__ == "__main__":
    asyncio.run(main())
