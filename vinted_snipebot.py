#!/usr/bin/env python3
"""
Vinted Snipebot - Luxury Brand Price Monitor
"""

import html as html_mod
import json
import random
import re
import signal
import time
import requests
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "config.json"
SEEN_ITEMS_FILE = Path(__file__).parent / "seen_items.json"

CATALOG_IDS = {
    "tops_tshirts": ["12"],
    "hosen_jeans": ["9", "183"],
    "blazer_anzuege": ["8"],
    "schuhe": ["2632", "543", "1049", "2630", "215", "1242", "1452", "1233"],
    "taschen": ["156", "158", "552", "160", "157", "159", "1848", "94"],
    "guertel": ["20", "96"],
    "sonnenbrillen": ["26", "98"],
    "schals": ["89", "87"],
}

CAT_EMOJIS = {
    "schuhe": "\U0001f45f", "taschen": "\U0001f45c",
    "blazer_anzuege": "\U0001f935", "pullover_strick": "\U0001f9f6",
    "hosen_jeans": "\U0001f456", "guertel": "\U0001f454", "sonnenbrillen": "\U0001f576\ufe0f",
    "tops_tshirts": "\U0001f455", "schals": "\U0001f9e3",
}

CAT_MAX_PRICES = {
    "schuhe": 50, "taschen": 45,
    "blazer_anzuege": 40, "pullover_strick": 30,
    "hosen_jeans": 30, "guertel": 25, "sonnenbrillen": 25,
    "tops_tshirts": 15, "schals": 10,
}

BABY_KIDS_BLACKLIST = [
    "baby", "kinder", "kids", "child", "children", "toddler",
    "enfant", "bambino", "bambina", "neonato", "bebe",
    "neo", "newborn", "infant",
    "12 mois", "18 mois", "24 mois", "36 mois",
    "monat", "monate", "jahre", "jahrig",
    "strampler", "leggin", "petit", "petite", "garcon", "fille",
    "jungen", "madchen",
]

EXCLUDE_KEYWORDS = [
    "buch", "buchar", "book", "books", "romane", "roman", "krimi", "thriller",
    "fantasy", "sachbuch", "ratgeber", "biografie", "taschenbuch", "hardcover",
    "ebook", "lesebuch", "manga", "novel", "fiction", "lexikon", "atlas",
    "parfum", "parfum", "eau de toilette", "eau de parfum", "eau de cologne",
    "perfume", "fragrance", "scent", "duft", "deo", "deodorant",
    "body spray", "flakon", "flacon", "dutter", "raumduft", "kerzendutter",
    "kosmetik", "cosmetic", "make-up", "makeup", "schminke", "mascara",
    "lippenstift", "foundation", "concealer", "puder", "blush",
    "augenpalette", "eyeshadow", "eyeliner", "nagellack", "nail polish",
    "creme", "serum", "moisturizer", "lotion", "peeling",
    "gesichtsmaske", "feuchtigkeitscreme", "reinigung", "cleanser",
    "shampoo", "spulung", "conditioner", "haarpflege",
    "zahnpasta", "toothpaste", "mundwasser",
    "rasierer", "razor", "after shave", "aftershave",
    "dvd", "bluray", "blu-ray", "kassette", "cd", "vinyl",
    "spiel", "spielzeug", "toy", "puzzle", "lego", "brettspiel",
    "handyhulle", "phone case",
    "glas", "tasse", "becher", "flasche", "kerze",
    "decke", "bettwasche", "kissen", "polster",
    "geschenktute", "geschenktasche", "gift bag", "gift box", "geschenkbox",
    "verpackung", "packaging", "papier", "tissue", "seidenpapier",
    "sticker", "aufkleber", "aufnasher", "patch",
    "ringelsocken", "strumpf", "socken", "pantyhose",
    "maske", "mask", "schutzmaske", "ffp2",
    "tie", "krawatt", "fliege", "schlips",
    "burreste", "kamm", "burr", "kamm",
    "pinsel", "brush", "schauf",
    "waschmittel", "pille", "medikament", "tablette",
]

KIDS_SIZE_PATTERNS = re.compile(
    r'(?:^[/,\s|·]|(?<=^)|(?<=[/,\s|·]))(?:'
    r'(?:5[06]|6[28]|7[48]|[89]\d|1[0-7]\d)'
    r'|(?:1[0-9]|[23][0-5])(?:[/,\s|·]|$)'
    r')'
)


