#!/usr/bin/env python3
"""
Vinted Snipebot v4
- 4 Worker parallel mit separaten Tor-Circuits
- Zwei Limits: Kategorie UND Marken-Tier (das niedrigere gewinnt)
- Laender-Rotation: de + fr/it/nl im Wechsel
- Telegram laedt Fotos direkt von Vinted
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
NUM_WORKERS = 4
CYCLE_SLEEP = 10

MAIN_DOMAIN = "www.vinted.de"
ROTATE_DOMAINS = ["www.vinted.fr", "www.vinted.it", "www.vinted.nl"]

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

# Marken-Tier Limits (normalisiert via norm()); Kollabs folgen Hauptmarke
BRAND_TIERS = {
    # Tier 1 - Top-Luxus: 60 EUR
    "chanel": 60, "hermes": 60, "louisvuitton": 60, "lv": 60,
    "louisvuittonxsupreme": 60, "supremexlouisvuitton": 60,
    "christiandior": 60, "dior": 60, "diorhomme": 60,
    "diorxjordan": 60, "diorxstoneisland": 60, "diorxstssy": 60, "stssyxdior": 60,
    "prada": 60, "pradalinearossa": 60, "pradaxadidas": 60, "adidasxprada": 60,
    "gucci": 60, "guccixadidas": 60, "adidasxgucci": 60,
    "guccixnorthface": 60, "thenorthfacexgucci": 60,
    "bottegaveneta": 60, "cline": 60,
    "loewe": 60, "loewexpiritedaway": 60,
    "fendi": 60, "fendicasa": 60, "fendixfila": 60, "filaxfendi": 60,
    "fendixskims": 60, "fendixversace": 60, "versacexfendi": 60,
    "cartier": 60, "rolex": 60, "patekphilippe": 60, "richardmille": 60,
    "vancleef": 60, "vancleefarpels": 60,
    # Tier 2 - High Fashion: 50 EUR
    "ysl": 50, "yvessaintlaurent": 50, "saintlaurent": 50,
    "balenciaga": 50, "balenciagaxcrocs": 50,
    "balmain": 50, "pumaxbalmain": 50,
    "miumiu": 50, "givenchy": 50,
    "valentino": 50, "redvalentino": 50, "valentinoxnewbalance": 50,
    "burberry": 50,
    "moncler": 50, "monclergenius": 50, "monclergrenoble": 50,
    "monclerxfragmentdesign": 50, "monclerxjwanderson": 50, "monclerxrickowens": 50,
    "tomford": 50,
    "maisonmargiela": 50, "margiela": 50,
    "maisonmargielaxreebok": 50, "reebokxmaisonmargiela": 50,
    "jacquemus": 50, "isabelmarant": 50, "maxmara": 50,
    "loropiana": 50, "brunellocucinelli": 50,
    "ermenegildozegna": 50, "zegna": 50, "brioni": 50,
    "thombrowne": 50, "rickowens": 50, "goldengoose": 50,
    "christianlouboutin": 50, "louboutin": 50,
    "salvatoreferragamo": 50, "ferragamo": 50,
    "oscardelarenta": 50, "acnestudios": 50, "amiri": 50,
    "offwhite": 50, "offwhitexdrmartens": 50, "offwhitexikea": 50,
    "offwhitexnike": 50, "offwhitextimberland": 50, "timberlandxoffwhite": 50,
    "vetements": 50, "vetementsxreebok": 50, "reebokxvetements": 50,
    "dolcegabbana": 50, "dg": 50,
    "giuseppezanotti": 50,
    # Tier 3 - Premium: 45 EUR
    "stoneisland": 45, "canadagoose": 45,
    "palmangels": 45, "palmangelsxvarious": 45,
    "amiparis": 45, "kenzo": 45, "kenzojungle": 45,
    "philippplein": 45, "fearofgod": 45,
    "commedesgarons": 45, "cdg": 45,
    "commedesgaronsxconverse": 45, "conversexcommedesgarons": 45,
    "nikexambush": 45, "nikexcommedesgarons": 45,
    "nikexsacai": 45, "sacaixnike": 45,
    "nikextravisscott": 45, "travisscottxnike": 45,
    "nikexundercover": 45, "undercoverxnike": 45,
    "newbalancexaimeleondore": 45, "newbalancexjjjjound": 45,
    "supreme": 45, "supremexnike": 45, "supremexthenorthface": 45,
    "thenorthfacexsupreme": 45, "supremextiffany": 45,
    "palace": 45, "rafsimonsxadidas": 45,
    # Tier 4 - Einsteiger: 35 EUR
    "poloralphlauren": 35, "ralphlauren": 35, "ralphlaurencollection": 35, "rl": 35,
    "nudiejeans": 35,
    "versacejeanscouture": 35, "versusversace": 35,
    "jwandersonxuniqlo": 35, "kenzoxhm": 35,
}

BAD_WORDS = [
    # Baby/Kinder
    "baby", "kinder", "kids", "child", "toddler", "enfant", "bambino",
    "bebe", "newborn", "infant", "monat", "jahre",
    # Keine Kleidung
    "parfum", "perfume", "deo", "kosmetik", "makeup", "shampoo",
    "buch", "book", "dvd", "vinyl", "spielzeug", "toy",
    "handyhulle", "phone case", "maske", "socken",
    # Muell: Karten, Zertifikate, leere Verpackungen
    "garantie", "garanzia", "warranty", "guarantee",
    "zertifikat", "certificat", "carta d'autenticit",
    "authenticity card", "authenticity", "autenticidad",
    "porta garanzia", "portagaranzia",
    "box only", "nur box", "only box", "empty box", "leere box",
    "no item", "ohne inhalt", "without content",
    "staubbeutel nur", "dust bag only", "dustbag only",
]

# Sprach-Patterns pro Domain
LANG_PATTERNS = {
    "de": {"brand": r"Marke\s*:\s*([^,]+)", "size": r"Gr(?:o|\u00f6)\s*e\s*:\s*([^,]+)", "cond": r"Zustand\s*:\s*([^,]+)"},
    "fr": {"brand": r"Marque\s*:\s*([^,]+)", "size": r"Taille\s*:\s*([^,]+)", "cond": r"\u00c9tat\s*:\s*([^,]+)"},
    "it": {"brand": r"Marca\s*:\s*([^,]+)", "size": r"Taglia\s*:\s*([^,]+)", "cond": r"Condizion[ei]\s*:\s*([^,]+)"},
    "nl": {"brand": r"Merk\s*:\s*([^,]+)", "size": r"Maat\s*:\s*([^,]+)", "cond": r"Staat\s*:\s*([^,]+)"},
}


def norm(s):
    s = s.lower()
    s = s.replace("&", "").replace("+", "")
    return re.sub(r"[^a-z0-9]", "", s)


class Worker:
    def __init__(self, wid):
        self.wid = wid
        self.session = None
        self.proxy = f"socks5h://worker{wid}:x@127.0.0.1:9050"

    def start(self):
        s = cffi_requests.Session(impersonate="chrome131", proxy=self.proxy)
        s.headers.update({"Accept-Language": "de-DE,de;q=0.9,en;q=0.8,fr;q=0.7,it;q=0.6,nl;q=0.5"})
        self.session = s

    def fetch(self, url, referer):
        for attempt in range(3):
            try:
                r = self.session.get(url, timeout=60, headers={"Referer": referer})
                if r.status_code == 200:
                    return r
                if r.status_code == 403:
                    print(f"   [W{self.wid}] Block -> neuer Circuit")
                    self.start()
                    time.sleep(8)
                    continue
                return None
            except Exception as e:
                print(f"   [W{self.wid}] Fehler: {str(e)[:70]}")
                time.sleep(6)
        return None


def parse_page(html_text, lang):
    pats = LANG_PATTERNS.get(lang, LANG_PATTERNS["de"])
    brand_re = re.compile(pats["brand"])
    size_re = re.compile(pats["size"])
    cond_re = re.compile(pats["cond"])
    price_re = re.compile(r"(\d+[.,]\d{2})\s*\u20ac")

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
        brand_m = brand_re.search(label)
        size_m = size_re.search(label)
        cond_m = cond_re.search(label)
        pm = price_re.search(label)

        img_m = re.search(
            rf'product-item-id-{iid}--image[^"]*"[^>]*>.*?<img src="(https://images[^"]+)"',
            html_text, re.DOTALL,
        )
        # Favoriten aus eingebettetem JSON (best effort)
        favs = None
        window = html_text[m.start():m.start() + 3000]
        fm = re.search(r'"favourite_count":(\d+)', window)
        if fm:
            favs = int(fm.group(1))

        try:
            price = float(pm.group(1).replace(",", ".")) if pm else 0.0
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
            "favs": favs,
        })
    return items


class Bot:
    def __init__(self):
        self.cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        self.token = self.cfg["telegram_bot_token"]
        self.chat_id = self.cfg["telegram_chat_id"]
        self.seen = self._load(SEEN_FILE, {})
        # Marken-Limits: konfigurierte Marken -> Tier-Limit
        self.limits = {}
        default_tier = 40
        for name in self.cfg.get("brands", {}):
            t = BRAND_TIERS.get(norm(name))
            self.limits[norm(name)] = t if t else default_tier
        print(f"Marken mit Tier-Limit: {len(self.limits)}")
        self.sizes = {}
        for cat, keys in SIZE_KEYS.items():
            allowed = set()
            for k in keys:
                for s in self.cfg.get("sizes", {}).get(k, []):
                    allowed.add(str(s).strip().lower())
            if allowed:
                self.sizes[cat] = allowed
        self.workers = []
        for i in range(NUM_WORKERS):
            w = Worker(i + 1)
            w.start()
            self.workers.append(w)
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
                print(f"   TG rate-limit {wait}s")
                time.sleep(wait)
                return False
            return r.status_code == 200
        except Exception:
            return False

    def tg_send_message(self, text):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id, "text": text,
                    "parse_mode": "HTML", "disable_web_page_preview": True,
                },
                timeout=25,
            )
            return r.status_code == 200
        except Exception:
            return False

    def ok_item(self, item, category):
        text = f"{item['title']} {item['brand']}".lower()
        if any(w in text for w in BAD_WORDS):
            return False
        b = norm(item["brand"])
        if not b or b not in self.limits:
            return False
        cat_cap = CATEGORIES[category]["max_price"]
        cap = min(cat_cap, self.limits[b])
        if item["price"] <= 0 or item["price"] > cap:
            return False
        allowed = self.sizes.get(category)
        if allowed:
            sz = item["size"].strip().lower()
            if sz and sz not in ("none", "one size", "einheitsgrosse"):
                if not any(a in sz or sz in a for a in allowed):
                    return False
        return True

    def process_item(self, item, cat):
        emoji = EMOJIS.get(cat, "\U0001f4e6")
        lines = [
            f"{emoji} <b>{item['brand']}</b>",
            f"\U0001f4b0 {item['price']}€",
        ]
        if item["size"]:
            lines.append(f"\U0001f4cf {item['size']}")
        if item["favs"] is not None:
            fav_icon = "\U0001f525" if item["favs"] >= 20 else "\u2764\ufe0f"
            lines.append(f"{fav_icon} {item['favs']} Favoriten")
        lines.append(f"\U0001f4dd {item['title'][:70]}")
        lines.append(f'<a href="{item["url"]}">\U0001f517 Ansehen</a>')
        caption = "\n".join(lines)

        print(f"   NEU [{cat}]: {item['brand']} | {item['size']} | "
              f"{item['price']}€ | \u2764\ufe0f{item['favs'] or '-'} | {item['title'][:35]}")
        sent = False
        if item["img"]:
            sent = self.tg_send_photo_url(item["img"], caption)
        if not sent:
            sent = self.tg_send_message(caption)
        return sent

    def scan_job(self, worker, cat, cid, cat_max, domain, lang):
        url = f"https://{domain}/catalog?catalog[]={cid}&price_to={cat_max}&order=newest_first"
        r = worker.fetch(url, referer=f"https://{domain}/")
        if r is None:
            return 0
        sent = 0
        for item in parse_page(r.text, lang):
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
        print(f"VINTED SNIPEBOT v4 ({NUM_WORKERS} Worker)")
        print(f"Limits: Kategorie + Marken-Tier (das niedrigere gilt)")
        print("=" * 50)
        base_jobs = []
        for cat, info in CATEGORIES.items():
            for cid in info["ids"]:
                base_jobs.append((cat, cid, info["max_price"]))
        cycle = 0
        while not self.shutdown:
            t0 = time.time()
            alt_domain = ROTATE_DOMAINS[cycle % len(ROTATE_DOMAINS)]
            alt_lang = alt_domain.split(".")[1]
            jobs = [(cat, cid, mp, MAIN_DOMAIN, "de") for cat, cid, mp in base_jobs]
            jobs += [(cat, cid, mp, alt_domain, alt_lang) for cat, cid, mp in base_jobs]
            random.shuffle(jobs)
            print(f"\n=== Scan #{cycle} {datetime.now():%H:%M:%S} "
                  f"(de + {alt_lang}, {len(jobs)} Jobs) ===")
            total = 0
            with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
                futures = [
                    ex.submit(self.scan_job, self.workers[i % NUM_WORKERS],
                              cat, cid, mp, dom, lang)
                    for i, (cat, cid, mp, dom, lang) in enumerate(jobs)
                ]
                for f in as_completed(futures):
                    if self.shutdown:
                        break
                    try:
                        total += f.result()
                    except Exception as e:
                        print(f"   Job-Fehler: {str(e)[:80]}")
            self._save_seen()
            dur = int(time.time() - t0)
            print(f"=== Fertig in {dur}s, {total} gesendet ===")
            cycle += 1
            if not self.shutdown:
                time.sleep(CYCLE_SLEEP)


if __name__ == "__main__":
    Bot().run()
