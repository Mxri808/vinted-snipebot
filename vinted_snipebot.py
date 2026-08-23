#!/usr/bin/env python3
"""
Vinted Snipebot v3
- Parallel-Scanning: 4 Worker mit separaten Tor-Circuits
- Fotos: Telegram laedt Bilder direkt von Vinted (kein Download noetig)
"""

import html as html_mod
import json
import random
import re
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from curl_cffi import requests as cffi_requests

BASE = Path(__file__).parent
CONFIG_FILE = BASE / "config.json"
SEEN_FILE = BASE / "seen_items.json"
TOR_PROXY = "socks5h://127.0.0.1:9050"
NUM_WORKERS = 4

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

EMOJIS = {"schuhe": "\U0001f45f", "hosen_jeans": "\U0001f456", "oberteile": "\U0001f455"}

BAD_WORDS = [
    "baby", "kinder", "kids", "child", "toddler", "enfant", "bambino",
    "bebe", "newborn", "infant", "monat", "jahre",
    "parfum", "perfume", "deo", "kosmetik", "makeup", "shampoo",
    "buch", "book", "dvd", "vinyl", "spielzeug", "toy",
    "handyhulle", "phone case", "maske", "socken",
]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


class Worker:
    """Ein Worker = eine Session durch einen eigenen Tor-Circuit."""

    def __init__(self, wid):
        self.wid = wid
        self.session = None
        # Eigener Username pro Worker -> Tor isoliert Circuits automatisch
        self.proxy = f"socks5h://worker{wid}:x@127.0.0.1:9050"

    def start(self):
        s = cffi_requests.Session(impersonate="chrome131", proxy=self.proxy)
        s.headers.update({"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
        self.session = s

    def fetch(self, url, referer="https://www.vinted.de/catalog"):
        for attempt in range(3):
            try:
                r = self.session.get(url, timeout=60, headers={"Referer": referer})
                if r.status_code == 200:
                    return r
                if r.status_code == 403:
                    print(f"   [W{self.wid}] Block -> neuer Circuit")
                    self.start()  # neue Session = neuer Circuit (neuer Auth-Context)
                    time.sleep(8)
                    continue
                return None
            except Exception as e:
                print(f"   [W{self.wid}] Fehler: {str(e)[:70]}")
                time.sleep(6)
        return None


def parse_page(html_text):
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


class Bot:
    def __init__(self):
        self.cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        self.token = self.cfg["telegram_bot_token"]
        self.chat_id = self.cfg["telegram_chat_id"]
        self.seen = self._load(SEEN_FILE, {})
        self.brands = {norm(b) for b in self.cfg.get("brands", {})}
        self.sizes = {}
        for cat, keys in SIZE_KEYS.items():
            allowed = set()
            for k in keys:
                for s in self.cfg.get("sizes", {}).get(k, []):
                    allowed.add(str(s).strip().lower())
            if allowed:
                self.sizes[cat] = allowed
        self.workers = [Worker(i + 1) for i in range(NUM_WORKERS)]
        for w in self.workers:
            w.start()
        self.lock = threading.Lock()
        self.shutdown = False
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, *_):
        print("\nStop.")
        self.shutdown = True

    @staticmethod
    def _load(path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _save_seen(self):
        with self.lock:
            try:
                SEEN_FILE.write_text(json.dumps(self.seen, indent=2), encoding="utf-8")
            except Exception:
                pass

    def tg(self, method, **kwargs):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/{method}",
                timeout=25, **kwargs,
            )
            if r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 30)
                print(f"   TG rate-limit {wait}s")
                time.sleep(wait)
                return False
            return r.status_code == 200
        except Exception:
            return False

    def ok_item(self, item, category):
        text = f"{item['title']} {item['brand']}".lower()
        if any(w in text for w in BAD_WORDS):
            return False
        if not item["brand"] or norm(item["brand"]) not in self.brands:
            return False
        allowed = self.sizes.get(category)
        if not allowed:
            return True
        sz = item["size"].strip().lower()
        if not sz or sz in ("none", "one size", "einheitsgrosse"):
            return True
        return any(a in sz or sz in a for a in allowed)

    def process_item(self, item, cat):
        emoji = EMOJIS.get(cat, "\U0001f4e6")
        caption = (
            f"{emoji} <b>{item['brand']}</b>\n"
            f"\U0001f4b0 {item['price']}€\n"
            f"\U0001f4cf {item['size']}\n"
            f"\U0001f4dd {item['title'][:70]}\n"
            f'<a href="{item["url"]}">\U0001f517 Ansehen</a>'
        )
        print(f"   NEU [{cat}]: {item['brand']} | {item['size']} | {item['price']}€ | {item['title'][:35]}")
        # Telegram laedt das Bild selbst (schnell, kein Tor noetig)
        sent = False
        if item["img"]:
            sent = self.tg_send_photo_url(item["img"], caption)
        if not sent:
            sent = self.tg("sendMessage", json={
                "chat_id": self.chat_id, "text": caption,
                "parse_mode": "HTML", "disable_web_page_preview": True,
            })
        return sent

    def tg_send_photo_url(self, img_url, caption):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendPhoto",
                data={
                    "chat_id": self.chat_id,
                    "photo": img_url,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                timeout=25,
            )
            if r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 30)
                time.sleep(wait)
                return False
            return r.status_code == 200
        except Exception:
            return False

    def scan_job(self, worker, cat, cid, max_price):
        url = f"https://www.vinted.de/catalog?catalog[]={cid}&price_to={max_price}&order=newest_first"
        r = worker.fetch(url)
        if r is None:
            return 0
        sent = 0
        for item in parse_page(r.text):
            if self.shutdown:
                break
            with self.lock:
                if item["id"] in self.seen:
                    continue
                if not self.ok_item(item, cat):
                    continue
                self.seen[item["id"]] = datetime.now().isoformat()
            if self.process_item(item, cat):
                sent += 1
            time.sleep(random.uniform(1.5, 2.5))
        return sent

    def run(self):
        print("=" * 50)
        print(f"VINTED SNIPEBOT v3 ({NUM_WORKERS} Worker parallel)")
        print("=" * 50)
        jobs = []
        for cat, info in CATEGORIES.items():
            for cid in info["ids"]:
                jobs.append((cat, cid, info["max_price"]))
        random.shuffle(jobs)
        while not self.shutdown:
            t0 = time.time()
            total = 0
            print(f"\n=== Scan {datetime.now():%H:%M:%S} ({len(jobs)} Jobs) ===")
            with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
                futures = {}
                for i, (cat, cid, max_price) in enumerate(jobs):
                    w = self.workers[i % NUM_WORKERS]
                    futures[ex.submit(self.scan_job, w, cat, cid, max_price)] = None
                for f in as_completed(futures):
                    try:
                        total += f.result()
                    except Exception as e:
                        print(f"   Job-Fehler: {e}")
                    if self.shutdown:
                        break
            self._save_seen()
            dur = int(time.time() - t0)
            print(f"=== Fertig in {dur}s, {total} gesendet ===")
            time.sleep(20)


if __name__ == "__main__":
    Bot().run()
