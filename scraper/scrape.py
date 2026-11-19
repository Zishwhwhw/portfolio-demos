"""Book catalogue scraper (portfolio demo).

Collects every book from https://books.toscrape.com — a public sandbox site made for scraping practice —
with category, price, star rating and stock status, then writes CSV, Excel and JSON for the dashboard.

    python scrape.py                # full run, ~70 pages, ~30 s
    python scrape.py --limit 3      # only 3 categories (quick check)
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://books.toscrape.com/"
RATING = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
JUNK_CATEGORIES = {"Add a comment", "Default"}  # placeholders on the source site
OUT = Path(__file__).parent / "data"
session = requests.Session()
session.headers["User-Agent"] = "portfolio-demo-scraper/1.0 (+https://github.com/Zishwhwhw/portfolio-demos)"


@dataclass
class Book:
    title: str
    category: str
    price_gbp: float
    rating: int
    in_stock: bool
    url: str


def get(url: str, tries: int = 3) -> str:
    for attempt in range(tries):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except requests.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def parse_categories(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select(".side_categories ul li ul li a")
    return [(a.get_text(strip=True), urljoin(BASE, a["href"])) for a in links]


def clean_category(name: str) -> str:
    return "Uncategorised" if name in JUNK_CATEGORIES else name


def parse_listing(html: str, page_url: str, category: str) -> tuple[list[Book], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for pod in soup.select("article.product_pod"):
        a = pod.select_one("h3 a")
        price = pod.select_one(".price_color").get_text(strip=True)
        rating_cls = [c for c in pod.select_one(".star-rating")["class"] if c != "star-rating"]
        books.append(Book(
            title=a["title"].strip(),
            category=clean_category(category),
            price_gbp=float(price.replace("£", "").replace("Â", "")),
            rating=RATING.get(rating_cls[0], 0) if rating_cls else 0,
            in_stock="In stock" in pod.select_one(".availability").get_text(),
            url=urljoin(page_url, a["href"]),
        ))
    nxt = soup.select_one("li.next a")
    return books, urljoin(page_url, nxt["href"]) if nxt else None


def scrape_category(item: tuple[str, str]) -> list[Book]:
    name, url = item
    out = []
    while url:
        books, url = parse_listing(get(url), url, name)
        out.extend(books)
        time.sleep(0.2)  # be polite
    return out


def scrape(limit: int | None = None) -> list[Book]:
    cats = parse_categories(get(BASE))[:limit]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(scrape_category, cats))
    seen, books = set(), []
    for b in (b for chunk in results for b in chunk):
        if b.url not in seen:
            seen.add(b.url)
            books.append(b)
    return books


def save(books: list[Book]) -> None:
    OUT.mkdir(exist_ok=True)
    rows = [asdict(b) for b in books]
    with open(OUT / "books.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Books"
        ws.append(list(rows[0]))
        for r in rows:
            ws.append(list(r.values()))
        ws.auto_filter.ref = ws.dimensions
        wb.save(OUT / "books.xlsx")
    except ImportError:
        pass
    meta = {"source": BASE, "scraped_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "count": len(rows)}
    (OUT / "books.json").write_text(json.dumps({"meta": meta, "books": rows}, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only the first N categories")
    args = ap.parse_args()
    t0 = time.time()
    data = scrape(args.limit)
    save(data)
    print(f"{len(data)} books from {len({b.category for b in data})} categories in {time.time() - t0:.0f}s -> {OUT}")
