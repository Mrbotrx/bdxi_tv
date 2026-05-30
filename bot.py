import requests
import os
import sys
import base64

# সোর্স লিংকটিকে Base64 দিয়ে এনকোড করে রাখা হয়েছে (কোডে সরাসরি লিংক দেখা যাবে না)
ENCODED_URL = b'aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL2FidXNhZWVpZHgvTXJnaWZ5LUJESVgtSVBUVi9yZWZzL2hlYWRzL21haW4vcGxheWxpc3QubTN1'

SOURCE_URL = os.environ.get("SOURCE_PLAYLIST_URL")
if not SOURCE_URL or SOURCE_URL.strip() == "":
    SOURCE_URL = base64.b64decode(ENCODED_URL).decode('utf-8')

def check_stream(url):
    """লিংকটি লাইভ এবং সচল কিনা তা দ্রুত পরীক্ষা করে"""
    if ".mp4" in url.lower() or "promo" in url.lower():
        return False
    try:
        # দ্রুত রেসপন্সের জন্য HEAD এবং GET রিকোয়েস্টের কম্বিনেশন ৩ সেকেন্ড টাইমআউটে
        session = requests.Session()
        response = session.head(url, timeout=3, allow_redirects=True)
        
        # যদি HEAD রিকোয়েস্ট সফল হয় (200 OK)
        if response.status_code == 200:
            return True
            
        # কিছু বিডিআইএক্স সার্ভার HEAD রিকোয়েস্ট ব্লক করে, তাদের জন্য GET ট্রাই করবে
        response = session.get(url, timeout=3, stream=True)
        if response.status_code == 200:
            return True
        return False
    except:
        return False

def parse_and_filter():
    try:
        print("Fetching source playlist securely...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(SOURCE_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            print("Failed to fetch source playlist")
            return
        
        lines = response.text.split('\n')
        new_playlist = ["#EXTM3U"]
        current_info = None
        
        print("Filtering live and fast working BDIX channels...")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("#EXTINF"):
                current_info = line
            elif line.startswith("http"):
                # প্রোমো বা এমপি৪ থাকলে শুরুতেই বাদ
                if "promo" in line.lower() or ".mp4" in line.lower():
                    current_info = None
                    continue
                
                # লাইভ চ্যানেল চেক
                if current_info and check_stream(line):
                    new_playlist.append(current_info)
                    new_playlist.append(line)
                    print(f"Added working channel: {line[:40]}...")
                
                current_info = None

        # ফাইনাল আউটপুট kbtvpro.m3u8 ফাইলে সেভ
        with open("kbtvpro.m3u8", "w", encoding="utf-8") as f:
            f.write("\n".join(new_playlist))
        print("kbtvpro.m3u8 updated successfully with verified live channels.")
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    parse_and_filter()
