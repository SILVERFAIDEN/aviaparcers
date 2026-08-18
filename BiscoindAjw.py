"""
  pip install requests beautifulsoup4 --break-system-packages
"""

from __future__ import annotations

import csv
import random
import time
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scraper")

HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

@dataclass
class Offer:
    part_number: str
    supplier: str
    found: bool
    price: Optional[str] = None
    currency: Optional[str] = None
    availability: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    note: Optional[str] = None

def polite_wait(min_s: float = 1.0, max_s: float = 2.5):
    time.sleep(random.uniform(min_s, max_s))

def search_biscoind(part_number: str) -> list[Offer]:

    url = "https://www.biscoind.com/api/catalog_system/pub/products/search"
    try:
        resp = requests.get(
            url, params={"ft": part_number}, headers=HEADERS, timeout=15
        )
        resp.raise_for_status()
        items = resp.json()
    except Exception as e:
        return [Offer(part_number, "biscoind", found=False, note=f"request failed: {e}")]

    if not items:
        return [Offer(part_number, "biscoind", found=False, note="no results")]

    offers = []
    for item in items:
        product_name = item.get("productName")
        link = item.get("link") or item.get("linkText")
        for sku_item in item.get("items", []):
            sku_ref = sku_item.get("referenceId", [])
            sku_ean = sku_item.get("ean")
            sellers = sku_item.get("sellers", [])

            if not sellers:
                continue

            chosen = next((s for s in sellers if s.get("sellerDefault")), sellers[0])

            offer_data = chosen.get("commertialOffer", {})
            price = offer_data.get("Price")
            qty = offer_data.get("AvailableQuantity")
            is_available = offer_data.get("IsAvailable")

            other_sellers_note = ""
            if len(sellers) > 1:
                other_qtys = [
                    s.get("commertialOffer", {}).get("AvailableQuantity")
                    for s in sellers if s is not chosen
                ]
                other_sellers_note = f" | {len(sellers) - 1} other seller(s) with qty={other_qtys}"

            offers.append(Offer(
                part_number=part_number,
                supplier="biscoind",
                found=True,
                price=str(price) if price is not None else None,
                currency="USD",
                availability=f"qty:{qty}, is_available:{is_available}" if qty is not None else None,
                url=link,
                title=product_name,
                note=f"sku_ref={sku_ref}, ean={sku_ean}, seller_id={chosen.get('sellerId')}{other_sellers_note}",
            ))
    if not offers:
        offers.append(Offer(part_number, "biscoind", found=False, note="matched product but no seller offers"))
    return offers

def search_ajw(part_number: str) -> list[Offer]:

    search_url = "https://eventory.ajw-group.com/a/search"
    try:
        resp = requests.get(
            search_url, params={"q": part_number}, headers=HEADERS, timeout=15
        )
        resp.raise_for_status()
    except Exception as e:
        return [Offer(part_number, "AJW eventory", found=False, note=f"request failed: {e}")]

    soup = BeautifulSoup(resp.text, "html.parser")
    product_links = set()
    for a in soup.select("a[href*='/products/']"):
        href = a.get("href")
        if href:
            full_url = "https://eventory.ajw-group.com" + href if href.startswith("/") else href
            product_links.add(full_url.split("?")[0])

    if not product_links:
        return [Offer(part_number, "AJW eventory", found=False, note="no results")]

    offers = []
    for link in product_links:
        offers.append(fetch_ajw_product(part_number, link))
        polite_wait()
    return offers

def fetch_ajw_product(part_number: str, product_url: str) -> Offer:
    try:
        resp = requests.get(product_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return Offer(part_number, "AJW eventory", found=False, url=product_url, note=f"fetch failed: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")

    def meta(prop):
        tag = soup.find("meta", property=prop)
        return tag["content"] if tag and tag.has_attr("content") else None

    price = meta("og:price:amount")
    currency = meta("og:price:currency")
    title = meta("og:title")

    if not price or price == "0.00":
        return Offer(
            part_number=part_number,
            supplier="AJW eventory",
            found=True,
            price=None,
            availability="make_an_offer",
            url=product_url,
            title=title,
            note="no fixed price - negotiated via 'Make an Offer'",
        )

    availability = None
    stock_text = soup.find(string=lambda s: s and "in stock" in s.lower())
    if stock_text:
        availability = stock_text.strip()

    return Offer(
        part_number=part_number,
        supplier="AJW eventory",
        found=True,
        price=price,
        currency=currency,
        availability=availability,
        url=product_url,
        title=title,
    )

def run(part_numbers: list[str], output_path: str = "results.csv"):
    fieldnames = ["part_number", "supplier", "found", "price", "currency",
                  "availability", "url", "title", "note"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for pn in part_numbers:
            for search_fn, supplier in [(search_biscoind, "biscoind"), (search_ajw, "AJW eventory")]:
                log.info(f"Searching {pn} on {supplier}")
                try:
                    offers = search_fn(pn)
                except Exception as e:
                    offers = [Offer(pn, supplier, found=False, note=f"unexpected error: {e}")]
                for offer in offers:
                    writer.writerow(offer.__dict__)
                polite_wait()

    log.info(f"Done. Results saved to {output_path}")

if __name__ == "__main__":
    part_number = "ORB-RB-10004-APO"
    run(["ORB-RB-10004-APO", "Dk120-90", "NAS1351-3-10"], output_path="results.csv")