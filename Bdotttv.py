import os
import re
import asyncio
import aiohttp
from datetime import datetime
import time

# API endpoints from environment variables
LIVE_API = os.getenv("LIVE_API")
DETAIL_API = os.getenv("DETAIL_API")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

# DRM keywords for URL check only
DRM_KEYWORDS = [
    'drm', 'license', 'widevine', 'fairplay', 'playready',
    'key', 'token', 'auth', 'sign', 'signature', 'expires',
    'kid', 'pssh', 'decrypt', 'encrypted', 'protection'
]


def quick_extract_channels(data):
    """Fast channel extraction"""
    channels = []
    try:
        if isinstance(data, dict):
            for key in ['contentList', 'channels', 'data', 'items']:
                if key in data and isinstance(data[key], list):
                    channels = data[key]
                    break
        elif isinstance(data, list):
            channels = data
    except:
        pass
    return channels


def quick_find_m3u8(text):
    """Fast regex-based m3u8 URL finder"""
    if isinstance(text, str):
        return re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', text)
    return []


def separate_streams(urls):
    """Separate clean and DRM streams"""
    clean = []
    drm = []
    for url in urls:
        url_lower = url.lower()
        if any(keyword in url_lower for keyword in DRM_KEYWORDS):
            drm.append(url)
        else:
            clean.append(url)
    return clean, drm


def get_category(ch):
    """Get category fast"""
    genre = ch.get("genre")
    return genre[0] if (isinstance(genre, list) and genre) else "General"


def create_header(total, clean_count, drm_count, elapsed):
    """Create M3U header"""
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")
    return f"""#EXTM3U
############################################
#     📺 ALL CHANNELS - NO ONE LEFT
############################################
# 📺 Total Channels : {total}
# ✅ Clean Streams  : {clean_count}
# ⚠️ DRM Streams    : {drm_count}
# ⚡ Time : {elapsed:.1f}s
# 🕒 {now}
############################################

"""


