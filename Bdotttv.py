import os
import asyncio
import aiohttp
from datetime import datetime

LIVE_API = os.getenv("LIVE_API")
DETAIL_API = os.getenv("DETAIL_API")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}


# ---------- EXTRACT CHANNELS ----------
def extract_channels(data):
    channels = []

    def walk(obj):
        if isinstance(obj, dict):
            if "contentList" in obj and isinstance(obj["contentList"], list):
                channels.extend(obj["contentList"])

            for v in obj.values():
                walk(v)

        elif isinstance(obj, list):
            for i in obj:
                walk(i)

    walk(data)
    return channels


# ---------- ONLY VLC FRIENDLY STREAM ----------
def get_vlc_streams(obj):
    streams = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)

        elif isinstance(x, list):
            for i in x:
                walk(i)

        elif isinstance(x, str):
            if ".m3u8" in x.lower():
                streams.append(x)

    walk(obj)
    return list(set(streams))


# ---------- CATEGORY ----------
def get_category(ch):
    g = ch.get("genre")
    if isinstance(g, list) and g:
        return g[0]
    return "General"


# ---------- HEADER ----------
def make_header(total):
    now = datetime.now().strftime("%I:%M %p | %d-%b-%Y")

    return f"""#EXTM3U
############################################
#        📡 VLC IPTV CLEAN PLAYLIST
############################################
# 📺 Total Channels : {total}
# 🔥 Mode : VLC / IPTV Compatible ONLY
############################################
# 🕒 Updated : {now}
############################################

"""


# ---------- FETCH ----------
async def fetch(session, sem, ch):

    pid = ch.get("providerContentId")
    name = ch.get("channelName") or ch.get("title") or "Unknown"
    logo = ch.get("logo") or ""
    category = get_category(ch)

    if 
