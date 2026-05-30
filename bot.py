import requests
import os
import sys

# GitHub Secret থেকে সোর্স লিংকটি রিড করা হচ্ছে (কোডে লিংক হাইড থাকবে)
SOURCE_URL = os.environ.get("SOURCE_PLAYLIST_URL")

if not SOURCE_URL:
    print("Error: SOURCE_PLAYLIST_URL secret is missing in GitHub Settings!")
    sys.exit(1)

def check_stream(url):
    """স্ট্রিমিং লিংকটি সচল এবং লাইভ কিনা তা পরীক্ষা করে"""
    if ".mp4" in url.lower() or "promo" in url.lower():
        return False
    try:
        # দ্রুত রেসপন্সের জন্য HEAD রিকোয়েস্ট এবং ৩ সেকেন্ড টাইমআউট
        response = requests.head(url, timeout=3, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def parse_and_filter():
    try:
        print("Fetching source playlist...")
        response = requests.get(SOURCE_URL, timeout=10)
        if response.status_code != 200:
            print("Failed to fetch source playlist")
            return
        
        lines = response.text.split('\n')
        new_playlist = ["#EXTM3U"]
        current_info = None
        
        print("Filtering channels (removing promos, .mp4 and dead links)...")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("#EXTINF"):
                current_info = line
            elif line.startswith("http"):
                # প্রোমো বা এমপি৪ শব্দ থাকলে বাদ
                if "promo" in line.lower() or ".mp4" in line.lower():
                    current_info = None
                    continue
                
                # চ্যানেলটি সচল কিনা চেক
                if current_info and check_stream(line):
                    new_playlist.append(current_info)
                    new_playlist.append(line)
                
                current_info = None

        # ফিল্টার করা প্লেলিস্টটি সেভ করা
        with open("playlist.m3u8", "w", encoding="utf-8") as f:
            f.write("\n".join(new_playlist))
        print("playlist.m3u8 updated successfully with fast working channels.")
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    parse_and_filter()
