from urllib.parse import urljoin
from bs4 import BeautifulSoup

from main import (
    parse_price,
    find_book_links,
    extract_book_record,
    BookRecord,
)

def test_parse_price_converts_text_to_number():
    assert parse_price("£51.77") == 51.77


def test_parse_price_handles_missing_price():
    assert parse_price(None) is None
    assert parse_price("") is None


def test_relative_url_becomes_absolute():
    page_url = "https://books.toscrape.com/catalogue/page-1.html"
    fake_html = """
    <article class="product_pod">
        <h3><a href="../../a-light-in-the-attic_1000/index.html" title="A Light in the Attic">A Light...</a></h3>
    </article>
    """
    links = find_book_links(fake_html, page_url)

    assert len(links) == 1
    assert links[0].startswith("https://books.toscrape.com/")
    assert "a-light-in-the-attic_1000" in links[0]


def test_missing_description_becomes_null(monkeypatch):
    """A book page with NO 'Product Description' section at all should
    result in description=None, never an invented value."""

    fake_html_no_description = """
    <html><body>
        <div class="product_main">
            <h1>A Book With No Description</h1>
        </div>
        <p class="price_color">£10.00</p>
        <p class="instock availability">In stock (5 available)</p>
        <p class="star-rating Two"></p>
    </body></html>
    """

    monkeypatch.setattr("main.fetch_page", lambda url: fake_html_no_description)

    record = extract_book_record("https://books.toscrape.com/fake-book/index.html",
                                  "https://books.toscrape.com/catalogue/page-1.html")

    assert record["description"] is None
    assert record["title"] == "A Book With No Description"


def test_duplicate_book_links_are_removed():
    page_url = "https://books.toscrape.com/catalogue/page-1.html"
    fake_html = """
    <article class="product_pod">
        <h3><a href="../../same-book_1/index.html">Same Book</a></h3>
    </article>
    <article class="product_pod">
        <h3><a href="../../same-book_1/index.html">Same Book</a></h3>
    </article>
    """
    links = find_book_links(fake_html, page_url)

    
    unique_links = list(dict.fromkeys(links))

    assert len(links) == 2            
    assert len(unique_links) == 1     


def test_malformed_page_does_not_crash(monkeypatch):
    """A page with broken/unexpected HTML (missing price, missing rating,
    weird nesting) should not crash the whole program - it should either
    extract what it safely can, or fail validation cleanly."""

    broken_html = """
    <html><body>
        <div class="product_main">
            <h1>A Very Broken Page</h1>
        </div>
        <!-- no price_color tag at all -->
        <!-- no instock availability tag at all -->
        <!-- no star-rating tag at all -->
    </body></html>
    """

    monkeypatch.setattr("main.fetch_page", lambda url: broken_html)

    record = extract_book_record("https://books.toscrape.com/broken-book/index.html",
                                  "https://books.toscrape.com/catalogue/page-1.html")

    assert record["title"] == "A Very Broken Page"
    assert record["price_text"] is None
    assert record["availability_text"] is None
    assert record["rating_text"] is None

    try:
        BookRecord(**{**record, "price_gbp": None})
        assert False, "Expected validation to fail for a record with no price"
    except Exception:
        pass  