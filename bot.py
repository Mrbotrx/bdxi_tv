import requests
import os
import sys
import base64

# সোর্স লিংকটিকে Base64 দিয়ে এনকোড করে রাখা হয়েছে
ENCODED_URL = b'aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL2FidXNhZWVpZHgvTXJnaWZ5LUJESVgtSVBUVi9yZWZzL2hlYWRzL21haW4vcGxheWxpc3QubTN1'

SOURCE_URL = os.environ.get("SOURCE_PLAYLIST_URL")
if not SOURCE_URL or SOURCE_URL.strip() == "":
    SOURCE_URL = base64.b64decode(ENCODED_URL).decode('utf-8')

def parse_and_filter():
    try:
        print("Fetching source playlist securely...")
        # গিটহাব ব্লক এড়াতে ব্রাউজার হেডার ব্যবহার করা হয়েছে
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(SOURCE_URL, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"Failed to fetch source playlist. Status code: {response.status_code}")
            return
        
        lines = response.text.split('\n')
        new_playlist = ["#EXTM3U"]
        current_info = None
        channel_count = 0
        
        print("Filtering channels (removing promos and .mp4)...")
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
                
                # আমেরিকার আইপি থেকে চেক না করে সরাসরি চ্যানেল অ্যাড হবে (BDIX ব্লকিং এড়াতে)
                if current_info:
                    new_playlist.append(current_info)
                    new_playlist.append(line)
                    channel_count += 1
                
                current_info = None

        # ফাইল রাইট করা
        with open("kbtvpro.m3u8", "w", encoding="utf-8") as f:
            f.write("\n".join(new_playlist))
        print(f"Success! kbtvpro.m3u8 updated with {channel_count} channels.")
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    parse_and_filter()
