"""
main.py - Stages 1 & 2

Stage 1: Fetch once, cache once
- Downloads a catalogue page from Books to Scrape
- Sends an honest user-agent (introduces itself, like a polite visitor)
- Gives up after a few seconds if the site doesn't respond (a timeout)
- Checks the response is really OK (status code 200) before trusting it
- Saves the page to a "cache" folder, so next time we run this, we read the
  saved copy instead of bothering the site again

Stage 2: Find all three pages
- Reads the saved HTML and finds every book link on the page
- Turns each relative link ("../book-name/index.html") into a full,
  absolute URL, using Python's own URL-joining tool (never by gluing text)
- Follows the site's own "next page" link, instead of guessing there are
  exactly 3 pages
- Removes any duplicate links before moving on

Run it with:
    python src/main.py
"""

import os
import re
import json
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError

# Our honest, polite user-agent. Replace the URL with your own repo link.
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/Nidaamir083/The-Polite-Scrapper)"

TIMEOUT_SECONDS = 10
CACHE_FOLDER = "cache"
DELAY_BETWEEN_REQUESTS = 0.5  # half a second, as the assignment requires

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_PAGES = 3  # the assignment's scope: only the first 3 catalogue pages, ever

OUTPUT_FOLDER = "output"
BOOKS_FILE = os.path.join(OUTPUT_FOLDER, "books.json")
ERRORS_FILE = os.path.join(OUTPUT_FOLDER, "errors.json")


class BookRecord(BaseModel):
    """The exact shape a record must have to be considered 'clean and safe
    to store'. Any record that doesn't fit this shape is rejected, not
    silently accepted."""
    title: str
    product_url: str          # the canonical URL - this book's identity
    price_text: str           # the original text, e.g. "£51.77"
    price_gbp: float          # the cleaned number, e.g. 51.77
    availability_text: str
    rating_text: str | None
    description: str | None   # allowed to be missing - stored as null, never invented
    source_page: str
    fetched_at: str


def cache_filename_for(url):
    """Turns a URL into a safe, readable filename for the cache folder."""
    # e.g. ".../catalogue/page-2.html" -> "catalogue-page-2.html"
    safe_name = url.split("/catalogue/")[-1].replace("/", "-")
    if not safe_name:
        safe_name = "page.html"
    return os.path.join(CACHE_FOLDER, safe_name)


def fetch_page(url):
    """Returns the page's HTML text. Uses the cache if we already have it.
    Only waits politely before a REAL request - cached pages need no delay."""
    cache_path = cache_filename_for(url)

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT: {cache_path} ({len(html)} bytes)")
        return html

    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)

    if response.status_code != 200:
        raise Exception(f"Fetch failed: got status {response.status_code} for {url}")

    # The site serves UTF-8, but requests sometimes guesses the wrong encoding
    # on its own (seen as "Â£" instead of "£" in prices). Force UTF-8 explicitly.
    response.encoding = "utf-8"
    html = response.text

    os.makedirs(CACHE_FOLDER, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"FETCH: {url} -> saved to {cache_path} ({len(html)} bytes)")

    # Be polite: wait before the NEXT real request. No need to wait after a
    # cache hit, since that never left our own computer.
    time.sleep(DELAY_BETWEEN_REQUESTS)
    return html


def find_book_links(html, page_url):
    """Returns a list of absolute URLs, one per book, found on this page."""
    soup = BeautifulSoup(html, "html.parser")

    book_links = []
    # Every book on a catalogue page sits inside an <article class="product_pod">
    for article in soup.select("article.product_pod"):
        link_tag = article.select_one("h3 a")
        if link_tag and link_tag.get("href"):
            relative_url = link_tag["href"]
            # Turn "../book-name/index.html" into a full, real URL.
            absolute_url = urljoin(page_url, relative_url)
            book_links.append(absolute_url)

    return book_links


def find_next_page_url(html, page_url):
    """Returns the absolute URL of the 'next' page, or None if there isn't one."""
    soup = BeautifulSoup(html, "html.parser")
    next_tag = soup.select_one("li.next a")
    if next_tag and next_tag.get("href"):
        return urljoin(page_url, next_tag["href"])
    return None


