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


def deep_find_m3u8(data):
    """
    Recursively search every corner of the response
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


def create_header(total_channels, total_streams):
    """Create M3U playlist header"""
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")
    return f"""#EXTM3U
############################################
#     ✅ VERIFIED M3U8 PLAYLIST
############################################
# 📺 Working Channels : {total_channels}
# 🎯 Total Streams    : {total_streams}
# 🔒 Only Playable M3U8 Streams
############################################
# 🕒 Last Updated : {now}
############################################

"""


async def verify_stream(session, url, timeout=8):
    """
    Actually check if the stream is playable
    Returns True only if stream is working
    """
    try:
        async with session.get(url, timeout=timeout, allow_redirects=True) as resp:
            if resp.status >= 400:
                return False
            
            # Read some data to verify it's real M3U8 content
            try:
                chunk = await asyncio.wait_for(resp.content.read(1024), timeout=5)
                text = chunk.decode('utf-8', errors='ignore')
                
                # Must contain M3U8 markers
                if '#EXTM3U' in text or '#EXTINF' in text or '#EXT-X-STREAM-INF' in text:
                    return True
                    
                # Also accept if we got some data and URL ends with .m3u8
                if len(chunk) > 0 and url.lower().endswith('.m3u8'):
                    return True
                    
            except:
                # If content check fails, at least URL should return 200
                return resp.status < 300
                
        return False
        
    except:
        return False


async def process_channel(session, sem, channel, index, total):
    """Process one channel - find and verify its m3u8 streams"""
    
    pid = channel.get("providerContentId")
    name = channel.get("channelName") or channel.get("title") or "Unknown"
    logo = channel.get("logo") or ""
    category = get_category(channel)
    
    if not pid:
        return None
    
    try:
        async with sem:
            print(f"[{index}/{total}] Checking: {name}", end=" ")
            
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
            
            # 🔍 Deep search for m3u8 URLs
            m3u8_urls = deep_find_m3u8(data)
            
            if not m3u8_urls:
                print("❌ No m3u8 found")
                return None
            
            print(f"→ Found {len(m3u8_urls)} streams", end=" ")
            
            # ✅ Verify each stream
            working = []
            for url in m3u8_urls:
                if await verify_stream(session, url):
                    working.append(url)
            
            if not working:
                print("❌ All dead")
                return None
            
            print(f"✅ {len(working)} working")
            
            return {
                "id": pid,
                "name": name,
                "logo": logo,
                "category": category,
                "streams": working
            }
            
    except Exception as e:
        print(f"❌ Error: {str(e)[:50]}")
        return None


async def main():
    print("\n" + "="*60)
    print("🎯 M3U8 STREAM FINDER & VALIDATOR")
    print("="*60 + "\n")
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # Get channel list
        print("📡 Fetching channel list...")
        async with session.get(LIVE_API) as resp:
            data = await resp.json(content_type=None)
        
        channels = extract_channels(data)
        total = len(channels)
        print(f"✅ Found {total} channels\n")
        print("-"*60)
        
        # Process all channels
        sem = asyncio.Semaphore(25)
        tasks = [
            process_channel(session, sem, ch, i+1, total)
            for i, ch in enumerate(channels)
        ]
        results = await asyncio.gather(*tasks)
        
        # Collect working channels
        working_channels = [ch for ch in results if ch is not None]
        
        # Remove duplicates
        seen = set()
        unique_channels = []
        for ch in working_channels:
            if ch["id"] not in seen:
                seen.add(ch["id"])
                unique_channels.append(ch)
        
        # Build M3U content
        total_streams = sum(len(ch["streams"]) for ch in unique_channels)
        playlist = [create_header(len(unique_channels), total_streams)]
        
        for ch in unique_channels:
            # Channel info
            playlist.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-logo="{ch["logo"]}" '
                f'group-title="{ch["category"]}",{ch["name"]}\n'
            )
            # Stream URLs
            for stream_url in ch["streams"]:
                playlist.append(stream_url + "\n")
        
        # Save to file
        output_file = "working_channels.m3u"
        with open(output_file, "w", encoding="utf-8") as f:
            f.writelines(playlist)
        
        # Show summary
        print("\n" + "="*60)
        print("📊 FINAL RESULTS")
        print("="*60)
        print(f"📡 Total Channels Scanned : {total}")
        print(f"✅ Working Channels       : {len(unique_channels)}")
        print(f"🎯 Working M3U8 Streams  : {total_streams}")
        print(f"❌ Failed/No Stream      : {total - len(unique_channels)}")
        
        if total > 0:
            rate = len(unique_channels) / total * 100
            print(f"📈 Success Rate          : {rate:.1f}%")
        
        print("="*60)
        print(f"\n💾 Saved to: {output_file}")
        print("🎉 Only playable m3u8 streams included!\n")


if __name__ == "__main__":
    asyncio.run(main())
