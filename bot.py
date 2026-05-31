import os
from datetime import datetime
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor

# GitHub Secret থেকে সোর্স লিংক নেওয়া হচ্ছে
SOURCE_URL = os.getenv("KBPROTV")
OUTPUT_FILE = "kbtvpro.m3u8"


def check_live_stream(channel):
    """লিঙ্কটি সচল এবং ফাস্ট কাজ করছে কিনা তা পরীক্ষা করার ফাংশন"""
    info, link = channel
    try:
        # stream চেক করার জন্য ৩ সেকেন্ড টাইমআউট দেওয়া হয়েছে (Fast Link Filter)
        response = requests.head(link, timeout=3.0, allow_redirects=True)
        if response.status_code == 200:
            return info, link
    except requests.RequestException:
        try:
            # HEAD রিকোয়েস্ট ব্লক হলে GET রিকোয়েস্ট দিয়ে শেষবারের মতো চেক করা
            response = requests.get(link, timeout=3.0, stream=True)
            if response.status_code == 200:
                return info, link
        except requests.RequestException:
            pass
    return None


def fetch_and_filter_playlist():
    if not SOURCE_URL:
        print("Error: Source URL not found in Environment Variables!")
        return

    try:
        response = requests.get(SOURCE_URL, timeout=15)
        if response.status_code != 200:
            print("Failed to fetch source playlist.")
            return

        lines = response.text.splitlines()
        
        raw_bd_india_channels = []
        raw_other_channels = []
        current_info = None

        # ১. সোর্স থেকে ডেটা রিড ও প্রোমো/MP4 ফিল্টারিং
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                current_info = line
            elif line.startswith("http") or line.startswith("rtmp"):
                is_mp4 = ".mp4" in line.lower()
                is_promo = (
                    "promo" in line.lower()
                    or (current_info and "promo" in current_info.lower())
                )
                is_m3u8 = ".m3u8" in line.lower() or "live" in line.lower()

                if is_m3u8 and not is_mp4 and not is_promo:
                    channel_meta = current_info if current_info else '#EXTINF:-1 tvg-id="" tvg-name="Channel" tvg-logo="",Live Channel'
                    meta_lower = channel_meta.lower()
                    
                    is_bd_or_in = any(
                        keyword in meta_lower for keyword in [
                            'bd', 'bangla', 'bangladesh', 'india', 'ind ', 'zee', 'star', 'sony', 'colors'
                        ]
                    )

                    if is_bd_or_in:
                        raw_bd_india_channels.append((channel_meta, line))
                    else:
                        raw_other_channels.append((channel_meta, line))

                current_info = None

        # ২. থ্রেড পুল ব্যবহার করে দ্রুত লিঙ্ক চেক করা (Multi-threading Link Checker)
        print("Verifying link status and speed...")
        verified_bd_in = []
        verified_others = []

        # সর্বোচ্চ ২০টি থ্রেড একসাথে লিঙ্ক চেক করবে যাতে দ্রুত কাজ শেষ হয়
        with ThreadPoolExecutor(max_workers=20) as executor:
            bd_in_results = executor.map(check_live_stream, raw_bd_india_channels)
            other_results = executor.map(check_live_stream, raw_other_channels)

        for res in bd_in_results:
            if res: verified_bd_in.append(res)
            
        for res in other_results:
            if res: verified_others.append(res)

        # ফাইনাল সচল প্লেলিস্ট মার্জিং (BD & IN সবার উপরে)
        final_playlist = verified_bd_in + verified_others
        total_channels = len(final_playlist)

        # বাংলাদেশ সময় (Asia/Dhaka) ফরম্যাট তৈরি
        dhaka_tz = pytz.timezone("Asia/Dhaka")
        current_time = (
            datetime.now(dhaka_tz).strftime("%I:%M %p | %d-%b-%Y") + " (BST)"
        )

        # কাস্টম হেডার ডিজাইন তৈরি
        header_content = f"""#EXTM3U
# 📡 IPTV STREAM HUB
# 
# 👨‍💻 Dev : KB CYBER TEAM  
# 🌐 Panel : https://kbtvpro.totalh.net/  
# 💻 GitHub : https://github.com/Mrbotrx  
# 📢 Telegram : https://t.me/KBCYBERTEAM  
# 
# 📺 Channels : {total_channels} CHANNELS ONLINE (SPEED VERIFIED)
# • https://t.me/iptvlinksm3u8  
# • https://t.me/KBCYBERTEAM  
# 
# 🕒 Time : {current_time}  
# 🔄 Status : LIVE / UPDATED  
# 
# 📬 @KBCYBERTEAM 
"""

        # ফাইল রাইট করা
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(header_content)
            for info, link in final_playlist:
                f.write(f"{info}\n{link}\n")

        print(f"Playlist updated. Active channels: {total_channels} (Dead links dropped)")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    fetch_and_filter_playlist()
