#!/usr/bin/env python3
"""Diagnose 4: Herren-Katalog-IDs von vinted.de/herren ziehen."""
import re

from curl_cffi import requests


def main():
    s = requests.Session(
        impersonate="chrome131",
        proxy="socks5h://diag2:x@127.0.0.1:9050",
    )
    r = s.get("https://www.vinted.de/herren", timeout=60)
    print("status:", r.status_code, "| groesse:", len(r.text))
    open("/tmp/herren.html", "w").write(r.text)

    # Katalog-Links: /catalog/ID-slug
    cats = sorted(set(re.findall(r"/catalog/(\d{2,6})-([a-z0-9-]+)", r.text)))
    print(f"\n{len(cats)} Kataloge gefunden:\n")
    for cid, slug in cats:
        print(f"{cid:>6}  {slug}")


if __name__ == "__main__":
    main()
