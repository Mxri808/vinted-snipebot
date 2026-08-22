#!/usr/bin/env python3
"""
Quick test script for Vinted Snipebot
Tests the search functionality using web scraping
"""

import re
import requests
from datetime import datetime

# Headers to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}


def test_search_web(brand_name, brand_id, max_price=50):
    """Test search using web scraping"""
    print(f"\n🔍 Teste Suche: {brand_name} (ID: {brand_id})")

    # Build Vinted catalog URL
    url = "https://www.vinted.de/catalog"
    params = {
        "search_text": brand_name.lower().replace(" ", "+"),
        "price_to": max_price,
        "order": "newest_first",
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=15)

        if response.status_code == 200:
            # Extract items from HTML (simplified parsing)
            html = response.text
            
            # Count results
            item_pattern = r'items/(\d+)'
            items_found = re.findall(item_pattern, html)
            unique_items = list(set(items_found))
            
            print(f"   ✅ {len(unique_items)} eindeutige Items gefunden!")
            
            # Extract some sample items
            title_pattern = r'"title":"([^"]+)"'
            price_pattern = r'"price":"([^"]+)"'
            
            titles = re.findall(title_pattern, html)[:3]
            prices = re.findall(price_pattern, html)[:3]
            
            for i, (title, price) in enumerate(zip(titles, prices), 1):
                print(f"   {i}. {title}")
                print(f"      Preis: {price}")
            
            return unique_items
        else:
            print(f"   ⚠️  Fehler: HTTP {response.status_code}")
            return []

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Netzwerkfehler: {e}")
        return []


def main():
    print("=" * 60)
    print("🧪 VINTED SNIPEBOT - TEST MODUS")
    print("=" * 60)
    print(f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("=" * 60)

    # Test with a few brands
    test_brands = {
        "Stone Island": 73306,
        "Gucci": 567,
        "Louis Vuitton": 60,
    }

    for brand_name, brand_id in test_brands.items():
        test_search_web(brand_name, brand_id, max_price=50)

    print("\n" + "=" * 60)
    print("✅ TEST ABGESCHLOSSEN!")
    print("=" * 60)


if __name__ == "__main__":
    main()
