#!/usr/bin/env python3
"""
Vinted Snipebot v5
- 6 Worker parallel mit separaten Tor-Circuits
- Laender: DE, AT, FR, BE, NL, IT (+ Seite 2 auf DE)
- Keyword-Suchen zusaetzlich zu Kategorien
- Favoriten + Views + Verkaeufer aus eingebettetem JSON
- Zustand immer auf Deutsch (uebersetzt aus allen Sprachen)
- Tages-Statistik per Telegram
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
NUM_WORKERS = 6
CYCLE_SLEEP = 10
SCAN_PAGE2_DE = True

SCAN_DOMAINS = [
    "www.vinted.de",
    "www.vinted.at",
    "www.vinted.fr",
    "www.vinted.be",
    "www.vinted.nl",
    "www.vinted.it",
]

# Kategorie-IDs nach Geschlecht gegliedert.
# Aktiviert/deaktiviert wird über config.json -> "categories".
CATEGORIES = {
    "schuhe": {
        "ids": {
            "damen": ["2632", "543", "1049", "2630", "215"],
            "herren": ["1242", "1452", "1233", "1238", "2656",
                       "2969", "2968", "2970", "2659", "2657"],
        },
        "max_price": 50,
    },
    "hosen_jeans": {
        "ids": {
            "damen": ["9", "183"],
            "herren": ["34", "257", "80"],
        },
        "max_price": 30,
    },
    "oberteile": {
        "ids": {
            "damen": ["12"],
            "herren": ["76", "79", "30"],
        },
        "max_price": 15,
    },
    "jacken_maentel": {
        "ids": {
            "damen": ["16", "1205"],
            "herren": ["1206"],
        },
        "max_price": 45,
    },
}

SIZE_KEYS = {
    "schuhe": {
        "damen": ["damen_schuhe"],
        "herren": ["herren_schuhe"],
    },
    "hosen_jeans": {
        "damen": ["damen_jeans", "damen_kleidung"],
        "herren": ["herren_jeans", "herren_kleidung"],
    },
    "oberteile": {
        "damen": ["damen_kleidung"],
        "herren": ["herren_kleidung"],
    },
    "jacken_maentel": {
        "damen": ["damen_kleidung"],
        "herren": ["herren_kleidung"],
    },
}

EMOJIS = {"schuhe": "\U0001f45f", "hosen_jeans": "\U0001f456", "oberteile": "\U0001f455",
          "jacken_maentel": "\U0001f9e5", "keyword": "\U0001f50e"}

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
    # Armani-Familie - nur billige Snipes: 30 EUR
    "armani": 30, "giorgioarmani": 30, "emporioarmani": 30,
    "armaniexchange": 25, "armanijeans": 30, "ea7": 30,
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

# Multi-Sprach-Patterns fuer Overlay-Label (de/fr/nl/it/es gleichzeitig)
BRAND_RE = re.compile(r"(?:Marke|Marque|Marca|Merk)\s*:\s*([^,]+)")
SIZE_RE = re.compile(
    r"(?:Gr\u00f6\u00dfe|Gr\u00f6sse|Groesse|Gr\.\s*|Size|Taille|Taglia|Talla|Maat)\s*\.?\s*:\s*([^,]+)"
)
COND_RE = re.compile(
    r"(?:Zustand|\u00c9tat|Etat|Staat|Condizioni?|Estado)\s*:\s*([^,]+)"
)
PRICE_RE = re.compile(r"(\d+[.,]\d{2})")

# Eingebettetes JSON am Seitenende (RSC-Payload, escaped Quotes)
FAV_ID_RE = re.compile(r'\\?"favourite_count\\?":\s*(\d+),\s*\\?"id\\?":\s*(\d{7,12})')
LOGIN_RE = re.compile(r'\\?"login\\?":\\?"([^"\\]{1,40})')
VIEWS_RE = re.compile(r'\\?"view_count\\?":(\d+)')

# Zustands-Uebersetzung -> Deutsch
CONDITION_MAP = [
    (("neu mit etikett", "new with tags", "neuf avec \u00e9tiquette", "nuovo con etichetta",
      "nuevo con etiquetas", "nieuw met kaartje"), "Neu mit Etikett"),
    (("neu ohne etikett", "new without tags", "neuf sans \u00e9tiquette", "nuovo senza etichetta",
      "nuevo sin etiquetas", "nieuw zonder kaartje"), "Neu ohne Etikett"),
    (("sehr gut", "very good", "tr\u00e8s bon \u00e9tat", "molto buono",
      "muy bueno", "zeer goede staat"), "Sehr gut"),
    (("gut", "good", "bon \u00e9tat", "buono", "bueno", "goede staat"), "Gut"),
    (("befriedigend", "satisfactory", "satisfaisant", "discreto",
      "satisfactorio", "redelijke staat"), "Befriedigend"),
]


def norm(s):
    s = s.lower()
    s = s.replace("&", "").replace("+", "")
    return re.sub(r"[^a-z0-9]", "", s)


def translate_condition(cond):
    if not cond:
        return ""
    c = cond.strip().lower()
    for needles, german in CONDITION_MAP:
        if any(n in c for n in needles):
            return german
    return cond.strip()


def extract_rsc_data(html_text):
    """Fav/Views/Seller aus dem eingebetteten JSON ziehen."""
    meta = {}
    for m in FAV_ID_RE.finditer(html_text):
        favs, iid = int(m.group(1)), m.group(2)
        window = html_text[m.end():m.end() + 3500]
        cs = window.find("content_source")
        seg = window[:cs] if cs > 0 else window
        login_m = LOGIN_RE.search(seg)
        views_m = VIEWS_RE.search(seg)
        meta[iid] = {
            "favs": favs,
            "seller": login_m.group(1) if login_m else "",
            "views": int(views_m.group(1)) if views_m else None,
        }
    return meta


class Worker:
    def __init__(self, wid):
        self.wid = wid
        self.session = None
        self.rotations = 0
        self.proxy = f"socks5h://worker{wid}:x@127.0.0.1:9050"

    def start(self):
        s = cffi_requests.Session(impersonate="chrome131", proxy=self.proxy)
        s.headers.update({
            "Accept-Language": "de-DE,de;q=0.9,fr;q=0.8,nl;q=0.7,it;q=0.6,en;q=0.5"
        })
        self.session = s

    def rotate(self):
        """Eindeutiger Username pro Rotation = garantiert neuer Circuit."""
        self.rotations += 1
        self.proxy = f"socks5h://worker{self.wid}-r{self.rotations}:x@127.0.0.1:9050"
        print(f"   [W{self.wid}] Block -> neuer Circuit (#{self.rotations})")
        self.start()

    def fetch(self, url, referer):
        for attempt in range(3):
            try:
                r = self.session.get(url, timeout=60, headers={"Referer": referer})
                if r.status_code == 200:
                    return r
                if r.status_code == 403:
                    self.rotate()
                    time.sleep(8)
                    continue
                return None
            except Exception as e:
                print(f"   [W{self.wid}] Fehler: {str(e)[:70]}")
                time.sleep(6)
        return None


def parse_page(html_text):
    rsc = extract_rsc_data(html_text)

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
        brand_m = BRAND_RE.search(label)
        size_m = SIZE_RE.search(label)
        cond_m = COND_RE.search(label)
        # Erste Zahl = Artikelpreis (zweite ist Gesamtpreis inkl. Gebuehr)
        prices = PRICE_RE.findall(label)
        try:
            price = float(prices[0].replace(",", ".")) if prices else 0.0
        except ValueError:
            price = 0.0

        img_m = re.search(
            rf'product-item-id-{iid}--image[^"]*"[^>]*>.*?<img src="(https://images[^"]+)"',
            html_text, re.DOTALL,
        )
        extra = rsc.get(iid, {})

        items.append({
            "id": iid,
            "title": label.split(",")[0].strip(),
            "brand": brand_m.group(1).strip() if brand_m else "",
            "size": size_m.group(1).strip() if size_m else "",
            "price": price,
            "cond": translate_condition(cond_m.group(1)) if cond_m else "",
            "url": f"https://www.vinted.de/items/{iid}",
            "img": img_m.group(1) if img_m else "",
            "favs": extra.get("favs"),
            "views": extra.get("views"),
            "seller": extra.get("seller", ""),
        })
    return items


class Bot:
    def __init__(self):
        self.cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        self.token = self.cfg["telegram_bot_token"]
        self.chat_id = self.cfg["telegram_chat_id"]
        self.seen = self._load(SEEN_FILE, {})
        self.keywords = [k for k in self.cfg.get("keywords", []) if k]
        self.limits = {}
        default_tier = 40
        for name in self.cfg.get("brands", {}):
            t = BRAND_TIERS.get(norm(name))
            self.limits[norm(name)] = t if t else default_tier
        print(f"Marken mit Tier-Limit: {len(self.limits)}")
        print(f"Keywords: {self.keywords}")
        self.sizes = {}
        enabled_genders = {g for g, v in self.cfg.get("categories", {}).items() if v}
        for cat, gender_keys in SIZE_KEYS.items():
            allowed = set()
            for gender in enabled_genders:
                for k in gender_keys.get(gender, []):
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
        self.stats_today = {"date": datetime.now().strftime("%Y-%m-%d"), "sent": 0}
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
                cutoff = datetime.now().timestamp() - 21 * 86400
                pruned = {}
                for iid, ts_str in self.seen.items():
                    try:
                        if datetime.fromisoformat(ts_str).timestamp() >= cutoff:
                            pruned[iid] = ts_str
                    except Exception:
                        pruned[iid] = ts_str
                self.seen = pruned
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
        cat_cap = CATEGORIES.get(category, {}).get("max_price", 50)
        cap = min(cat_cap, self.limits[b])
        if item["price"] <= 0 or item["price"] > cap:
            return False
        if category == "keyword":
            return True
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
        if item["cond"]:
            lines.append(f"\u2728 {item['cond'][:40]}")
        stats = []
        if item["favs"] is not None:
            stats.append(f"\u2764\ufe0f {item['favs']}")
        if item["views"]:
            stats.append(f"\U0001f441 {item['views']}")
        if stats:
            lines.append(" · ".join(stats))
        if item["seller"]:
            lines.append(f"\U0001f464 {html_mod.escape(item['seller'])}")
        lines.append(f"\U0001f4dd {item['title'][:70]}")
        lines.append(f'<a href="{item["url"]}">\U0001f517 Ansehen</a>')
        caption = "\n".join(lines)

        print(f"   NEU [{cat}]: {item['brand']} | {item['size']} | "
              f"{item['price']}€ | \u2764\ufe0f{item['favs'] if item['favs'] is not None else '-'} "
              f"| {item['title'][:35]}")
        sent = False
        if item["img"]:
            big_url = item["img"].replace("/310x430/", "/758x1136/")
            if big_url != item["img"]:
                sent = self.tg_send_photo_url(big_url, caption)
            if not sent:
                sent = self.tg_send_photo_url(item["img"], caption)
        if not sent:
            sent = self.tg_send_message(caption)
        return sent

    def scan_job(self, worker, url, referer, cat):
        r = worker.fetch(url, referer=referer)
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
                with self.lock:
                    self.stats_today["sent"] += 1
            time.sleep(random.uniform(1.5, 2.5))
        return sent

    def build_jobs(self):
        jobs = []
        base_jobs = []
        enabled_genders = {g for g, v in self.cfg.get("categories", {}).items() if v}
        for cat, info in CATEGORIES.items():
            for gender in enabled_genders:
                for cid in info["ids"].get(gender, []):
                    base_jobs.append((cat, cid, info["max_price"]))
        for dom in SCAN_DOMAINS:
            for cat, cid, mp in base_jobs:
                url = f"https://{dom}/catalog?catalog[]={cid}&price_to={mp}&order=newest_first"
                jobs.append((url, f"https://{dom}/", cat))
        # Seite 2 nur auf DE (aehltere Treffer)
        if SCAN_PAGE2_DE:
            for cat, cid, mp in base_jobs:
                url = (f"https://www.vinted.de/catalog?catalog[]={cid}"
                       f"&page=2&price_to={mp}&order=newest_first")
                jobs.append((url, "https://www.vinted.de/", cat))
        # Keyword-Suchen auf DE
        for kw in self.keywords:
            url = (f"https://www.vinted.de/catalog?search_text={kw.replace(' ', '%20')}"
                   f"&order=newest_first")
            jobs.append((url, "https://www.vinted.de/", "keyword"))
        random.shuffle(jobs)
        return jobs

    def run(self):
        print("=" * 50)
        print(f"VINTED SNIPEBOT v5 ({NUM_WORKERS} Worker)")
        print(f"Laender: {', '.join(d.split('.')[2] for d in SCAN_DOMAINS)}")
        print("Limits: Kategorie + Marken-Tier (das niedrigere gilt)")
        print("=" * 50)
        cycle = 0
        while not self.shutdown:
            today = datetime.now().strftime("%Y-%m-%d")
            if today != self.stats_today["date"]:
                self.tg_send_message(
                    f"\U0001f4ca Gestern: {self.stats_today['sent']} Items gefunden")
                self.stats_today = {"date": today, "sent": 0}

            t0 = time.time()
            jobs = self.build_jobs()
            print(f"\n=== Scan #{cycle} {datetime.now():%H:%M:%S} ({len(jobs)} Jobs) ===")
            total = 0
            with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
                futures = [
                    ex.submit(self.scan_job, self.workers[i % NUM_WORKERS],
                              url, ref, cat)
                    for i, (url, ref, cat) in enumerate(jobs)
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
            print(f"=== Fertig in {dur}s, {total} gesendet | heute: "
                  f"{self.stats_today['sent']} ===")
            cycle += 1
            if not self.shutdown:
                time.sleep(CYCLE_SLEEP)


if __name__ == "__main__":
    Bot().run()
