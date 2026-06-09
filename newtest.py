import requests

BASE_API = "https://tv.roarzone.net/api/android"
CHANNELS_URL = f"{BASE_API}/channels.php"
STREAM_URL = f"{BASE_API}/stream.php?channel="

OUTPUT_FILE = "ROARZONET.m3u8"


def get_channels():
    try:
        r = requests.get(CHANNELS_URL, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("Error fetching channels:", e)
        return []


def build_stream_url(channel_id):
    return f"{STREAM_URL}{channel_id}"


def generate_m3u(channels):
    lines = ["#EXTM3U"]

    for ch in channels:
        name = ch.get("name", "Unknown")
        cid = ch.get("id") or ch.get("channel_id")

        if not cid:
            continue

        url = build_stream_url(cid)

        lines.append(f'#EXTINF:-1 group-title="ROARZONE",{name}')
        lines.append(url)

    return "\n".join(lines)


def save_file(content):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    print("Fetching channels...")
    channels = get_channels()

    if not channels:
        print("No channels found!")
        exit()

    print(f"Found {len(channels)} channels")

    m3u = generate_m3u(channels)
    save_file(m3u)

    print(f"Saved {OUTPUT_FILE}")
