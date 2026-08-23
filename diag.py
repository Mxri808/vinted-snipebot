#!/usr/bin/env python3
"""Diagnose 6: Katalogbaum aus der echten Katalogseite gruppieren."""
import re

from curl_cffi import requests


def fetch():
    s = requests.Session(
        impersonate="chrome131",
        proxy="socks5h://diag4:x@127.0.0.1:9050",
    )
    r = s.get(
        "https://www.vinted.de/catalog?catalog[]=2632&order=newest_first",
        timeout=90,
    )
    print("fetch status:", r.status_code, "| groesse:", len(r.text))
    return r.text


def main():
    html = fetch()
    # Alle Katalog-Eintraege mit parentId-Kontext
    cats = {}
    for m in re.finditer(r'/catalog/(\d{2,6})-([a-z0-9-]+)', html):
        cid, slug = m.group(1), m.group(2)
        if cid in cats:
            continue
        window = html[max(0, m.start() - 500):m.start() + 1200]
        par = re.findall(r'"parentId\\?":(\d+)', window)
        par2 = re.findall(r'parentId\\?":(\d+)', window)
        dep = re.search(r'depth\\?":(\d+)', window)
        cats[cid] = {
            "slug": slug,
            "parent": (par + par2)[-1] if (par or par2) else "?",
            "depth": dep.group(1) if dep else "?",
        }

    print(f"{len(cats)} Kataloge\n")
    groups = {}
    for cid, c in cats.items():
        groups.setdefault(c["parent"], []).append((cid, c))

    for parent in sorted(groups, key=lambda x: (x == "?", x)):
        kids = groups[parent]
        print(f"\n=== parentId {parent} ({len(kids)} Kinder) ===")
        for cid, c in sorted(kids)[:60]:
            print(f"  {cid:>6} d{c['depth']} {c['slug']}")


if __name__ == "__main__":
    main()
