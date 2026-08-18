import csv
import random
import time
import requests

class StradeAdapter:

    BASE_URL = "https://marketplace.strade.aero"
    SEARCH_URL = "https://cosmos.strade.aero/product-catalog/search"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/",
            }
        )
        self._init_guest_session()

    def _init_guest_session(self):
        self.session.get(f"{self.BASE_URL}/search-parts", timeout=15)

    def polite_wait(self, min_s: float = 1.0, max_s: float = 3.0):
        time.sleep(random.uniform(min_s, max_s))

    def search_part(self, part_number: str, limit: int = 10) -> list[dict]:
        payload = {
            "query": part_number,
            "filters": [],
            "limit": limit,
            "offset": 0,
            "newQuery": True,
            "searchAlternateParts": True,
            "sortBy": "",
        }

        resp = self.session.post(self.SEARCH_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("results", []):
            location = item.get("location") or {}
            warehouse = item.get("warehouse") or {}
            results.append(
                {
                    "part_number": part_number,
                    "matched_part_number": item.get("partNumber"),
                    "title": item.get("title"),
                    "condition": item.get("condition"),
                    "serial_number": item.get("serialNumber"),
                    "outright_price": item.get("outrightPrice"),
                    "exchange_price": item.get("exchangePrice"),
                    "in_stock": item.get("inStock"),
                    "warehouse": warehouse.get("name"),
                    "country": location.get("country"),
                    "city": location.get("city"),
                    "lead_time_days": item.get("leadTime"),
                    "is_alternate_part": item.get("isAlternatePart"),
                }
            )
        return results

    def bulk_search(self, part_numbers: list[str], output_csv: str = "strade_results.csv"):
        fieldnames = [
            "part_number",
            "matched_part_number",
            "title",
            "condition",
            "serial_number",
            "outright_price",
            "exchange_price",
            "in_stock",
            "warehouse",
            "country",
            "city",
            "lead_time_days",
            "is_alternate_part",
        ]
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for pn in part_numbers:
                try:
                    results = self.search_part(pn)
                except requests.HTTPError as e:
                    print(f"[!] Ошибка для {pn}: {e}")
                    results = []

                if not results:
                    row = {fn: None for fn in fieldnames}
                    row["part_number"] = pn
                    writer.writerow(row)
                else:
                    for row in results:
                        writer.writerow(row)

                self.polite_wait()

        print(f"Парсинг успешный, результаты в {output_csv}")


if __name__ == "__main__":
    adapter = StradeAdapter()
    adapter.bulk_search(["ORB-RB-10004-APO", "Dk120-90", "NAS1351-3-10"])