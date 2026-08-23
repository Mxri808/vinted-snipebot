#!/usr/bin/env python3
"""Diagnose 7: parentId direkt NACH dem Katalog-Slug suchen (RSC-Payload)."""
import re

from curl_cffi import requests


def fetch():
    s = requests.Session(
        impersonate="chrome131",
        proxy="socks5h://diag5:x@127.0.0.1:9050",
    )
    r = s.get(
        "https://www.vinted.de/catalog?catalog[]=2632&order=newest_first",
        timeout=90,
    )
    print("fetch status:", r.status_code, "| groesse:", len(r.text))
    return r.text


def main():
    html = fetch()
    # RSC-Payload: "/catalog/ID-slug\",\"order\":...,\"parentId\":NNN
    cats = {}
    for m in re.finditer(r'/catalog/(\d{2,6})-([a-z0-9-]+)', html):
        cid, slug = m.group(1), m.group(2)
        if cid in cats:
            continue
        nach = html[m.end():m.end() + 600]
        pm = re.search(r'parentId\\?":(\d+)', nach)
        dm = re.search(r'depth\\?":(\d+)', nach)
        cats[cid] = {
            "slug": slug,
            "parent": pm.group(1) if pm else None,
            "depth": dm.group(1) if dm else "?",
        }

    mit_parent = {k: v for k, v in cats.items() if v["parent"]}
    print(f"{len(cats)} Kataloge gesamt, {len(mit_parent)} mit parentId\n")

    groups = {}
    for cid, c in mit_parent.items():
        groups.setdefault(c["parent"], []).append((cid, c))

    for parent in sorted(groups, key=int):
        kids = sorted(groups[parent])
        print(f"\n=== parentId {parent} ({len(kids)} Kinder) ===")
        for cid, c in kids[:80]:
            print(f"  {cid:>6} d{c['depth']} {c['slug']}")


if __name__ == "__main__":
    main()
