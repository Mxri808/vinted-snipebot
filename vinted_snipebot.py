#!/usr/bin/env python3
"""
Vinted Snipebot v2 - Clean Rewrite
- Tor Proxy fuer alle Requests
- Neue Tor-Session bei Cloudflare-Block
- Telegram mit Fotos
"""

import html as html_mod
import json
import random
import re
import signal
import time
from datetime import datetime
from pathlib import Path

import requests
from curl_cffi import requests as cffi_requests

BASE = Path(__file__).parent
CONFIG_FILE = BASE / "config.json"
SEEN_FILE = BASE / "seen_items.json"
TOR_PROXY = "socks5h://127.0.0.1:9050"

# Kategorien: name -> (vinted catalog ids, max price EUR)
CATEGORIES = {
    "schuhe": {
        "ids": ["2632", "543", "1049", "2630", "215", "1242", "1452", "1233"],
        "max_price": 50,
    },
    "hosen_jeans": {
        "ids": ["9", "183"],
        "max_price": 30,
    },
    "oberteile": {
        "ids": ["12"],
        "max_price": 15,
    },
}

SIZE_KEYS = {
    "schuhe": ["damen_schuhe", "herren_schuhe"],
    "hosen_jeans": ["damen_jeans", "damen_kleidung", "herren_jeans", "herren_kleidung"],
    "oberteile": ["damen_kleidung", "herren_kleidung"],
}

BAD_WORDS = [
    "baby", "kinder", "kids", "child", "toddler", "enfant", "bambino",
    "bebe", "newborn", "infant", "monat", "jahre",
    "parfum", "perfume", "deo", "kosmetik", "makeup", "shampoo",
    "buch", "book", "dvd", "cd", "vinyl", "spielzeug", "toy",
    "handyhulle", "phone case", "maske", "socken",
]


