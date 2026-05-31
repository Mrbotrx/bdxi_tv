import os
from datetime import datetime
import pytz
import requests

# GitHub Secret থেকে সোর্স লিংক নেওয়া হচ্ছে
SOURCE_URL = os.getenv("KBPROTV")
OUTPUT_FILE = "kbtvpro.m3u8"


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
        output_channels = []
        current_info = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                current_info = line
            elif line.startswith("http") or line.startswith("rtmp"):
                # ফিল্টারিং কন্ডিশন (No MP4, No PROMO, Must be M3U8/Live)
                is_mp4 = ".mp4" in line.lower()
                is_promo = (
                    "promo" in line.lower()
                    or (current_info and "promo" in current_info.lower())
                )
                is_m3u8 = ".m3u8" in line.lower() or "live" in line.lower()

                if is_m3u8 and not is_mp4 and not is_promo:
                    if current_info:
                        output_channels.append((current_info, line))
                    else:
                        output_channels.append(
                            (
                                '#EXTINF:-1 tvg-id="" tvg-name="Channel" tvg-logo="",Live Channel',
                                line,
                            )
                        )
                current_info = None

        # বাংলাদেশ সময় (Asia/Dhaka) ফরম্যাট তৈরি
        dhaka_tz = pytz.timezone("Asia/Dhaka")
        current_time = (
            datetime.now(dhaka_tz).strftime("%I:%M %p | %d-%b-%Y") + " (BST)"
        )
        total_channels = len(output_channels)

        # কাস্টম হেডার ডিজাইন তৈরি
        header_content = f"""#EXTM3U
# 📡 IPTV STREAM HUB
# 
# 👨‍💻 Dev : KB CYBER TEAM  
# 🌐 Panel : https://kbtvpro.totalh.net/  
# 💻 GitHub : https://github.com/Mrbotrx  
# 📢 Telegram : https://t.me/KBCYBERTEAM  
# 
# 📺 Channels : {total_channels} CHANNELS LIVE
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
            for info, link in output_channels:
                f.write(f"{info}\n{link}\n")

        print(f"Playlist updated successfully. Total channels: {total_channels}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    fetch_and_filter_playlist()
