#!/usr/bin/env python3
"""Diagnose 2: Wo genau steckt favourite_count?"""
import re


def main():
    try:
        html = open("/tmp/cat.html").read()
    except FileNotFoundError:
        print("Bitte erst diag.py laufen lassen")
        return

    print("groesse:", len(html))
    positions = [m.start() for m in re.finditer(r"favourite_count", html)]
    print("Anzahl:", len(positions), "| erste Positionen:", positions[:5])

    if positions:
        p = positions[0]
        print("\n--- Kontext um Vorkommen 1 ---")
        print(repr(html[p - 400:p + 400]))

    # Paare id -> favourite_count im ganzen Dokument?
    pairs = re.findall(r'"id":\s*(\d{7,12})[^{}]{0,600}?"favourite_count":\s*(\d+)', html)
    print("\nid->fav Paare gefunden:", len(pairs))
    print(pairs[:5])

    # Umgekehrte Reihenfolge probieren
    pairs2 = re.findall(r'"favourite_count":\s*(\d+)[^{}]{0,600}?"id":\s*(\d{7,12})', html)
    print("fav->id Paare:", len(pairs2))
    print(pairs2[:5])


if __name__ == "__main__":
    main()
