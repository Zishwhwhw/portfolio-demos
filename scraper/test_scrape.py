from scrape import clean_category, parse_categories, parse_listing

LISTING = """
<article class="product_pod">
  <p class="star-rating Four"><i class="icon-star"></i></p>
  <h3><a href="a-book_12/index.html" title="A Book: Part 1">A Book...</a></h3>
  <div class="product_price"><p class="price_color">£51.77</p>
  <p class="instock availability"><i class="icon-ok"></i> In stock</p></div>
</article>
<article class="product_pod">
  <p class="star-rating One"></p>
  <h3><a href="../../../other_7/index.html" title="Other">Other</a></h3>
  <div class="product_price"><p class="price_color">Â£9.00</p>
  <p class="availability">Out of stock</p></div>
</article>
<ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>
"""
PAGE = "https://books.toscrape.com/catalogue/category/books/poetry_23/index.html"


def test_parse_listing_fields_and_next_page():
    books, nxt = parse_listing(LISTING, PAGE, "Poetry")
    assert [b.title for b in books] == ["A Book: Part 1", "Other"]
    assert books[0].price_gbp == 51.77 and books[0].rating == 4 and books[0].in_stock
    assert books[1].price_gbp == 9.0 and books[1].rating == 1 and not books[1].in_stock
    assert books[0].url == "https://books.toscrape.com/catalogue/category/books/poetry_23/a-book_12/index.html"
    assert books[1].url == "https://books.toscrape.com/catalogue/other_7/index.html"
    assert nxt == "https://books.toscrape.com/catalogue/category/books/poetry_23/page-2.html"


def test_last_page_has_no_next():
    _, nxt = parse_listing(LISTING.split("<ul")[0], PAGE, "Poetry")
    assert nxt is None


def test_parse_categories():
    html = """<div class="side_categories"><ul><li><a href="catalogue/category/books_1/index.html">Books</a>
    <ul><li><a href="catalogue/category/books/travel_2/index.html"> Travel </a></li></ul></li></ul></div>"""
    assert parse_categories(html) == [("Travel", "https://books.toscrape.com/catalogue/category/books/travel_2/index.html")]


def test_placeholder_categories_are_merged():
    assert clean_category("Add a comment") == "Uncategorised"
    assert clean_category("Default") == "Uncategorised"
    assert clean_category("Poetry") == "Poetry"
