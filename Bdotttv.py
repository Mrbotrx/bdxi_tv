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


# ---------- FIND ALL VLC FRIENDLY STREAMS ----------
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
    return list(set(streams))  # Remove duplicates


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
#        📡 VLC IPTV CLEAN PLAYLIST
############################################
# 📺 Total Channels : {total}
# 🔥 Mode : VLC / IPTV Compatible ONLY
# 📌 All m3u8 streams included
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

    async with sem:
        try:
            url = f"{DETAIL_API}?providerContentId={pid}"
            async with session.get(url, headers=HEADERS) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    streams = get_vlc_streams(data)
                    if streams:
                        return {
                            "name": name,
                            "logo": logo,
                            "category": category,
                            "streams": streams  # ALL streams found
                        }
        except Exception as e:
            print(f"Error fetching {name}: {e}")
    return None


# ---------- GENERATE M3U WITH ALL STREAMS ----------
def generate_m3u(channels_data):
    if not channels_data:
        return ""

    m3u = make_header(len(channels_data))

    for ch in channels_data:
        name = ch["name"]
        logo = ch["logo"]
        category = ch["category"]
        streams = ch["streams"]  # All streams

        # Add each stream with a suffix
        if len(streams) == 1:
            # Single stream - normal entry
            m3u += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category}",{name}\n'
            m3u += f"{streams[0]}\n\n"
        else:
            # Multiple streams - add each with quality/source indicator
            for idx, stream_url in enumerate(streams, 1):
                # Try to extract quality from URL
                quality = "Unknown"
                if "480" in stream_url or "360" in stream_url:
                    quality = "SD"
                elif "720" in stream_url:
                    quality = "HD"
                elif "1080" in stream_url:
                    quality = "FHD"
                elif "4k" in stream_url.lower() or "2160" in stream_url:
                    quality = "4K"
                
                # Add stream number or quality to name
                stream_name = f"{name} [{quality}]" if quality != "Unknown" else f"{name} #{idx}"
                
                m3u += f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category}",{stream_name}\n'
                m3u += f"{stream_url}\n\n"

    return m3u


# ---------- MAIN ----------
async def main():
    if not LIVE_API or not DETAIL_API:
        print("Missing API keys")
        return

    async with aiohttp.ClientSession() as session:
        try:
            # Fetch live channels
            async with session.get(LIVE_API, headers=HEADERS) as resp:
                if resp.status != 200:
                    print(f"Failed to fetch live: {resp.status}")
                    return
                live_data = await resp.json()

            channels = extract_channels(live_data)
            print(f"Found {len(channels)} channels")

            if not channels:
                print("No channels found")
                return

            # Process channels with semaphore
            sem = asyncio.Semaphore(10)
            tasks = [fetch(session, sem, ch) for ch in channels]
            results = await asyncio.gather(*tasks)

            # Filter out None results
            valid_channels = [r for r in results if r is not None]
            print(f"Valid channels: {len(valid_channels)}")

            # Count total streams
            total_streams = sum(len(ch["streams"]) for ch in valid_channels)
            print(f"Total streams found: {total_streams}")

            # Generate M3U
            m3u_content = generate_m3u(valid_channels)

            # Write to file
            with open("akashdth.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            print(f"Playlist saved with {len(valid_channels)} channels and {total_streams} streams")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