class VintedSnipebot:
    def __init__(self):
        self.config = self.load_config()
        self.seen_items = self.load_seen_items()
        self.telegram_bot_token = self.config.get("telegram_bot_token", "")
        self.telegram_chat_id = self.config.get("telegram_chat_id", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })
        self._size_cache = self._build_size_cache()
        self._brand_names = set()
        self._brand_ids = {}
        self._build_brand_data()
        self._shutdown = False
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        print("\n\U0001f6d1 Shutdown-Signal empfangen - breche ab...")
        self._shutdown = True
        self.save_seen_items()

    def load_config(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def load_seen_items(self):
        if SEEN_ITEMS_FILE.exists():
            with open(SEEN_ITEMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_seen_items(self):
        with open(SEEN_ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.seen_items, f, indent=2)

    def is_new_item(self, item_id):
        return item_id not in self.seen_items

    def mark_as_seen(self, item_id):
        self.seen_items[item_id] = datetime.now().isoformat()

    def _build_size_cache(self):
        sizes_config = self.config.get("sizes", {})
        cache = {}
        size_map = {
            "schuhe": ["damen_schuhe", "herren_schuhe"],
            "taschen": [],
            "blazer_anzuege": ["damen_kleidung", "herren_kleidung", "herren_anzugjacken"],
            "pullover_strick": ["damen_kleidung", "herren_kleidung"],
            "hosen_jeans": ["damen_jeans", "damen_kleidung", "herren_jeans", "herren_kleidung"],
            "guertel": ["guertel"],
            "sonnenbrillen": [],
            "tops_tshirts": ["damen_kleidung", "herren_kleidung", "herren_hemden"],
            "schals": [],
        }
        for category, size_keys in size_map.items():
            allowed = set()
            for key in size_keys:
                for size_val in sizes_config.get(key, []):
                    allowed.add(str(size_val).strip().lower())
            cache[category] = allowed
        return cache

    def _build_brand_data(self):
        brands = self.config.get("brands", {})
        for brand_name, brand_id in brands.items():
            normalized = brand_name.lower().strip()
            self._brand_names.add(normalized)
            if brand_id is not None:
                self._brand_ids[normalized] = brand_id

    def _get_brand_id_batches(self, batch_size=8):
        all_ids = [str(v) for v in self._brand_ids.values() if v is not None]
        return [all_ids[i:i + batch_size] for i in range(0, len(all_ids), batch_size)]

    def refresh_session(self):
        try:
            r = self.session.get("https://www.vinted.de", timeout=15, headers={
                "Referer": "https://www.google.de/",
            })
            return r.status_code == 200
        except Exception:
            return False

    def is_baby_kids_item(self, title):
        title_lower = title.lower()
        for word in BABY_KIDS_BLACKLIST:
            if word in title_lower:
                return True
        if KIDS_SIZE_PATTERNS.search(title_lower):
            return True
        return False

    def is_excluded_item(self, title):
        title_lower = title.lower()
        for word in EXCLUDE_KEYWORDS:
            if word in title_lower:
                return True
        return False

    def check_size_str(self, size_str, category):
        allowed_sizes = self._size_cache.get(category, set())
        if not allowed_sizes:
            return True
        size_lower = size_str.strip().lower()
        if not size_lower or size_lower in ("none", "sonstige", "einheitsgrosse", "one size"):
            return True
        for allowed in allowed_sizes:
            if allowed in size_lower or size_lower in allowed:
                return True
        return False

    @staticmethod
    def _normalize_brand(name):
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def match_brand(self, brand_from_label):
        if not brand_from_label or brand_from_label.lower() in ("keine", "unknown", "no brand", ""):
            return None
        label_norm = self._normalize_brand(brand_from_label)
        if not label_norm:
            return None
        for configured_name in self._brand_names:
            if self._normalize_brand(configured_name) == label_norm:
                return brand_from_label.strip()
        return None

    def parse_accessibility_label(self, label):
        brand_m = re.search(r'Marke:\s*([^,]+)', label)
        size_m = re.search(r'Gr.\s*e:\s*([^,]+)', label)
        price_m = re.search(r'(\d+[.,]\d{2})\s*\u20ac', label)
        condition_m = re.search(r'Zustand:\s*([^,]+)', label)
        title = label.split(',')[0].strip() if label else ""

        brand = brand_m.group(1).strip() if brand_m else ""
        size_str = size_m.group(1).strip() if size_m else ""
        condition = condition_m.group(1).strip() if condition_m else ""

        try:
            price = float(price_m.group(1).replace(",", ".")) if price_m else 0
        except (ValueError, AttributeError):
            price = 0

        return {
            "title": title,
            "brand": brand,
            "size_str": size_str,
            "price": price,
            "condition": condition,
        }

    def scrape_catalog_page(self, catalog_id, page, max_price, brand_ids_batch=None):
        try:
            params = {
                "catalog[]": catalog_id,
                "page": str(page),
                "price_to": str(max_price),
                "order": "newest_first",
            }
            if brand_ids_batch:
                params["brand_ids[]"] = brand_ids_batch

            response = self.session.get(
                "https://www.vinted.de/catalog",
                params=params,
                timeout=20,
                headers={"Referer": "https://www.vinted.de/catalog"},
            )

            if response.status_code == 403:
                return None

            if response.status_code != 200:
                return []

            html = response.text
            items = []
            seen = set()

            for m in re.finditer(
                r'product-item-id-(\d+)--overlay-link[^>]*title="([^"]*)"',
                html,
            ):
                item_id = m.group(1)
                label = html_mod.unescape(m.group(2))
                if item_id in seen:
                    continue
                seen.add(item_id)

                parsed = self.parse_accessibility_label(label)

                link_m = re.search(rf'href="(/items/{item_id}[^"]*)"', html)
                link = link_m.group(1) if link_m else f"/items/{item_id}"

                img_m = re.search(
                    rf'product-item-id-{item_id}--image[^"]*"[^>]*>.*?<img src="(https://images[^"]+)"',
                    html,
                    re.DOTALL,
                )
                image_url = img_m.group(1) if img_m else ""

                items.append({
                    "id": item_id,
                    "title": parsed["title"],
                    "brand": parsed["brand"],
                    "size_str": parsed["size_str"],
                    "price": parsed["price"],
                    "condition": parsed["condition"],
                    "url": f"https://www.vinted.de{link}",
                    "image_url": image_url,
                    "full_label": label,
                })

            return items

        except requests.exceptions.RequestException:
            return []

    def _filter_item(self, item, category):
        if not item.get("brand"):
            return False
        label = item.get("full_label", item.get("title", ""))
        title = item.get("title", "").lower()
        combined = (label + " " + title).lower()
        for word in BABY_KIDS_BLACKLIST:
            if word in combined:
                return False
        for word in EXCLUDE_KEYWORDS:
            if word in combined:
                return False
        size_str = item.get("size_str", "")
        size_lower = size_str.strip().lower()
        kids_sizes_cm = {
            "50", "56", "62", "68", "74", "80", "86", "92", "98", "104",
            "110", "116", "122", "128", "134", "140", "146", "152", "158", "164", "170",
        }
        kids_sizes_shoe = {str(i) for i in range(17, 36)}
        for part in re.split(r'[/,\s|]+', size_lower):
            part = part.strip()
            if part in kids_sizes_cm or part in kids_sizes_shoe:
                return False
        if not self.check_size_str(size_str, category):
            return False
        return True

    def send_telegram_photo(self, image_url, caption):
        if not self.telegram_bot_token or not self.telegram_chat_id or not image_url:
            return "error"

        try:
            img_resp = requests.get(
                image_url,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.vinted.de/"},
                timeout=15,
            )
            if img_resp.status_code != 200 or len(img_resp.content) < 100:
                return "error"
        except requests.exceptions.RequestException:
            return "error"

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendPhoto"

        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    data={"chat_id": self.telegram_chat_id, "caption": caption, "parse_mode": "HTML"},
                    files={"photo": ("img.webp", img_resp.content, "image/webp")},
                    timeout=15,
                )
                if response.status_code == 200:
                    return "ok"
                elif response.status_code == 429:
                    retry_after = 35
                    try:
                        retry_after = response.json().get("parameters", {}).get("retry_after", 35)
                    except Exception:
                        pass
                    print(f"      \u23f3 Rate-limit - warte {retry_after}s...")
                    time.sleep(retry_after)
                else:
                    return "error"
            except requests.exceptions.RequestException:
                time.sleep(2)

        return "error"

    def send_telegram_text(self, message):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def format_item_caption(self, item):
        cat = item.get("category", "unbekannt")
        emoji = CAT_EMOJIS.get(cat, "\U0001f4e6")
        brand = item.get("brand", "?")
        price = item.get("price", "?")
        size_str = item.get("size_str", "")
        title = item.get("title", "?")[:80]
        url = item.get("url", "")
        condition = item.get("condition", "")

        lines = [
            f"{emoji} <b>{brand}</b>",
            f"\U0001f4b0 {price}\u20ac",
            f"\U0001f4cf {size_str}" if size_str else None,
            f"\U0001f4dd {title}",
            f"\u2728 {condition}" if condition else None,
            f'<a href="{url}">\U0001f517 Link</a>',
        ]
        return "\n".join(l for l in lines if l)

    def scrape_category_with_batch(self, category, catalog_ids, brand_ids_batch):
        """Scrape one category with one brand_ids batch. Returns (sent, blocked)."""
        max_price = CAT_MAX_PRICES.get(category, 50)
        sent = 0

        for catalog_id in catalog_ids:
            if self._shutdown:
                break

            page_items = self.scrape_catalog_page(
                catalog_id, 1, max_price, brand_ids_batch=brand_ids_batch
            )

            if page_items is None:
                return sent, True

            if not page_items:
                continue

            for item in page_items:
                if self._shutdown:
                    break
                if self._filter_item(item, category):
                    matched = self.match_brand(item["brand"])
                    if matched:
                        item_id = item.get("id", "")
                        if self.is_new_item(item_id):
                            item["brand"] = matched
                            item["category"] = category
                            print(
                                f"   \U0001f195 {matched} | "
                                f"{item.get('size_str', '?')} | "
                                f"{item.get('price', '?')}\u20ac | "
                                f"{item.get('title', '?')[:40]}"
                            )
                            self.mark_as_seen(item_id)
                            self.save_seen_items()
                            image_url = item.get("image_url", "")
                            if image_url:
                                caption = self.format_item_caption(item)
                                result = self.send_telegram_photo(image_url, caption)
                                if result == "ok":
                                    sent += 1
                                time.sleep(random.uniform(2.0, 2.5))

            time.sleep(random.uniform(2, 3))

        return sent, False

    def run(self):
        print("=" * 60)
        print("\U0001f680 VINTED SNIPEBOT GESTARTET")
        print("=" * 60)
        print(f"\u23f1\ufe0f  Intervall: {self.config.get('check_interval', 180)}s")
        print(f"\U0001f3f7\ufe0f  Marken: {len(self._brand_names)} ({len(self._brand_ids)} mit ID)")
        batches = self._get_brand_id_batches()
        print(f"\U0001f4e6 Brand-Batches: {len(batches)} (je {len(batches[0]) if batches else 0} IDs)")
        print(f"\U0001f4cf Groessenfilter: aktiviert")
        print(f"\U0001f4c2 Kategorien + Max-Preise:")
        for cat, price in CAT_MAX_PRICES.items():
            print(f"   {cat}: max. {price}\u20ac")
        print("=" * 60)

        while True:
            try:
                print(f"\n\U0001f50d Suche: {datetime.now().strftime('%H:%M:%S')}")
                print("-" * 40)

                self.refresh_session()
                time.sleep(1)

                total_sent = 0
                blocked = False

                brand_batches = self._get_brand_id_batches()
                cats = list(CATALOG_IDS.items())
                random.shuffle(cats)

                for category, catalog_ids in cats:
                    if blocked or self._shutdown:
                        break

                    max_price = CAT_MAX_PRICES.get(category, 50)
                    print(f"\n\U0001f4c2 {category} ({len(catalog_ids)} Sub-Kats, max {max_price}\u20ac)")

                    for batch_idx, batch in enumerate(brand_batches):
                        if blocked or self._shutdown:
                            break

                        cat_sent, was_blocked = self.scrape_category_with_batch(
                            category, catalog_ids, batch
                        )
                        total_sent += cat_sent

                        if was_blocked:
                            blocked = True
                            break

                        if batch_idx < len(brand_batches) - 1:
                            time.sleep(random.uniform(2, 3))

                    time.sleep(random.uniform(3, 5))

                if blocked:
                    wait = random.randint(1800, 3600)
                    print(f"\n\u23f0 Cloudflare Block! Warte {wait}s (~{wait//60} Min)...")
                    self.send_telegram_text(f"\u26a0\ufe0f Cloudflare Block \u2014 warte ~{wait//60} Min")
                    self.save_seen_items()
                    time.sleep(wait)
                    continue

                if total_sent > 0:
                    print(f"\n\U0001f4e4 Fertig! {total_sent} Fotos gesendet!")
                    self.send_telegram_text(f"\u2705 Scan fertig \u2014 {total_sent} Fotos gesendet")
                else:
                    print("\n\U0001f4ed Keine neuen Angebote.")

                self.save_seen_items()

                interval = self.config.get("check_interval", 180)
                print(f"\n\u2705 Naechste Suche in {interval}s...")
                print("=" * 40)

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n\n\U0001f6d1 Bot gestoppt!")
                self.save_seen_items()
                break
            except Exception as e:
                print(f"\n\u274c Fehler: {e}")
                import traceback
                traceback.print_exc()
                print("\U0001f504 Neustart in 60s...")
                time.sleep(60)


if __name__ == "__main__":
    bot = VintedSnipebot()
    bot.run()