class Bot:
    def __init__(self):
        self.cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        self.token = self.cfg["telegram_bot_token"]
        self.chat_id = self.cfg["telegram_chat_id"]
        self.seen = self.load_json(SEEN_FILE, {})
        self.brands = {self.norm(b) for b in self.cfg.get("brands", {})}
        self.sizes = {}
        for cat, keys in SIZE_KEYS.items():
            allowed = set()
            for k in keys:
                for s in self.cfg.get("sizes", {}).get(k, []):
                    allowed.add(str(s).strip().lower())
            if allowed:
                self.sizes[cat] = allowed
        self.session = None
        self.ip = "?"
        self.shutdown = False
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        self.new_session()

    def stop(self, *_):
        print("\nStop.")
        self.shutdown = True
        self.save_json(SEEN_FILE, self.seen)

    @staticmethod
    def norm(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    @staticmethod
    def load_json(path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def save_json(path, data):
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def new_session(self):
        """Frische Session durch Tor."""
        try:
            self.session.close()
        except Exception:
            pass
        s = cffi_requests.Session(impersonate="chrome131", proxy=TOR_PROXY)
        s.headers.update({"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
        self.session = s
        try:
            r = s.get("https://api.ipify.org", timeout=15)
            self.ip = r.text.strip() if r.status_code == 200 else "?"
        except Exception:
            self.ip = "?"

    def tg(self, method, **kwargs):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/{method}",
                timeout=20, **kwargs,
            )
            if r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 30)
                print(f"   TG rate-limit {wait}s")
                time.sleep(wait)
                return False
            return r.status_code == 200
        except Exception:
            return False

    def fetch(self, url, referer="https://www.vinted.de/"):
        """GET mit Retry + IP-Wechsel bei Block."""
        for attempt in range(4):
            if self.shutdown:
                return None
            try:
                r = self.session.get(url, timeout=60, headers={"Referer": referer})
                if r.status_code == 200:
                    return r
                if r.status_code == 403:
                    print(f"   Block -> neue IP...")
                    self.new_session()
                    time.sleep(10)
                    continue
                return None
            except Exception as e:
                print(f"   Fehler: {str(e)[:80]}")
                time.sleep(8)
        return None

    def parse_page(self, html_text):
        items = []
        seen_ids = set()
        for m in re.finditer(
            r'product-item-id-(\d+)--overlay-link[^>]*title="([^"]*)"', html_text
        ):
            iid = m.group(1)
            if iid in seen_ids:
                continue
            seen_ids.add(iid)
            label = html_mod.unescape(m.group(2))
            brand_m = re.search(r"Marke:\s*([^,]+)", label)
            size_m = re.search(r"Gr(?:o|\u00f6)\s*e:\s*([^,]+)", label) or re.search(r"Gr\.\s*([^,]+)", label)
            price_m = re.search(r"(\d+[.,]\d{2})\s*\u20ac", label)
            cond_m = re.search(r"Zustand:\s*([^,]+)", label)
            img_m = re.search(
                rf'product-item-id-{iid}--image[^"]*"[^>]*>.*?<img src="(https://images[^"]+)"',
                html_text, re.DOTALL,
            )
            try:
                price = float(price_m.group(1).replace(",", ".")) if price_m else 0.0
            except ValueError:
                price = 0.0
            items.append({
                "id": iid,
                "title": label.split(",")[0].strip(),
                "brand": brand_m.group(1).strip() if brand_m else "",
                "size": size_m.group(1).strip() if size_m else "",
                "price": price,
                "cond": cond_m.group(1).strip() if cond_m else "",
                "url": f"https://www.vinted.de/items/{iid}",
                "img": img_m.group(1) if img_m else "",
            })
        return items

    def ok_item(self, item, category):
        text = f"{item['title']} {item['brand']}".lower()
        if any(w in text for w in BAD_WORDS):
            return False
        if not item["brand"] or self.norm(item["brand"]) not in self.brands:
            return False
        allowed = self.sizes.get(category)
        if not allowed:
            return True
        sz = item["size"].strip().lower()
        if not sz or sz in ("none", "one size", "einheitsgrosse"):
            return True
        return any(a in sz or sz in a for a in allowed)

    def scan_category(self, cat, info):
        found = 0
        for cid in info["ids"]:
            if self.shutdown:
                break
            url = (
                f"https://www.vinted.de/catalog?catalog[]={cid}"
                f"&price_to={info['max_price']}&order=newest_first"
            )
            r = self.fetch(url, referer="https://www.vinted.de/catalog")
            if r is None:
                continue
            for item in self.parse_page(r.text):
                if self.shutdown:
                    break
                if item["id"] in self.seen or not self.ok_item(item, cat):
                    continue
                self.seen[item["id"]] = datetime.now().isoformat()
                emoji = {"schuhe": "\U0001f45f", "hosen_jeans": "\U0001f456", "oberteile": "\U0001f455"}.get(cat, "\U0001f4e6")
                caption = (
                    f"{emoji} <b>{item['brand']}</b>\n"
                    f"\U0001f4b0 {item['price']}€\n"
                    f"\U0001f4cf {item['size']}\n"
                    f"\U0001f4dd {item['title'][:70]}\n"
                    f'<a href="{item["url"]}">\U0001f517 Ansehen</a>'
                )
                print(f"   NEU: {item['brand']} | {item['size']} | {item['price']}€ | {item['title'][:40]}")
                sent = False
                if item["img"]:
                    try:
                        ir = self.session.get(item["img"], timeout=40, headers={"Referer": "https://www.vinted.de/"})
                        if ir.status_code == 200 and len(ir.content) > 500:
                            sent = self.tg(
                                "sendPhoto",
                                data={"chat_id": self.chat_id, "caption": caption, "parse_mode": "HTML"},
                                files={"photo": ("i.jpg", ir.content)},
                            )
                    except Exception:
                        pass
                if not sent:
                    sent = self.tg("sendMessage", json={
                        "chat_id": self.chat_id, "text": caption,
                        "parse_mode": "HTML", "disable_web_page_preview": True,
                    })
                if sent:
                    found += 1
                time.sleep(random.uniform(2, 4))
            time.sleep(random.uniform(2, 4))
        return found

    def run(self):
        print("=" * 50)
        print("VINTED SNIPEBOT v2")
        print(f"IP: {self.ip}")
        print("=" * 50)
        while not self.shutdown:
            total = 0
            cats = list(CATEGORIES.items())
            random.shuffle(cats)
            for cat, info in cats:
                if self.shutdown:
                    break
                print(f"\n[{datetime.now():%H:%M:%S}] {cat} ({len(info['ids'])}) max {info['max_price']}EUR")
                total += self.scan_category(cat, info)
            self.save_json(SEEN_FILE, self.seen)
            print(f"\n{total} gesendet. Weiter sofort...")
            if self.shutdown:
                break
            time.sleep(30)


if __name__ == "__main__":
    Bot().run()
