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


# ---------- EXTRACT ALL STREAMS ----------
def extract_streams(ch):
    hls = ch.get("protectedHlsConsumerUrl")
    dash = ch.get("protectedDashWidevineConsumerUrl")

    streams = []

    if hls:
        streams.append(hls)

    if dash:
        streams.append(dash)

    return streams


# ---------- EXTRACT LICENSE ----------
def extract_license(ch):
    return {
        "widevine": ch.get("dashWidevineLicenseUrl"),
        "fairplay": ch.get("fairplayLicenseUrl")
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
#        📡 STREAM + LICENSE EXTRACTOR
############################################
# 📺 Total Channels : {total}
# 🔥 Mode : FULL (M3U8 + MPD + LICENSE)
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

    streams = extract_streams(ch)
    license_data = extract_license(ch)

    if not pid or not streams:
        return None

    return {
        "id": pid,
        "name": name,
        "logo": logo,
        "category": category,
        "streams": streams,
        "license": license_data
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

            # CHANNEL INFO
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["category"]}",{ch["name"]}\n'
            )

            # STREAM LINKS (M3U8 + MPD)
            for s in ch["streams"]:
                lines.append(f"# STREAM: {s}\n")
                lines.append(s + "\n")

            # LICENSE LINKS (JUST OUTPUT INFO)
            lic = ch["license"]

            if lic.get("widevine"):
                lines.append(f"# WIDEVINE: {lic['widevine']}\n")

            if lic.get("fairplay"):
                lines.append(f"# FAIRPLAY: {lic['fairplay']}\n")

            lines.append("\n")

        with open("akashdth.m3u", "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"Saved {len(valid)} channels (streams + license info)")


if __name__ == "__main__":
    asyncio.run(main())
