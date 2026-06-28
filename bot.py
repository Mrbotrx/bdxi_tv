import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import requests
import pytz


# ================= SETTINGS =================

SOURCE_URLS = [
    os.getenv("KBPROTV"),
    os.getenv("KBPROTV2"),
    os.getenv("ABCD")
]

OUTPUT_FILE = "kbtvpro.m3u8"

DEFAULT_LOGO = "https://shorturl.at/Egku0"



# ================= LIVE CHECK =================

def check_live_stream(channel):

    info, link = channel

    if not link or not link.startswith("http"):
        return None

    try:

        r = requests.get(
            link,
            timeout=5,
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if r.status_code in [200, 206, 301, 302]:
            return info, link

    except Exception:
        pass

    return None



# ================= LOAD SOURCE =================

def load_sources():

    lines = []

    for url in SOURCE_URLS:

        if not url:
            print("Missing source")
            continue

        try:

            print("Loading:", url)

            r = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            print(
                "Status:",
                r.status_code
            )

            if r.status_code == 200:

                lines.extend(
                    r.text.splitlines()
                )


        except Exception as e:

            print(
                "Source error:",
                e
            )


    return lines



# ================= BUILD PLAYLIST =================

def build_playlist():


    all_lines = load_sources()


    if not all_lines:

        print("No source data found")

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                "#EXTM3U\n"
                "# No source available\n"
            )

        return



    keywords = [

        "bangla",
        "bangladesh",
        "bd",

        "channel i",
        "ntv",
        "rtv",
        "somoy",
        "jamuna",
        "ekattor",
        "gazi",

        "india",
        "zee",
        "sony",
        "star",
        "colors",

        "sport",
        "sports",
        "cricket",
        "football",
        "fifa",

        "tsports",
        "espn",
        "bein",
        "sky"

    ]


    channels = []

    seen = set()

    current_info = None



    for line in all_lines:

        line = line.strip()


        if not line:
            continue



        if line.startswith("#EXTINF"):

            current_info = line



        elif line.startswith("http"):

            url = line


            if url in seen:
                current_info = None
                continue


            seen.add(url)



            if ".mp4" in url.lower():
                current_info = None
                continue



            info = (
                current_info
                if current_info
                else "#EXTINF:-1,Live TV"
            )



            # Add Logo

            if "tvg-logo" not in info:

                info = info.replace(
                    "#EXTINF:-1",
                    f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}"'
                )



            if any(
                k in info.lower()
                for k in keywords
            ):

                channels.append(
                    (
                        info,
                        url
                    )
                )



            current_info = None



    print(
        "Checking streams:",
        len(channels)
    )



    live_channels = []


    with ThreadPoolExecutor(
        max_workers=20
    ) as executor:


        results = executor.map(
            check_live_stream,
            channels
        )


        for item in results:

            if item:
                live_channels.append(item)



    dhaka = pytz.timezone(
        "Asia/Dhaka"
    )


    update_time = datetime.now(
        dhaka
    ).strftime(
        "%d-%b-%Y %I:%M %p"
    )



    # ================= WRITE =================


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:


        f.write(
f"""#EXTM3U

################################
# IPTV AUTO UPDATE
# Updated: {update_time}
# Total Channels: {len(live_channels)}
################################

"""
        )


        for info, url in live_channels:

            f.write(
                info +
                "\n" +
                url +
                "\n"
            )



    print(
        "DONE:",
        len(live_channels)
    )



# ================= START =================

if __name__ == "__main__":

    build_playlist()
