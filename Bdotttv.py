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


# ---------- ONLY VLC FRIENDLY STREAM ----------
def get_vlc_streams(obj):
    streams = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)

        elif isinstance(x, list):
            for i in x:
                walk(i)

        elif isinstance(x, str):
            if ".m3u8" in x.lower():
                streams.append(x)

    walk(obj)
    return list(set(streams))


# ---------- CATEGORY ----------
def get_category(ch):
    g = ch.get("genre")
    if isinstance(g, list) and g:
        return g[0]
    return "General"


# ---------- HEADER ----------
def make_header(total, working, failed):
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")

    return f"""#EXTM3U
############################################
#        📡 VLC IPTV CLEAN PLAYLIST
############################################
# 📺 Working Channels : {working}
# ❌ Failed Channels  : {failed}
# 🔥 Mode : Only Working Streams
############################################
# 🕒 Updated : {now}
############################################

"""


# ---------- VALIDATE STREAM (Check if URL is reachable) ----------
async def validate_stream(session, stream_url, timeout=10):
    """Check if the stream URL is actually accessible"""
    try:
        async with session.get(stream_url, timeout=timeout, allow_redirects=True) as resp:
            # Accept 200-399 status codes as valid
            return resp.status < 400
    except:
        return False


# ---------- FETCH ----------
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

        streams = get_vlc_streams(data)

        if not streams:
            return None

        # Filter only working streams
        working_streams = []
        for stream in streams:
            is_valid = await validate_stream(session, stream)
            if is_valid:
                working_streams.append(stream)

        # If no working streams found, skip this channel
        if not working_streams:
            return None

        return {
            "id": pid,
            "name": name,
            "logo": logo,
            "category": category,
            "streams": working_streams
        }

    except:
        return None


# ---------- MAIN ----------
async def main():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(LIVE_API) as r:
            data = await r.json(content_type=None)

        channels = extract_channels(data)
        total_channels = len(channels)

        sem = asyncio.Semaphore(50)  # Reduced to avoid overwhelming the server

        tasks = [fetch(session, sem, ch) for ch in channels]
        results = await asyncio.gather(*tasks)

        valid = [x for x in results if x]
        seen = set()
        
        failed_count = total_channels - len(valid)
        
        lines = [make_header(len(valid), len(valid), failed_count)]

        for ch in valid:
            if ch["id"] in seen:
                continue

            seen.add(ch["id"])

            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["category"]}",{ch["name"]}\n'
            )

            for s in ch["streams"]:
                lines.append(s + "\n")

        with open("akashdth.m3u", "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"✅ Saved {len(valid)} working channels")
        print(f"❌ Failed {failed_count} channels")
        print(f"📊 Success rate: {(len(valid)/total_channels*100):.1f}%" if total_channels > 0 else "No channels found")


if __name__ == "__main__":
    asyncio.run(main())
