import os
import base64
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pytz


# ================= SOURCES =================

SOURCE_URLS = [
    os.getenv("KBPROTV"),
    os.getenv("KBPROTV2"),
    os.getenv("ABCD")
]


OUTPUT_FILE = "kbtvpro.m3u8"


# ================= BASE64 LOGO =================

def decode_b64(data):
    return base64.b64decode(data).decode("utf-8")


DEFAULT_LOGO = decode_b64(
    "aHR0cHM6Ly9zaG9ydHVybC5hdC9FZ2t1MA=="
)

OLD_LOGO = decode_b64(
    "aHR0cHM6Ly9pbWd1ci5jb20vNzlnMmtNQS5wbmc="
)

NEW_LOGO = decode_b64(
    "aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL01yYm90cngvYmR4aV90di9tYWluL2tiY3Rsb2dvLnBuZw=="
)


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}



# ================= FAST LIVE CHECK =================

def check_live_stream(channel):

    info, link = channel

    try:

        r = requests.get(
            link,
            timeout=2,
            headers=HEADERS,
            stream=True
        )

        if r.status_code in [200, 206, 301, 302]:
            return info, link

    except Exception:
        return None

    return None



# ================= LOAD PLAYLIST =================

def load_playlist():

    all_lines = []

    for url in SOURCE_URLS:

        if not url:
            print("Missing source")
            continue


        try:

            print("Loading:", url)


            r = requests.get(
                url,
                timeout=10,
                headers=HEADERS
            )


            if r.status_code == 200:

                lines = r.text.splitlines()

                print(
                    "Loaded:",
                    len(lines)
                )

                all_lines.extend(lines)


        except Exception as e:

            print(
                "Source error:",
                e
            )


    return all_lines
    # ================= BUILD PLAYLIST =================

def build_playlist():

    lines = load_playlist()


    if not lines:

        print(
            "No source available"
        )

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



    KEYWORDS = [

        # Bangladesh

        "bd",
        "bangla",
        "bangladesh",
        "channel i",
        "ntv",
        "rtv",
        "ekattor",
        "somoy",
        "jamuna",
        "gtv",
        "gazi",
        "banglavision",
        "boishakhi",
        "desh tv",


        # India

        "india",
        "zee",
        "star",
        "sony",
        "colors",
        "zee bangla",
        "star plus",
        "sony sab",
        "sun tv",


        # Sports

        "sport",
        "sports",
        "cricket",
        "football",
        "fifa",
        "uefa",
        "tsports",
        "t sports",
        "espn",
        "bein",
        "sky sports"

    ]



    channels = []

    seen = set()

    current_info = None



    for line in lines:

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



            if (
                ".m3u8" not in url.lower()
                and
                "live" not in url.lower()
            ):

                current_info = None
                continue



            info = (
                current_info
                if current_info
                else "#EXTINF:-1,Live TV"
            )



            # ================= LOGO REPLACE =================

            if OLD_LOGO in info:

                info = info.replace(
                    OLD_LOGO,
                    NEW_LOGO
                )



            # Add default logo if missing

            if "tvg-logo" not in info:

                info = info.replace(
                    "#EXTINF:-1",
                    f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}"'
                )



            if any(
                word in info.lower()
                for word in KEYWORDS
            ):

                channels.append(
                    (
                        info,
                        url
                    )
                )



            current_info = None



    print(
        "Filtered channels:",
        len(channels)
    )
        # ================= LIVE CHECK =================

    live_channels = []


    with ThreadPoolExecutor(
        max_workers=100
    ) as executor:


        futures = [

            executor.submit(
                check_live_stream,
                c
            )

            for c in channels

        ]



        for future in as_completed(futures):

            result = future.result()

            if result:

                live_channels.append(result)



    print(
        "Live channels:",
        len(live_channels)
    )



    # ================= TIME =================

    dhaka = pytz.timezone(
        "Asia/Dhaka"
    )


    update_time = datetime.now(
        dhaka
    ).strftime(
        "%I:%M %p | %d-%b-%Y"
    )



    # ================= WRITE =================

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:


        f.write(
f"""#EXTM3U

#################################
# IPTV AUTO UPDATE
# Updated : {update_time}
# Total Live : {len(live_channels)}
#################################

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
        "DONE",
        OUTPUT_FILE
    )



# ================= START =================

if __name__ == "__main__":

    build_playlist()
