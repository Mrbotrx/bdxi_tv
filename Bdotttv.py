
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


# ---------- EXTRACT ALL CHANNELS ----------
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


# ---------- FIND ALL m3u8 STREAMS (ONLY m3u8) ----------
def find_all_m3u8(obj):
    streams = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, str):
            # Find ALL m3u8 URLs - চলে বা না চলে সব নিবে
            if ".m3u8" in x.lower():
                streams.append(x)
            # এছাড়া m3u8 ছাড়া অন্য কিছু নিবে না

    walk(obj)
    return list(set(streams))  # Duplicate রিমুভ


# ---------- GET CATEGORY ----------
def get_category(ch):
    g = ch.get("genre")
    if isinstance(g, list) and g:
        return g[0]
    elif isinstance(g, str):
        return g
    return "General"


# ---------- GENERATE M3U HEADER ----------
def make_header(total_channels, total_streams):
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")
    
    return f"""#EXTM3U
############################################
#        📡 IPTV PLAYLIST - ALL m3u8 STREAMS
############################################
# 📺 Total Channels : {total_channels}
# 📊 Total Streams  : {total_streams}
# 🔥 All m3u8 streams included (working or not)
############################################
# 🕒 Updated : {now}
############################################

"""


# ---------- FETCH CHANNEL DETAILS ----------
async def fetch_channel_details(session, sem, channel):
    pid = channel.get("providerContentId")
    name = channel.get("channelName") or channel.get("title") or "Unknown"
    logo = channel.get("logo") or ""
    category = get_category(channel)

    if not pid:
        return None

    async with sem:
        try:
            url = f"{DETAIL_API}?providerContentId={pid}"
            async with session.get(url, headers=HEADERS, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    streams = find_all_m3u8(data)
                    
                    if streams:
                        return {
                            "name": name,
                            "logo": logo,
                            "category": category,
                            "streams": streams  # ALL m3u8 streams
                        }
                    else:
                        print(f"⚠️ No m3u8 found for: {name}")
                else:
                    print(f"⚠️ HTTP {resp.status} for: {name}")
        except Exception as e:
            print(f"❌ Error fetching {name}: {e}")
    
    return None


# ---------- GENERATE FINAL M3U CONTENT ----------
def generate_m3u(channels_data):
    if not channels_data:
        return make_header(0, 0) + "# No m3u8 streams found\n"

    total_streams = sum(len(ch["streams"]) for ch in channels_data)
    m3u = make_header(len(channels_data), total_streams)

    for ch in channels_data:
        name = ch["name"]
        logo = ch["logo"]
        category = ch["category"]
        streams = ch["streams"]

        if len(streams) == 1:
            # Single stream
            m3u += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category}",{name}\n'
            m3u += f'{streams[0]}\n\n'
        else:
            # Multiple streams - numbered
            for idx, stream_url in enumerate(streams, 1):
                m3u += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category}",{name} #{idx}\n'
                m3u += f'{stream_url}\n\n'

    return m3u


# ---------- MAIN FUNCTION ----------
async def main():
    print("=" * 60)
    print("🚀 STARTING IPTV PLAYLIST GENERATOR (ALL m3u8)")
    print("=" * 60)

    # Check API keys
    if not LIVE_API or not DETAIL_API:
        print("❌ ERROR: Missing API keys!")
        print("Please set LIVE_API and DETAIL_API environment variables")
        return

    print(f"📡 LIVE_API: {LIVE_API[:50]}...")
    print(f"📡 DETAIL_API: {DETAIL_API[:50]}...")
    print()

    async with aiohttp.ClientSession() as session:
        try:
            # 1. FETCH LIVE CHANNELS
            print("📥 Fetching live channels...")
            async with session.get(LIVE_API, headers=HEADERS, timeout=30) as resp:
                if resp.status != 200:
                    print(f"❌ Failed to fetch live channels: HTTP {resp.status}")
                    return
                live_data = await resp.json()

            # 2. EXTRACT CHANNELS
            channels = extract_channels(live_data)
            print(f"✅ Found {len(channels)} total channels")
            print()

            if not channels:
                print("⚠️ No channels found!")
                with open("akashdth.m3u", "w", encoding="utf-8") as f:
                    f.write(generate_m3u([]))
                return

            # 3. FETCH DETAILS FOR EACH CHANNEL
            print("🔄 Fetching details for each channel...")
            sem = asyncio.Semaphore(10)  # Limit concurrent requests
            
            tasks = [fetch_channel_details(session, sem, ch) for ch in channels]
            results = await asyncio.gather(*tasks)

            # 4. FILTER VALID CHANNELS (যেগুলোতে m3u8 আছে)
            valid_channels = [r for r in results if r is not None]
            print(f"✅ Found {len(valid_channels)} channels with m3u8 streams")

            # Count total streams
            total_streams = sum(len(ch["streams"]) for ch in valid_channels)
            print(f"📊 Total m3u8 streams found: {total_streams}")
            print()

            # 5. GENERATE M3U CONTENT
            print("📝 Generating M3U playlist...")
            m3u_content = generate_m3u(valid_channels)

            # 6. WRITE TO FILE
            with open("akashdth.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"✅ Playlist saved to: akashdth.m3u")
            print(f"📺 Channels with m3u8: {len(valid_channels)}")
            print(f"🎬 Total m3u8 streams: {total_streams}")
            print("=" * 60)
            print("✨ DONE!")

        except Exception as e:
            print(f"❌ Critical error: {e}")
            # Still create a file with error message
            with open("akashdth.m3u", "w", encoding="utf-8") as f:
                f.write(f"#EXTM3U\n# Error: {e}\n")


# ---------- RUN ----------
if __name__ == "__main__":
    asyncio.run(main())
