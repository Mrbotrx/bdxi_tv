import os
from datetime import datetime
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor


# ================= SETTINGS =================

SOURCE_URLS = [
    os.getenv("KBPROTV"),
    os.getenv("KBPROTV2"),
    os.getenv("ABCD")
]

OUTPUT_FILE = "kbtvpro.m3u8"

DEFAULT_LOGO = (
    "https://raw.githubusercontent.com/Mrbotrx/bdxi_tv/main/assets/default_tv.png"
)


# ================= CHECK STREAM =================

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



# ================= MAIN =================

def fetch_and_filter_playlist():

    all_lines = []


    # ================= LOAD SOURCES =================

    print("Loading sources...")

    for url in SOURCE_URLS:

        if not url:
            print("Missing source")
            continue

        try:

            print("Downloading:", url)

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

                all_lines.extend(
                    r.text.splitlines()
                )


        except Exception as e:

            print(
                "Source error:",
                e
            )



    # ================= EMPTY CHECK =================

    if not all_lines:

        print(
            "No playlist data found"
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



    seen_links = set()

    current_info = None

    channels = []



    # ================= KEYWORDS =================

    KEYWORDS = [

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

        "india",
        "zee",
        "sony",
        "star",
        "colors",

        "sports",
        "sport",
        "cricket",
        "football",
        "fifa",
        "uefa",

        "tsports",
        "star sports",
        "sony sports",
        "espn",
        "bein",
        "sky sports"

    ]



    # ================= PARSE =================

    for line in all_lines:


        line = line.strip()


        if not line:
            continue



        if line.startswith("#EXTINF"):

            current_info = line



        elif line.startswith("http"):


            link = line



            if link in seen_links:

                current_info = None
                continue



            seen_links.add(link)



            if ".mp4" in link.lower():

                current_info = None
                continue



            if (
                ".m3u8" not in link.lower()
                and "live" not in link.lower()
            ):

                current_info = None
                continue



            info = (
                current_info
                if current_info
                else "#EXTINF:-1,Live TV"
            )



            if "tvg-logo" not in info:

                info = info.replace(
                    "#EXTINF:-1",
                    f'#EXTINF:-1 tvg-logo="{DEFAULT_LOGO}"'
                )



            if any(
                k in info.lower()
                for k in KEYWORDS
            ):

                channels.append(
                    (
                        info,
                        link
                    )
                )



            current_info = None




    print(
        "Checking live channels:",
        len(channels)
    )



    # ================= LIVE TEST =================

    final = []

    with ThreadPoolExecutor(
        max_workers=20
    ) as executor:


        results = executor.map(
            check_live_stream,
            channels
        )


        for item in results:

            if item:

                final.append(item)



    # ================= TIME =================


    dhaka = pytz.timezone(
        "Asia/Dhaka"
    )

    now = datetime.now(
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

################################
# IPTV STREAM HUB
# Dev : KB CYBER TEAM
# Updated : {now}
# Total Channels : {len(final)}
################################

"""
        )


        for info, link in final:

            f.write(
                info +
                "\n" +
                link +
                "\n"
            )



    print(
        "DONE Channels:",
        len(final)
    )




# ================= RUN =================

if __name__ == "__main__":

    fetch_and_filter_playlist()
