#!/usr/bin/env python3
"""
Vinted Snipebot - Playwright-based to bypass Cloudflare
"""

import json
import random
import re
import signal
import time
import requests as std_requests
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

EXTRACT_ITEMS_JS = """
() => {
    const items = [];
    document.querySelectorAll('[class*="feed-grid"] a[href*="/items/"]').forEach(a => {
        const href = a.getAttribute('href') || '';
        const idMatch = href.match(/\\/items\\/(\\d+)/);
        if (!idMatch) return;
        const itemId = idMatch[1];
        if (items.some(i => i.id === itemId)) return;

        const img = a.querySelector('img');
        const imageUrl = img ? (img.src || img.dataset.src || '') : '';

        const label = a.getAttribute('aria-label') || a.getAttribute('title') || '';
        const brandM = label.match(/Marke:\\s*([^,]+)/);
        const sizeM = label.match(/Gr\\.?\\s?e:\\s*([^,]+)/);
        const priceM = label.match(/(\\d+[.,]\\d{2})\\s*€/);
        const condM = label.match(/Zustand:\\s*([^,]+)/);
        const title = label.split(',')[0].trim() || '';

        items.push({
            id: itemId,
            title: title,
            brand: brandM ? brandM[1].trim() : '',
            size_str: sizeM ? sizeM[1].trim() : '',
            price: priceM ? parseFloat(priceM[1].replace(',', '.')) : 0,
            condition: condM ? condM[1].trim() : '',
            url: 'https://www.vinted.de' + href.split('?')[0],
            image_url: imageUrl,
            full_label: label,
        });
    });
    return items;
}
"""


class VintedSnipebot:
    def __init__(self):
        self.config = self.load_config()
        self.seen_items = self.load_seen_items()
        self.telegram_bot_token = self.config.get("telegram_bot_token", "")
        self.telegram_chat_id = self.config.get("telegram_chat_id", "")
        self._size_cache = self._build_size_cache()
        self._brand_names = set()
        self._build_brand_data()
        self._shutdown = False
        self.browser = None
        self.page = None
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        print("\n\U0001f6d1 Shutdown...")
        self._shutdown = True
        self.save_seen_items()
        self._close_browser()

    def _close_browser(self):
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass

    def _init_browser(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        self.page = self.browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="de-DE",
        )
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        print("\U0001f916 Browser gestartet (Playwright Chromium)")

    def _ensure_browser(self):
        try:
            if not self.browser or not self.page:
                self._init_browser()
            self.page.goto("https://www.vinted.de", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            return True
        except Exception as e:
            print(f"\u274c Browser-Init Fehler: {e}")
            self._close_browser()
            self.browser = None
            self.page = None
            return False

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

    def scrape_catalog_page(self, catalog_id, page, max_price):
        try:
            url = f"https://www.vinted.de/catalog?catalog[]={catalog_id}&page={page}&price_to={max_price}&order=newest_first"
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2, 4))
            current_url = self.page.url
            if "/challenge" in current_url or "captcha" in current_url.lower():
                print(f"      \u26a0\ufe0f Cloudflare Challenge - warte 10s...")
                time.sleep(10)
                self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2, 4))
            html = self.page.content()
            if len(html) < 5000:
                return []
            items = self.page.evaluate(EXTRACT_ITEMS_JS)
            return items if items else []
        except Exception as e:
            print(f"      \u274c Scrape Fehler: {e}")
            return []

    def send_telegram_photo(self, image_url, caption):
        if not self.telegram_bot_token or not self.telegram_chat_id or not image_url:
            return "error"
        try:
            img_resp = std_requests.get(
                image_url,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.vinted.de/"},
                timeout=15,
            )
            if img_resp.status_code != 200 or len(img_resp.content) < 100:
                return "error"
        except Exception:
            return "error"

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendPhoto"
        for attempt in range(3):
            try:
                response = std_requests.post(
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
            except Exception:
                time.sleep(2)
        return "error"

    def send_telegram_text(self, message):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        try:
            response = std_requests.post(url, json={
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }, timeout=10)
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

    def scrape_category(self, category, catalog_ids):
        max_price = CAT_MAX_PRICES.get(category, 50)
        sent = 0
        for catalog_id in catalog_ids:
            if self._shutdown:
                break
            for page in [1, 2]:
                page_items = self.scrape_catalog_page(catalog_id, page, max_price)
                if not page_items:
                    break
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
                                    time.sleep(random.uniform(3.0, 4.0))
                time.sleep(random.uniform(2, 3))
            time.sleep(random.uniform(3, 5))
        return sent, False

    def run(self):
        print("=" * 60)
        print("\U0001f680 VINTED SNIPEBOT (Playwright)")
        print("=" * 60)
        print(f"\U0001f3f7\ufe0f  Marken: {len(self._brand_names)}")
        print(f"\U0001f4cf Groessenfilter: aktiviert")
        for cat, price in CAT_MAX_PRICES.items():
            print(f"   {cat}: max. {price}\u20ac")
        print("=" * 60)

        while True:
            try:
                if not self._ensure_browser():
                    print("\U0001f504 Browser Neustart in 60s...")
                    time.sleep(60)
                    continue

                print(f"\n\U0001f50d Suche: {datetime.now().strftime('%H:%M:%S')}")
                print("-" * 40)

                total_sent = 0
                cats = list(CATALOG_IDS.items())
                random.shuffle(cats)

                for category, catalog_ids in cats:
                    if self._shutdown:
                        break
                    max_price = CAT_MAX_PRICES.get(category, 50)
                    print(f"\n\U0001f4c2 {category} ({len(catalog_ids)} Sub-Kats, max {max_price}\u20ac)")
                    cat_sent, _ = self.scrape_category(category, catalog_ids)
                    total_sent += cat_sent
                    time.sleep(random.uniform(2, 3))

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
                self._close_browser()
                self.browser = None
                self.page = None
                print("\U0001f504 Neustart in 60s...")
                time.sleep(60)


if __name__ == "__main__":
    bot = VintedSnipebot()
    bot.run()
