#!/usr/bin/env python3
"""Diagnose: Wie ist die Vinted-Katalogseite aufgebaut?"""
import re
from collections import Counter

from curl_cffi import requests


def main():
    s = requests.Session(
        impersonate="chrome131",
        proxy="socks5h://diag1:x@127.0.0.1:9050",
    )
    r = s.get(
        "https://www.vinted.de/catalog?catalog[]=2632&order=newest_first",
        timeout=60,
    )
    html = r.text
    print("status:", r.status_code, "| groesse:", len(html))
    open("/tmp/cat.html", "w").write(html)

    print("favourite_count Vorkommen:", html.count("favourite_count"))

    ids = re.findall(r"product-item-id-(\d+)", html)[:3]
    print("Item-IDs:", ids)

    if ids:
        iid = ids[0]
        i = html.find(f"product-item-id-{iid}")
        window = html[max(0, i - 500):i + 6000]
        favs = re.findall(r'"favourite_count":\s*(\d+)', window)
        print("Favoriten nahe Item 1:", favs[:5])
        keys = re.findall(r'"([a-zA-Z_]{4,30})":', window)
        print("JSON-Keys nahe Item:")
        print([k for k, _ in Counter(keys).most_common(30)])

    blobs = re.findall(r"data-js-react-on-rails-store=\"([^\"]{0,60})", html)
    print("Rails-Store-Attribute:", blobs[:3])

    scripts = len(re.findall(r"<script", html))
    print("Anzahl <script>-Tags:", scripts)


if __name__ == "__main__":
    main()
