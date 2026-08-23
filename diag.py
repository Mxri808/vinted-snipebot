#!/usr/bin/env python3
"""Diagnose 3: Kontext der echten favourite_count-Daten."""
import re


def main():
    html = open("/tmp/cat.html").read()
    positions = [m.start() for m in re.finditer(r"favourite_count", html)]
    print("Anzahl:", len(positions))

    for p in positions[3:6]:
        print(f"\n--- Position {p} ---")
        print(repr(html[p - 500:p + 300]))

    # Versuche id->fav Paarungen in verschiedenen Formaten
    tests = [
        (r'"id":(\d{7,12}).{0,2000}?"favourite_count":(\d+)', "id dann fav"),
        (r'"favourite_count":(\d+).{0,2000}?"id":(\d{7,12})', "fav dann id"),
        (r'\\?"id\\?":\s*\\?(\d{7,12})\\?.{0,2000}?\\?"favourite_count\\?":\s*\\?(\d+)', "escaped"),
    ]
    for pat, label in tests:
        m = re.findall(pat, html)
        print(f"\n{label}: {len(m)} Treffer")
        if m:
            print(m[:4])
            break


if __name__ == "__main__":
    main()
