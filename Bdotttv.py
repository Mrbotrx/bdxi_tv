import os
import re
import asyncio
import aiohttp
from datetime import datetime

# API endpoints from environment variables
LIVE_API = os.getenv("LIVE_API")
DETAIL_API = os.getenv("DETAIL_API")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

# DRM/License related keywords to detect
DRM_KEYWORDS = [
    'drm', 'license', 'widevine', 'fairplay', 'playready',
    'key', 'token', 'auth', 'sign', 'signature', 'expires',
    'session', 'kid', 'pssh', 'decrypt', 'encrypted',
    'protection', 'rights', 'permission', 'verify'
]


def deep_find_m3u8(data):
    """
    Recursively search everywhere in the response
    to find ALL .m3u8 URLs
    """
    urls = set()
    
    def search(obj):
        if isinstance(obj, str):
            # Find m3u8 URLs in strings
            found = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', obj)
            urls.update(found)
            
        elif isinstance(obj, dict):
            for v in obj.values():
                search(v)
                
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                search(item)
    
    search(data)
    return list(urls)


def deep_find_license_keys(data):
    """
    Find any DRM license keys, tokens, or protected content indicators
    """
    keys = []
    
    def search(obj, path=""):
        if isinstance(obj, str):
            # Check if string contains license key patterns
            if any(keyword in obj.lower() for keyword in ['license', 'widevine', 'drm', 'fairplay', 'playready', 'pssh', 'kid']):
                # Extract actual URLs or keys
                urls = re.findall(r'https?://[^\s"\'<>]+', obj)
                keys.extend(urls)
                
                # Also check for base64 encoded keys
                base64_keys = re.findall(r'[A-Za-z0-9+/=]{32,}', obj)
                keys.extend(base64_keys)
                
        elif isinstance(obj, dict):
            # Check for known DRM field names
            for k, v in obj.items():
                if any(drm in k.lower() for drm in ['license', 'drm', 'key', 'widevine', 'pssh', 'kid', 'token', 'protection']):
                    if isinstance(v, str):
                        keys.append(f"{k}: {v}")
                search(v, f"{path}.{k}")
                
        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                search(item, f"{path}[{i}]")
    
    search(data)
    return keys


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
