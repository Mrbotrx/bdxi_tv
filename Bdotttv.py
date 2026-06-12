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
            for item in obj:
                walk(item)

    walk(data)
    return channels


async def fetch_channel(session, ch, sem):
    pid = ch.get("providerContentId")

    if not pid:
        return None

    name = ch.get("channelName") or ch.get("title") or f"CH-{pid}"

    try:
        async with sem:
            async with session.get(
                DETAIL_API.format(pid),
                timeout=15
            ) as r:

                detail = await r.json(
                    content_type=None
                )

        m3u8 = find_m3u8(detail)

        if not m3u8:
            return None

        return (
            f'#EXTINF:-1 tvg-id="{pid}" '
            f'tvg-name="{name}",{name}\n'
            f'{m3u8}\n'
        )

    except Exception:
        return None


async def main():

    connector = aiohttp.TCPConnector(
        limit=200,
        ssl=False
    )

    async with aiohttp.ClientSession(
        headers=HEADERS,
        connector=connector
    ) as session:

        async with session.get(LIVE_API) as r:
            data = await r.json(content_type=None)

        channels = extract_channels(data)

        print(f"Found {len(channels)} channels")

        sem = asyncio.Semaphore(100)

        tasks = [
            fetch_channel(session, ch, sem)
            for ch in channels
        ]

        results = await asyncio.gather(*tasks)

        with open(
            "akashdth.m3u",
            "w",
            encoding="utf-8"
        ) as f:

            f.write("#EXTM3U\n")

            for item in results:
                if item:
                    f.write(item)

        total = sum(
            1 for x in results if x
        )

        print(
            f"Saved {total} channels -> akashdth.m3u"
        )


if __name__ == "__main__":
    asyncio.run(main())
