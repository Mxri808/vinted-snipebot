#!/usr/bin/env python3
"""
Vinted Snipebot - Luxury Brand Price Monitor
Scrapes Vinted HTML catalog pages using server-side filters (catalog[], brand_ids[], price_to).
Parses structured accessibility_label data for brand, size, price, condition.
Sends Telegram notifications when matches are found.
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
    "schuhe": [
        "2632", "543", "1049", "2630", "215",
        "1242", "1452", "1233",
    ],
    "taschen": ["156", "158", "552", "160", "157", "159", "1848", "94"],
    "guertel": ["20", "96"],
    "sonnenbrillen": ["26", "98"],
    "schals": ["89", "87"],
}

CAT_EMOJIS = {
    "schuhe": "👟", "taschen": "👜",
    "blazer_anzuege": "🤵", "pullover_strick": "🧶",
    "hosen_jeans": "👖", "guertel": "👔", "sonnenbrillen": "🕶️",
    "tops_tshirts": "👕", "schals": "🧣",
}

CAT_MAX_PRICES = {
    "schuhe": 50, "taschen": 45,
    "blazer_anzuege": 40, "pullover_strick": 30,
    "hosen_jeans": 30, "guertel": 25, "sonnenbrillen": 25,
    "tops_tshirts": 15, "schals": 10,
}

BABY_KIDS_BLACKLIST = [
    "baby", "kinder", "kids", "child", "children", "toddler",
    "enfant", "bambino", "bambina", "neonato", "bébé",
    "neo", "newborn", "infant",
    "12 mois", "18 mois", "24 mois", "36 mois",
    "monat", "monate", "jahre", "jahrig",
    "strampler", "leggin", "petit", "petite", "garçon", "fille",
    "jungen", "mädchen",
]

EXCLUDE_KEYWORDS = [
    "buch", "bücher", "book", "books", "romane", "roman", "krimi", "thriller",
    "fantasy", "sachbuch", "ratgeber", "biografie", "taschenbuch", "hardcover",
    "ebook", "lesebuch", "manga", "novel", "fiction", "lexikon", "atlas",
    "parfum", "parfüm", "eau de toilette", "eau de parfum", "eau de cologne",
    "perfume", "fragrance", "scent", "duft", "deo", "deodorant",
    "body spray", "flakon", "flacon", "düfter", "raumduft", "kerzendüfter",
    "kosmetik", "cosmetic", "make-up", "makeup", "schminke", "mascara",
    "lippenstift", "foundation", "concealer", "puder", "blush",
    "augenpalette", "eyeshadow", "eyeliner", "nagellack", "nail polish",
    "creme", "serum", "moisturizer", "lotion", "peeling",
    "gesichtsmaske", "feuchtigkeitscreme", "reinigung", "cleanser",
    "shampoo", "spülung", "conditioner", "haarpflege",
    "zahnpasta", "toothpaste", "mundwasser",
    "rasierer", "razor", "after shave", "aftershave",
    "dvd", "bluray", "blu-ray", "kassette", "cd", "vinyl",
    "spiel", "spielzeug", "toy", "puzzle", "lego", "brettspiel",
    "handyhülle", "phone case",
    "glas", "tasse", "becher", "flasche", "kerze",
    "decke", "bettwäsche", "kissen", "polster",
    "geschenktüte", "geschenktasche", "gift bag", "gift box", "geschenkbox",
    "verpackung", "packaging", "papier", "tissue", "seidenpapier",
    "sticker", "aufkleber", "aufnäher", "patch",
    "ringelsocken", "strumpf", "socken", "pantyhose",
    "maske", "mask", "schutzmaske", "ffp2",
    "tie", "krawatt", "fliege", "schlips",
    "bürste", "kamm", "bürst", "kämm",
    "pinsel", "brush", "schauf",
]

KIDS_SIZE_PATTERNS = re.compile(
    r'(?:^|[/,\s|·])(?:'
    r'(?:5[06]|6[28]|7[48]|[89]\d|1[0-7]\d)'  # cm sizes 50-170
    r'|(?:1[0-9]|[23][0-5])(?:\b|$)'  # shoe sizes 10-35
    r')(?:[/,\s|·]|$)'
)

SIZE_MAP = {
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


class VintedSnipebot:
    def __init__(self):
        self.config = self.load_config()
        self.seen_items = self.load_seen_items()
        self.telegram_bot_token = self.config.get("telegram_bot_token", "")
        self.telegram_chat_id = self.config.get("telegram_chat_id", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })
        self._size_cache = self._build_size_cache()
        self._brand_names = set()
        self._brand_ids = {}
        self._build_brand_data()
        self._shutdown = False
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        print("\n🛑 Shutdown-Signal empfangen — breche ab...")
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
        for category, size_keys in SIZE_MAP.items():
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

    def refresh_session(self):
        try:
            r = self.session.get("https://www.vinted.de", timeout=15)
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
        if not size_lower or size_lower in ("none", "sonstige", "einheitsgröße", "one size"):
            return True
        for allowed in allowed_sizes:
            if allowed in size_lower or size_lower in allowed:
                return True
        return False

    @staticmethod
    def _normalize_brand(name):
        """Lowercase + remove all non-alphanumeric chars for strict comparison."""
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
        """Parse structured accessibility_label: 'Title, Marke: Brand, Zustand: Cond, Größe: Size, Price €, TotalPrice €'"""
        brand_m = re.search(r'Marke:\s*([^,]+)', label)
        size_m = re.search(r'Größe:\s*([^,]+)', label)
        price_m = re.search(r'(\d+[.,]\d{2})\s*€', label)
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

    def scrape_catalog_page(self, catalog_id, page, max_price, brand_ids_to_use=None):
        """Scrape one page using URL params: catalog[], price_to, optionally brand_ids[].
        Returns list of item dicts or None if blocked."""
        try:
            params = {
                "catalog[]": catalog_id,
                "page": str(page),
                "price_to": str(max_price),
            }
            if brand_ids_to_use:
                params["brand_ids[]"] = brand_ids_to_use

            response = self.session.get(
                "https://www.vinted.de/catalog", params=params, timeout=20
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

                link_m = re.search(
                    rf'href="(/items/{item_id}[^"]*)"',
                    html,
                )
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

    def scrape_category(self, category, catalog_ids):
        """Scrape a category. Returns (items, blocked)."""
        max_price = CAT_MAX_PRICES.get(category, 50)
        all_items = []

        for catalog_id in catalog_ids:
            if self._shutdown:
                break
            page = 1
            while page <= 2:
                page_items = self.scrape_catalog_page(
                    catalog_id, page, max_price
                )
                if page_items is None:
                    return all_items, True
                if not page_items:
                    break
                for item in page_items:
                    if self._filter_item(item, category):
                        matched = self.match_brand(item["brand"])
                        if matched:
                            item["brand"] = matched
                            item["category"] = category
                            item["cat_max_price"] = max_price
                            all_items.append(item)
                if len(page_items) < 96:
                    break
                page += 1
                time.sleep(random.uniform(5, 8))

            time.sleep(random.uniform(6, 10))

        return all_items, False

    def _filter_item(self, item, category):
        """Return True if item passes all local filters (kids, exclude, size)."""
        if not item.get("brand"):
            return False
        label = item.get("full_label", item.get("title", ""))
        label_lower = label.lower()
        title_lower = item.get("title", "").lower()
        combined = label_lower + " " + title_lower
        for word in BABY_KIDS_BLACKLIST:
            if word in combined:
                return False
        for word in EXCLUDE_KEYWORDS:
            if word in combined:
                return False
        if self.check_kids_size_str(item["size_str"]):
            return False
        if not self.check_size_str(item["size_str"], category):
            return False
        return True

    def check_kids_size_str(self, size_str):
        size_lower = size_str.strip().lower()
        kids_sizes_cm = {
            "50", "56", "62", "68", "74", "80", "86", "92", "98", "104",
            "110", "116", "122", "128", "134", "140", "146", "152", "158", "164", "170",
        }
        kids_sizes_shoe = {
            str(i) for i in range(17, 36)
        }
        for part in re.split(r'[/,\s|·]+', size_lower):
            part = part.strip()
            if part in kids_sizes_cm or part in kids_sizes_shoe:
                return True
        return False

    def send_telegram_photo(self, image_url, caption, max_retries=2):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return "error"

        if not image_url:
            return "error"

        try:
            img_resp = requests.get(
                image_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", "Referer": "https://www.vinted.de/"},
                timeout=15,
            )
            print(f"      📷 Download {img_resp.status_code} | {len(img_resp.content)} bytes")
            if img_resp.status_code != 200 or len(img_resp.content) < 100:
                return "error"
        except requests.exceptions.RequestException as e:
            print(f"      ❌ Download-Fehler: {e}")
            return "error"

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendPhoto"

        for attempt in range(max_retries):
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
                    return "rate_limit"
                else:
                    print(f"      ❌ Telegram {response.status_code}: {response.text[:150]}")
                    return "error"
            except requests.exceptions.RequestException as e:
                print(f"      ❌ Telegram Fehler: {e}")
                time.sleep(2)

        return "error"

    def send_telegram_text(self, message, max_retries=2):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return False

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    return True
                elif response.status_code == 429:
                    print(f"   ⏳ Telegram Rate-limit — skip")
                    return False
                else:
                    print(f"   ❌ Telegram Fehler: {response.status_code}")
                    return False
            except requests.exceptions.RequestException as e:
                print(f"   ❌ Telegram Fehler: {e}")
                time.sleep(2)

        return False

    def format_item_caption(self, item):
        cat = item.get("category", "unbekannt")
        emoji = CAT_EMOJIS.get(cat, "📦")
        brand = item.get("brand", "?")
        price = item.get("price", "?")
        size_str = item.get("size_str", "")
        title = item.get("title", "?")[:80]
        url = item.get("url", "")
        condition = item.get("condition", "")

        lines = [
            f"{emoji} <b>{brand}</b>",
            f"💰 {price}€",
            f"📏 {size_str}" if size_str else None,
            f"📝 {title}",
            f"✨ {condition}" if condition else None,
            f"<a href=\"{url}\">🔗 Link</a>",
        ]
        return "\n".join(l for l in lines if l)

    def run(self):
        print("=" * 60)
        print("🚀 VINTED SNIPEBOT GESTARTET (Server-Side Filters)")
        print("=" * 60)
        print(f"⏱️  Intervall: {self.config.get('check_interval', 180)}s")
        print(f"🏷️  Marken: {len(self._brand_names)} ({len(self._brand_ids)} mit ID)")
        print(f"📏 Größenfilter: aktiviert")
        print(f"📂 Kategorien + Max-Preise:")
        for cat, price in CAT_MAX_PRICES.items():
            print(f"   {cat}: max. {price}€")
        print("=" * 60)

        is_first_run = len(self.seen_items) == 0

        while True:
            try:
                print(f"\n🔍 Suche: {datetime.now().strftime('%H:%M:%S')}")
                print("-" * 40)

                self.refresh_session()
                all_new_items = []
                blocked = False
                photo_count = 0
                fail_count = 0

                cats = list(CATALOG_IDS.items())
                random.shuffle(cats)

                for category, catalog_ids in cats:
                    if blocked or self._shutdown:
                        break

                    max_price = CAT_MAX_PRICES.get(category, 50)
                    print(f"\n📂 {category} ({len(catalog_ids)} Sub-Kats, max {max_price}€)...")

                    items, was_blocked = self.scrape_category(category, catalog_ids)

                    if was_blocked:
                        print(f"   ⚠️  Cloudflare Block — übrige Kategorien übersprungen")
                        blocked = True

                    for item in items:
                        item_id = item.get("id", "")
                        if self.is_new_item(item_id):
                            print(
                                f"   🆕 {item.get('brand', '?')} | "
                                f"{item.get('size_str', '?')} | "
                                f"{item.get('price', '?')}€ | "
                                f"{item.get('title', '?')[:40]}"
                            )
                            self.mark_as_seen(item_id)
                            all_new_items.append(item)
                            image_url = item.get("image_url", "")
                            if image_url:
                                caption = self.format_item_caption(item)
                                result = self.send_telegram_photo(image_url, caption)
                                if result == "ok":
                                    photo_count += 1
                                    time.sleep(random.uniform(2.5, 3.5))
                                elif result == "rate_limit":
                                    print(f"   ⏳ Rate-limit — warte 25s...")
                                    time.sleep(25)
                                    result2 = self.send_telegram_photo(image_url, caption)
                                    if result2 == "ok":
                                        photo_count += 1
                                        time.sleep(random.uniform(2.5, 3.5))
                                    else:
                                        fail_count += 1
                                else:
                                    fail_count += 1
                                    if fail_count >= 5:
                                        print(f"   ⛔ 5x fehlgeschlagen — stoppe Foto-Versand")
                                        break
                                    time.sleep(2)

                    self.save_seen_items()

                if blocked:
                    wait = random.randint(1800, 3600)
                    print(f"\n⏳ Cloudflare Block! Warte {wait}s (~{wait//60} Min)...")
                    self.save_seen_items()
                    time.sleep(wait)
                    continue

                if all_new_items:
                    print(f"\n📤 Fertig! {photo_count}/{len(all_new_items)} Fotos gesendet!")
                    is_first_run = False
                else:
                    print("\n📭 Keine neuen Angebote.")

                self.save_seen_items()

                interval = self.config.get("check_interval", 180)
                print(f"\n✅ Fertig! Nächste Suche in {interval}s...")
                print("=" * 40)

                time.sleep(interval)

            except KeyboardInterrupt:
                print("\n\n🛑 Bot gestoppt!")
                self.save_seen_items()
                break
            except Exception as e:
                print(f"\n❌ Fehler: {e}")
                print("🔄 Neustart in 60s...")
                time.sleep(60)


if __name__ == "__main__":
    bot = VintedSnipebot()
    bot.run()
