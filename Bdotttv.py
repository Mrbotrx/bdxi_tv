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


def make_header(total_channels, total_streams):
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")
    return f"""#EXTM3U
# Playlist: akashdth
# Channels: {total_channels}
# Streams: {total_streams}
# Updated: {now}

"""


async def fetch(session, sem, ch):
    pid = ch.get("providerContentId")
    name = ch.get("channelName") or ch.get("title") or "Unknown"
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
                        return {"name": name, "streams": streams}
        except Exception as e:
            print(f"Error fetching {name}: {e}")
    return None


def generate_m3u(channels_data):
    if not channels_data:
        # ফাইল খালি থাকলেও হেডার দিয়ে তৈরি করি
        return make_header(0, 0)

    total_streams = sum(len(ch["streams"]) for ch in channels_data)
    m3u = make_header(len(channels_data), total_streams)

    for ch in channels_data:
        name = ch["name"]
        streams = ch["streams"]
        if len(streams) == 1:
            m3u += f'#EXTINF:-1,{name}\n{streams[0]}\n\n'
        else:
            for idx, url in enumerate(streams, 1):
                m3u += f'#EXTINF:-1,{name} #{idx}\n{url}\n\n'
    return m3u


async def main():
    print("=== Starting IPTV playlist generation ===")
    if not LIVE_API or not DETAIL_API:
        print("ERROR: Missing API keys")
        return

    async with aiohttp.ClientSession() as session:
        try:
            # 1. Fetch live channels
            print(f"Fetching live channels from {LIVE_API}")
            async with session.get(LIVE_API, headers=HEADERS) as resp:
                if resp.status != 200:
                    print(f"Failed to fetch live: {resp.status}")
                    return
                live_data = await resp.json()

            channels = extract_channels(live_data)
            print(f"Found {len(channels)} channels")

            if not channels:
                print("No channels found – generating empty playlist")
                with open("akashdth.m3u", "w", encoding="utf-8") as f:
                    f.write(generate_m3u([]))
                return

            # 2. Fetch details for each channel
            sem = asyncio.Semaphore(10)
            tasks = [fetch(session, sem, ch) for ch in channels]
            results = await asyncio.gather(*tasks)

            valid = [r for r in results if r is not None]
            print(f"Valid channels with streams: {len(valid)}")

            # 3. Generate and write file
            m3u_content = generate_m3u(valid)
            with open("akashdth.m3u", "w", encoding="utf-8") as f:
                f.write(m3u_content)

            total_streams = sum(len(ch["streams"]) for ch in valid)
            print(f"Written {len(valid)} channels, {total_streams} streams to akashdth.m3u")

        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            # তবুও একটি খালি ফাইল তৈরি করি যাতে workflow fail না করে
            with open("akashdth.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n# Error occurred during generation\n")


if __name__ == "__main__":
    asyncio.run(main())
