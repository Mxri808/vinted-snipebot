#!/usr/bin/env python3
"""Diagnose 7: parentId direkt NACH dem Katalog-Slug suchen (RSC-Payload)."""
import re

from curl_cffi import requests


def fetch():
    for versuch in range(12):
        s = requests.Session(
            impersonate="chrome131",
            proxy=f"socks5h://diag7-{versuch}:x@127.0.0.1:9050",
        )
        try:
            r = s.get(
                "https://www.vinted.de/catalog?catalog[]=2632&order=newest_first",
                timeout=60,
            )
        except Exception as e:
            print(f"  Versuch {versuch + 1}: Fehler {e}")
            continue
        print(f"  Versuch {versuch + 1}: status {r.status_code} ({len(r.text)})")
        if r.status_code == 200 and len(r.text) > 500000:
            return r.text
    return None


def main():
    html = fetch()
    # RSC-Payload: "/catalog/ID-slug\",\"order\":...,\"parentId\":NNN
    cats = {}
    for m in re.finditer(r'/catalog/(\d{2,6})-([a-z0-9-]+)', html):
        cid, slug = m.group(1), m.group(2)
        alt = cats.get(cid)
        if alt and alt["parent"]:
            continue
        nach = html[m.end():m.end() + 600]
        pm = re.search(r'parentId\\?":(\d+)', nach)
        dm = re.search(r'depth\\?":(\d+)', nach)
        cats[cid] = {
            "slug": slug,
            "parent": pm.group(1) if pm else (alt["parent"] if alt else None),
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
