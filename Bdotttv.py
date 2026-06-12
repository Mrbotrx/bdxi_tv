import asyncio
import aiohttp

LIVE_API = "https://kong.akash-go.com/search-connector/pub/freemium/search/livedata"
DETAIL_API = "https://kong.akash-go.com/content-detail/pub/api/v6/channels/{}"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}


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


async def fetch(session, sem, ch):
    pid = ch.get("providerContentId")
    name = ch.get("channelName") or ch.get("title") or "Unknown"

    if not pid:
        return None

    try:
        async with sem:
            async with session.get(DETAIL_API.format(pid), timeout=20) as r:
                data = await r.json(content_type=None)

        m3u8 = find_m3u8(data)

        if not m3u8:
            return None

        return f'#EXTINF:-1 tvg-id="{pid}",{name}\n{m3u8}\n'

    except:
        return None


async def main():
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(LIVE_API) as r:
            data = await r.json(content_type=None)

        channels = extract_channels(data)

        sem = asyncio.Semaphore(80)

        tasks = [fetch(session, sem, ch) for ch in channels]
        results = await asyncio.gather(*tasks)

        with open("akashdth.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")

            count = 0
            for i in results:
                if i:
                    f.write(i)
                    count += 1

        print(f"Saved {count} channels")


if __name__ == "__main__":
    asyncio.run(main())
