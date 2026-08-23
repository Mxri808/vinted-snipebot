#!/usr/bin/env python3
"""Diagnose 5: Kompletter Katalogbaum von der Vinted-Startseite."""
import re

from curl_cffi import requests


def main():
    s = requests.Session(
        impersonate="chrome131",
        proxy="socks5h://diag3:x@127.0.0.1:9050",
    )
    r = s.get("https://www.vinted.de/", timeout=90)
    html = r.text
    print("status:", r.status_code, "| groesse:", len(html))

    # Alle Katalog-Eintraege: url mit id + slug, dazu code + parentId im Umfeld
    cats = {}
    for m in re.finditer(r'/catalog/(\d{2,6})-([a-z0-9-]+)', html):
        cid, slug = m.group(1), m.group(2)
        if cid in cats:
            continue
        window = html[max(0, m.start() - 700):m.start() + 900]
        code_m = re.search(r'\\"code\\":\\"([A-Z0-9_]+)\\"', window)
        par_m = re.findall(r'\\"parentId\\":(\d+)', window)
        dep_m = re.search(r'\\"depth\\":(\d+)', window)
        cats[cid] = {
            "slug": slug,
            "code": code_m.group(1) if code_m else "?",
            "parent": par_m[-1] if par_m else "?",
            "depth": dep_m.group(1) if dep_m else "?",
        }

    print(f"{len(cats)} Kataloge\n")
    print(f"{'ID':>6} {'parent':>7} {'dep':>3}  code")
    for cid, c in sorted(cats.items(), key=lambda x: int(x[0])):
        print(f"{cid:>6} {c['parent']:>7} {c['depth']:>3}  {c['code']}")


if __name__ == "__main__":
    main()
