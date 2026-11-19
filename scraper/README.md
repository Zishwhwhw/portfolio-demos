# Book catalogue scraper + dashboard (portfolio demo)

`scrape.py` collects all 1,000 books from [books.toscrape.com](https://books.toscrape.com/) (a public sandbox made for scraping practice): title, category, price, star rating, stock and link.

- requests + BeautifulSoup, 4 parallel workers with a polite delay, retries with back-off
- follows pagination in every category, removes duplicates, merges the site's placeholder categories into "Uncategorised"
- writes `data/books.csv`, `data/books.xlsx` (with filters) and `data/books.json`
- `index.html` is a static dashboard over the JSON: summary, price by category (click to filter), price by rating, searchable and sortable table

```bash
pip install requests beautifulsoup4 openpyxl pytest
pytest -q            # 4 tests
python scrape.py     # ~11 s for 1,000 books
```

Live dashboard: https://zishwhwhw.github.io/portfolio-demos/scraper/