def discover_all_book_links():
    """Walks the catalogue pages (following 'next' links) and collects every
    unique book URL found along the way, remembering which catalogue page
    each book was first discovered on (its source_page)."""
    discovered = []  # list of (book_url, source_page) tuples, in order found
    page_count = 0
    current_url = START_URL

    while current_url and page_count < MAX_PAGES:
        html = fetch_page(current_url)
        page_count += 1

        links_on_this_page = find_book_links(html, current_url)
        for link in links_on_this_page:
            discovered.append((link, current_url))

        current_url = find_next_page_url(html, current_url)

    # Remove duplicates by URL, keeping the first (url, source_page) pair seen.
    seen = {}
    for url, source_page in discovered:
        if url not in seen:
            seen[url] = source_page
    unique_books = list(seen.items())  # list of (url, source_page)

    print(f"catalogue_pages={page_count} discovered={len(discovered)} "
          f"unique_urls={len(unique_books)}")
    return unique_books


def extract_book_record(book_url, source_page):
    """Fetches one book's page and pulls out the 8 required raw fields."""
    html = fetch_page(book_url)
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.select_one("div.product_main h1")
    title = title_tag.get_text(strip=True) if title_tag else None

    price_tag = soup.select_one("p.price_color")
    price_text = price_tag.get_text(strip=True) if price_tag else None

    availability_tag = soup.select_one("p.instock.availability")
    availability_text = availability_tag.get_text(strip=True) if availability_tag else None

    # The star rating is stored as a CSS class, e.g. class="star-rating Three"
    rating_tag = soup.select_one("p.star-rating")
    rating_text = None
    if rating_tag:
        classes = rating_tag.get("class", [])
        # classes looks like ["star-rating", "Three"] - we want the word, not "star-rating"
        rating_words = [c for c in classes if c != "star-rating"]
        rating_text = rating_words[0] if rating_words else None

    # Not every book has a description. If it's missing, we store null -
    # never invent text that wasn't actually on the page.
    # NOTE: select_one() with "~" should only grab the FIRST matching <p>,
    # but we saw duplicated text in testing - using find_next_sibling
    # instead is more precise: "the very next <p> right after this div,
    # nothing else."
    description_heading = soup.select_one("div#product_description")
    description = None
    if description_heading:
        description_tag = description_heading.find_next_sibling("p")
        if description_tag:
            description = description_tag.get_text(strip=True)

    return {
        "title": title,
        "product_url": book_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def parse_price(price_text):
    """Turns '£51.77' into the number 51.77. Returns None if no number is found."""
    if not price_text:
        return None
    match = re.search(r"[\d]+\.?[\d]*", price_text)
    return float(match.group()) if match else None


def validate_record(raw_record):
    """Checks one raw record against our schema.
    Returns (valid_record_dict, None) if it passes,
    or (None, error_reason) if it fails."""
    price_gbp = parse_price(raw_record.get("price_text"))

    candidate = dict(raw_record)
    candidate["price_gbp"] = price_gbp

    try:
        validated = BookRecord(**candidate)
        return validated.model_dump(), None
    except ValidationError as error:
        # Keep the error message short and readable, not the full Pydantic dump.
        reason = "; ".join(f"{err['loc'][0]}: {err['msg']}" for err in error.errors())
        return None, reason


def save_json(path, data):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    unique_books = discover_all_book_links()

    # Use a dict keyed by the canonical product_url, so even if a URL were
    # somehow processed twice, it still counts once - this is what keeps
    # output/books.json idempotent (same 60 records every run, never 120).
    valid_records = {}
    errors = []

    for book_url, source_page in unique_books:
        raw_record = extract_book_record(book_url, source_page)

        valid_record, error_reason = validate_record(raw_record)
        if valid_record:
            valid_records[valid_record["product_url"]] = valid_record
        else:
            errors.append({"product_url": book_url, "reason": error_reason,
                            "raw_record": raw_record})

    books_list = list(valid_records.values())
    save_json(BOOKS_FILE, books_list)
    save_json(ERRORS_FILE, errors)

    print(f"detail_pages={len(unique_books)}")
    print(f"valid_records={len(books_list)}")
    print(f"invalid_records={len(errors)}")
    print(f"Saved to: {BOOKS_FILE}")
    print(f"Errors (if any) saved to: {ERRORS_FILE}")

    if books_list:
        print("\nOne complete clean record, as proof:")
        print(books_list[0])


if __name__ == "__main__":
    main()
