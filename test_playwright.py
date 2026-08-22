#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import time, re

pw = sync_playwright().start()
b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
p = b.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
p.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
p.goto("https://www.vinted.de/catalog?catalog[]=156&price_to=45&page=1&order=newest_first", wait_until="domcontentloaded", timeout=30000)
time.sleep(5)
html = p.content()
print(f"URL: {p.url}")
print(f"HTML size: {len(html)}")
items = re.findall(r'items/(\d+)', html)
print(f"Item links (items/ID): {len(set(items))}")
print(f"First 5: {list(set(items))[:5]}")
links = re.findall(r'href="(/[^"]*items/\d+[^"]*)"', html)
print(f"Full item links: {len(links)}")
print(f"First 3: {links[:3]}")
imgs = re.findall(r'src="(https://images[^"]+)"', html)
print(f"Image URLs: {len(imgs)}")
print(f"First: {imgs[0][:120] if imgs else 'none'}")
# Check for accessibility labels
labels = re.findall(r'aria-label="([^"]*[Mm]arke[^"]*)"', html)
print(f"Accessibility labels with Marke: {len(labels)}")
print(f"First label: {labels[0][:200] if labels else 'none'}")
# Check for product-item elements
products = re.findall(r'product-item-id-(\d+)', html)
print(f"product-item-id elements: {len(set(products))}")
b.close()
pw.stop()
