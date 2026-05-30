import requests
import os
import sys
import base64

# ১. সোর্স লিংকটিকে Base64 দিয়ে এনকোড করে রাখা হয়েছে (কোডে সরাসরি লিংক দেখা যাবে না)
# এনকোডেড টেক্সট: "aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL2FidXNhZWVpZHgvTXJnaWZ5LUJESVgtSVBUVi9yZWZzL2hlYWRzL21haW4vcGxheWxpc3QubTN1"
ENCODED_URL = b'aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL2FidXNhZWVpZHgvTXJnaWZ5LUJESVgtSVBUVi9yZWZzL2hlYWRzL21haW4vcGxheWxpc3QubTN1'

# ২. প্রথমে GitHub Secret চেক করবে, না পেলে হিডেন লিংকটি ডিকোড করে নেবে
SOURCE_URL = os.environ.get("SOURCE_PLAYLIST_URL")
if not SOURCE_URL or SOURCE_URL.strip() == "":
    SOURCE_URL = base64.b64decode(ENCODED_URL).decode('utf-8')

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
        print("Fetching source playlist securely...")
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
