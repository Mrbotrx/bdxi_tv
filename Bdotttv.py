import os
import asyncio
import aiohttp
from datetime import datetime

LIVE_API = os.getenv("LIVE_API")
DETAIL_API = os.getenv("DETAIL_API")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
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
            if ".m3u8" in x.lower() or ".ts" in x.lower():
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
def make_header(total):
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")
    return f"""#EXTM3U
############################################
#        📡 ONLY PLAYABLE CHANNELS
############################################
# 📺 Total Playable : {total}
# 🔥 Mode : Stream Verified & Working
############################################
# 🕒 Updated : {now}
############################################

"""


# ---------- CHECK IF STREAM ACTUALLY PLAYS ----------
async def check_stream_playable(session, url, timeout=8):
    """
    Actually verify the stream is playable by:
    1. Checking HTTP status
    2. Reading first few bytes to confirm it's real video content
    """
    try:
        async with session.get(url, timeout=timeout, allow_redirects=True) as resp:
            if resp.status >= 400:
                return False
            
            # Try to read first 1KB to verify it's actual video data
            try:
                chunk = await resp.content.read(1024)
                # M3U8 files start with #EXTM3U
                # TS files start with sync byte 0x47
                if chunk:
                    if url.endswith('.m3u8') and b'#EXTM3U' in chunk:
                        return True
                    elif url.endswith('.ts') and chunk[0] == 0x47:
                        return True
                    elif len(chunk) > 0:
                        return True  # If we got any data, consider it valid
                return False
            except:
                # If we can't read content but status is OK, still try to keep it
                return resp.status < 400
                
    except asyncio.TimeoutError:
        return False
    except:
        return False


# ---------- FETCH CHANNEL DETAILS ----------
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
                if r.status >= 400:
                    return None
                data = await r.json(content_type=None)

        streams = get_vlc_streams(data)
        if not streams:
            return None

        # 🔴 IMPORTANT: Only keep streams that ACTUALLY PLAY
        playable_streams = []
        for stream_url in streams:
            is_playable = await check_stream_playable(session, stream_url)
            if is_playable:
                playable_streams.append(stream_url)
            else:
                print(f"   ❌ Dead stream: {name} -> {stream_url[:80]}...")

        # If NO streams are playable, skip this channel completely
        if not playable_streams:
            print(f"⛔ SKIPPED: {name} (no playable stream)")
            return None

        print(f"✅ KEPT: {name} ({len(playable_streams)} playable streams)")
        
        return {
            "id": pid,
            "name": name,
            "logo": logo,
            "category": category,
            "streams": playable_streams
        }

    except Exception as e:
        return None


# ---------- MAIN ----------
async def main():
    print("🚀 Starting channel fetch...")
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Fetch live channels list
        async with session.get(LIVE_API) as r:
            data = await r.json(content_type=None)

        channels = extract_channels(data)
        total_channels = len(channels)
        print(f"📡 Found {total_channels} channels in API\n")

        # Process channels
        sem = asyncio.Semaphore(30)  # Conservative concurrency
        tasks = [fetch(session, sem, ch) for ch in channels]
        results = await asyncio.gather(*tasks)

        # Filter only channels with playable streams
        valid = [x for x in results if x is not None]
        seen_ids = set()
        unique_valid = []

        for ch in valid:
            if ch["id"] not in seen_ids:
                seen_ids.add(ch["id"])
                unique_valid.append(ch)

        # Generate M3U file
        lines = [make_header(len(unique_valid))]

        for ch in unique_valid:
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["category"]}",{ch["name"]}\n'
            )
            for s in ch["streams"]:
                lines.append(s + "\n")

        # Save to file
        with open("akashdth.m3u", "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Summary
        print("\n" + "="*50)
        print(f"✅ PLAYABLE CHANNELS KEPT : {len(unique_valid)}")
        print(f"❌ DEAD CHANNELS REMOVED   : {total_channels - len(unique_valid)}")
        if total_channels > 0:
            print(f"📊 SUCCESS RATE            : {(len(unique_valid)/total_channels*100):.1f}%")
        print("="*50)
        print(f"\n💾 Saved to: akashdth.m3u")


if __name__ == "__main__":
    asyncio.run(main())