async def fetch_all_channels(session, channels):
    """
    FAST: Fetch ALL channels - NONE skipped
    """
    sem = asyncio.Semaphore(100)
    
    async def fetch_one(ch, idx):
        pid = ch.get("providerContentId") or ch.get("id")
        name = ch.get("channelName") or ch.get("title") or f"Channel_{idx}"
        
        # Default channel data (even if no PID or error)
        default = {
            "id": pid or f"unknown_{idx}",
            "name": name,
            "logo": ch.get("logo") or "",
            "category": get_category(ch),
            "streams": [],
            "drm_streams": [],
            "status": "error"
        }
        
        if not pid:
            default["status"] = "no_id"
            return default
        
        try:
            url = DETAIL_API.format(pid)
            async with sem:
                async with session.get(url, timeout=10) as resp:
                    if resp.status >= 400:
                        default["status"] = f"http_{resp.status}"
                        return default
                    
                    text = await resp.text()
                    all_urls = quick_find_m3u8(text)
                    
                    if not all_urls:
                        default["status"] = "no_m3u8"
                        return default
                    
                    # Separate clean and DRM
                    clean, drm = separate_streams(all_urls)
                    
                    return {
                        "id": pid,
                        "name": name,
                        "logo": ch.get("logo") or "",
                        "category": get_category(ch),
                        "streams": clean,
                        "drm_streams": drm,
                        "status": "ok"
                    }
        except:
            default["status"] = "timeout"
            return default
    
    # Process ALL channels
    tasks = [fetch_one(ch, i) for i, ch in enumerate(channels)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter exceptions but keep all valid results
    final = []
    for r in results:
        if isinstance(r, dict):
            final.append(r)
        elif not isinstance(r, Exception):
            final.append(r)
    
    return final


async def main():
    start_time = time.time()
    
    print("\n" + "="*60)
    print("📺 ALL CHANNELS - 100% OUTPUT GUARANTEED")
    print("="*60 + "\n")
    
    # Connection pooling for speed
    connector = aiohttp.TCPConnector(
        limit=200,
        limit_per_host=100,
        ttl_dns_cache=300,
        use_dns_cache=True,
        force_close=False
    )
    
    timeout = aiohttp.ClientTimeout(
        total=20,
        connect=5,
        sock_read=10
    )
    
    async with aiohttp.ClientSession(
        headers=HEADERS,
        connector=connector,
        timeout=timeout
    ) as session:
        
        # Step 1: Fetch channel list
        print("📡 Fetching channels...")
        async with session.get(LIVE_API) as resp:
            data = await resp.json(content_type=None)
        
        channels = quick_extract_channels(data)
        total_input = len(channels)
        print(f"✅ Found {total_input} channels\n")
        
        # Step 2: Process ALL channels
        print(f"⚡ Processing ALL {total_input} channels...")
        results = await fetch_all_channels(session, channels)
        
        # Step 3: Statistics (no dedup, keep ALL)
        total_clean = sum(len(ch["streams"]) for ch in results)
        total_drm = sum(len(ch["drm_streams"]) for ch in results)
        
        ok_count = sum(1 for ch in results if ch["status"] == "ok")
        error_count = sum(1 for ch in results if ch["status"] != "ok")
        
        # Step 4: Build M3U content
        elapsed = time.time() - start_time
        lines = [create_header(len(results), total_clean, total_drm, elapsed)]
        
        for ch in results:
            name = ch["name"]
            status = ch["status"]
            
            if status == "ok":
                if ch["drm_streams"]:
                    # Channel with some DRM
                    lines.append(
                        f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                        f'tvg-logo="{ch["logo"]}" '
                        f'group-title="{ch["category"]}",'
                        f'⚠️ {name} [DRM:{len(ch["drm_streams"])}]\n'
                    )
                else:
                    # Clean channel
                    lines.append(
                        f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                        f'tvg-logo="{ch["logo"]}" '
                        f'group-title="{ch["category"]}",{name}\n'
                    )
                
                # Add clean streams
                for url in ch["streams"]:
                    lines.append(url + "\n")
                    
                # Comment out DRM streams
                for url in ch["drm_streams"]:
                    lines.append(f"#DRM:{url}\n")
                    
            elif status == "no_m3u8":
                lines.append(
                    f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                    f'tvg-logo="{ch["logo"]}" '
                    f'group-title="{ch["category"]}",'
                    f'❌ {name} [No m3u8]\n'
                )
                
            elif status in ["error", "timeout"]:
                lines.append(
                    f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                    f'tvg-logo="{ch["logo"]}" '
                    f'group-title="{ch["category"]}",'
                    f'💥 {name} [Error]\n'
                )
                
            else:
                lines.append(
                    f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                    f'tvg-logo="{ch["logo"]}" '
                    f'group-title="{ch["category"]}",'
                    f'❓ {name} [{status}]\n'
                )
        
        # Step 5: Save file
        with open("all_channels.m3u", "w", encoding="utf-8", buffering=8192) as f:
            f.write(''.join(lines))
        
        # Summary
        print("\n" + "="*60)
        print(f"⚡ Completed in {elapsed:.1f} seconds!")
        print("="*60)
        print(f"📺 Total Channels in Output : {len(results)} (100%)")
        print(f"✅ OK with m3u8            : {ok_count}")
        print(f"⚠️  No m3u8/Error          : {error_count}")
        print(f"🎯 Clean Streams           : {total_clean}")
        print(f"🛡️ DRM Streams (commented) : {total_drm}")
        print("="*60)
        print(f"\n💾 Saved: all_channels.m3u")
        print("🎉 100% channels included - NO ONE LEFT BEHIND!\n")


if __name__ == "__main__":
    asyncio.run(main())

def has_drm_protection(stream_url):
    """
    Check if stream URL or its parameters contain DRM indicators
    """
    url_lower = stream_url.lower()
    
    for keyword in DRM_KEYWORDS:
        if keyword in url_lower:
            return True
    
    return False


def is_clean_stream(stream_url, license_keys):
    """
    Determine if stream is clean (no DRM) or protected
    """
    # Check URL itself for DRM keywords
    if has_drm_protection(stream_url):
        return False
    
    # Check if any license key is related to this stream
    stream_domain = re.findall(r'https?://([^/]+)', stream_url)
    if stream_domain:
        domain = stream_domain[0]
        for key in license_keys:
            if domain in key:
                return False
    
    return True


def extract_channels(data):
    """Extract channel list from API response"""
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


def get_category(ch):
    """Get channel category"""
    genre = ch.get("genre")
    if isinstance(genre, list) and genre:
        return genre[0]
    return "General"


def create_header(total_channels, total_streams, drm_blocked):
    """Create M3U playlist header"""
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")
    return f"""#EXTM3U
############################################
#     📺 CLEAN M3U8 PLAYLIST
#     🚫 DRM/License Protected = REMOVED
############################################
# 📺 Total Channels     : {total_channels}
# 🎯 Clean M3U8 Streams : {total_streams}
# 🛡️ DRM Blocked        : {drm_blocked}
############################################
# 🕒 Last Updated : {now}
############################################

"""


async def process_channel(session, sem, channel, index, total):
    """Process one channel - find m3u8 streams and filter out DRM"""
    
    pid = channel.get("providerContentId")
    name = channel.get("channelName") or channel.get("title") or "Unknown"
    logo = channel.get("logo") or ""
    category = get_category(channel)
    
    if not pid:
        return None
    
    try:
        async with sem:
            print(f"[{index}/{total}] Processing: {name}", end=" ")
            
            # Fetch channel details
            async with session.get(DETAIL_API.format(pid), timeout=25) as resp:
                if resp.status >= 400:
                    print("❌ API Error")
                    return None
                
                try:
                    data = await resp.json(content_type=None)
                except:
                    text = await resp.text()
                    data = text  # Fallback to raw text
            
            # 🔍 Find all m3u8 URLs
            all_m3u8 = deep_find_m3u8(data)
            
            # 🔑 Find any license keys or DRM info
            license_keys = deep_find_license_keys(data)
            
            if not all_m3u8:
                print("❌ No m3u8")
                return None
            
            # 🚫 Filter out DRM-protected streams
            clean_streams = []
            drm_streams = []
            
            for stream_url in all_m3u8:
                if is_clean_stream(stream_url, license_keys):
                    clean_streams.append(stream_url)
                else:
                    drm_streams.append(stream_url)
            
            # Status display
            if clean_streams and drm_streams:
                print(f"⚠️ {len(clean_streams)} clean + {len(drm_streams)} DRM blocked")
            elif clean_streams:
                print(f"✅ {len(clean_streams)} clean")
            else:
                print(f"🚫 ALL DRM ({len(drm_streams)}) - Skipping")
                return None
            
            return {
                "id": pid,
                "name": name,
                "logo": logo,
                "category": category,
                "streams": clean_streams,
                "drm_count": len(drm_streams),
                "license_keys": license_keys
            }
            
    except Exception as e:
        print(f"❌ Error: {str(e)[:50]}")
        return None


async def main():
    print("\n" + "="*70)
    print("🎯 M3U8 CLEANER - Keep All m3u8 But Remove DRM/License")
    print("="*70 + "\n")
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Get channel list
        print("📡 Fetching channel list...")
        async with session.get(LIVE_API) as resp:
            data = await resp.json(content_type=None)
        
        channels = extract_channels(data)
        total = len(channels)
        print(f"✅ Found {total} channels\n")
        print("-"*70)
        
        # Process all channels
        sem = asyncio.Semaphore(25)
        tasks = [
            process_channel(session, sem, ch, i+1, total)
            for i, ch in enumerate(channels)
        ]
        results = await asyncio.gather(*tasks)
        
        # Collect channels with clean streams
        processed_channels = [ch for ch in results if ch is not None]
        
        # Remove duplicates
        seen = set()
        unique_channels = []
        for ch in processed_channels:
            if ch["id"] not in seen:
                seen.add(ch["id"])
                unique_channels.append(ch)
        
        # Calculate statistics
        total_clean_streams = sum(len(ch["streams"]) for ch in unique_channels)
        total_drm_blocked = sum(ch["drm_count"] for ch in unique_channels)
        channels_with_drm = [ch for ch in unique_channels if ch["drm_count"] > 0]
        channels_completely_blocked = total - len(unique_channels)
        
        # Build M3U content
        playlist = [create_header(len(unique_channels), total_clean_streams, total_drm_blocked)]
        
        for ch in unique_channels:
            # Add comment if channel had some DRM blocked streams
            if ch["drm_count"] > 0:
                playlist.append(f'## Note: {ch["drm_count"]} DRM streams removed from {ch["name"]}\n')
            
            # Channel info
            playlist.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["category"]}",{ch["name"]}\n'
            )
            
            # Clean stream URLs only
            for stream_url in ch["streams"]:
                playlist.append(stream_url + "\n")
        
        # Save to file
        output_file = "clean_no_drm.m3u"
        with open(output_file, "w", encoding="utf-8") as f:
            f.writelines(playlist)
        
        # Show detailed summary
        print("\n" + "="*70)
        print("📊 DETAILED RESULTS")
        print("="*70)
        print(f"📡 Total Channels Scanned      : {total}")
        print(f"✅ Channels with Clean Streams : {len(unique_channels)}")
        print(f"⛔ Channels Completely Blocked  : {channels_completely_blocked}")
        print(f"🎯 Total Clean M3U8 Streams    : {total_clean_streams}")
        print(f"🛡️ Total DRM Streams Blocked   : {total_drm_blocked}")
        
        if channels_with_drm:
            print(f"\n📋 Channels with partial DRM ({len(channels_with_drm)}):")
            for ch in channels_with_drm[:5]:  # Show first 5
                print(f"   ⚠️ {ch['name']}: {ch['drm_count']} DRM blocked")
                if ch.get('license_keys'):
                    print(f"      🔑 License: {ch['license_keys'][0][:60]}...")
            if len(channels_with_drm) > 5:
                print(f"   ... and {len(channels_with_drm) - 5} more")
        
        print("="*70)
        print(f"\n💾 Saved to: {output_file}")
        print("✅ All m3u8 streams kept EXCEPT DRM/License protected ones!\n")


if __name__ == "__main__":
    asyncio.run(main())
