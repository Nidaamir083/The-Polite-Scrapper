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
REPORT_FILE = os.path.join(OUTPUT_FOLDER, "run-report.json")

# Set this to True ONLY to prove Stage 5 works (adds one fake book URL on
# purpose, so you can see the run survive it). Set back to False afterward -
# we never test failure by hammering the real site, only by breaking our
# own side on purpose.
INJECT_TEST_FAILURE = False

# How many cached pages we read this run, vs. how many we actually fetched.
# (Tracked with a simple counter, updated inside fetch_page.)
cache_hit_count = 0


class FetchError(Exception):
    """Raised when a page could not be fetched, after any allowed retry."""
    def __init__(self, url, reason):
        self.url = url
        self.reason = reason
        super().__init__(f"{url}: {reason}")


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


def fetch_page(url, is_retry=False):
    """Returns the page's HTML text. Uses the cache if we already have it.
    Only waits politely before a REAL request - cached pages need no delay.

    On a timeout or server error (5xx), retries ONCE after a short wait.
    A 404 (doesn't exist) or 403 (blocked) is never retried - asking again
    won't change the answer, and retrying a 403 is how a polite robot
    becomes a pest.
    """
    global cache_hit_count
    cache_path = cache_filename_for(url)

    if os.path.exists(cache_path) and not is_retry:
        with open(cache_path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT: {cache_path} ({len(html)} bytes)")
        cache_hit_count += 1
        return html

    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        if not is_retry:
            print(f"   Timeout on {url}, waiting and retrying once...")
            time.sleep(1)
            return fetch_page(url, is_retry=True)
        raise FetchError(url, "timed out twice")
    except requests.exceptions.RequestException as error:
        raise FetchError(url, f"network error: {error}")

    status = response.status_code

    if status == 200:
        response.encoding = "utf-8"
        html = response.text

        os.makedirs(CACHE_FOLDER, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"FETCH: {url} -> saved to {cache_path} ({len(html)} bytes)")
        time.sleep(DELAY_BETWEEN_REQUESTS)
        return html

    if status in (404, 403):
        # Never retry these - a 404 won't exist on a second try, and
        # retrying a 403 is rude, not helpful.
        raise FetchError(url, f"status {status}, not retried")

    if status >= 500 and not is_retry:
        print(f"   Server error {status} on {url}, waiting and retrying once...")
        time.sleep(1)
        return fetch_page(url, is_retry=True)

    raise FetchError(url, f"unexpected status {status}")


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
    start_time = datetime.now(timezone.utc)
    global cache_hit_count
    cache_hit_count = 0  # reset in case main() is ever called more than once

    try:
        unique_books = discover_all_book_links()
    except FetchError as error:
        # Even a catalogue page itself could fail - if so, we can't continue
        # at all, so this is reported honestly rather than crashing silently.
        print(f"FATAL: could not load the catalogue pages: {error}")
        unique_books = []

    # Stage 5 proof: deliberately add one book URL that does not exist.
    if INJECT_TEST_FAILURE:
        fake_url = "https://books.toscrape.com/catalogue/this-book-does-not-exist_0000/index.html"
        unique_books.append((fake_url, "manually injected for testing"))
        print(f"\n[TEST] Injected a fake URL on purpose: {fake_url}\n")

    valid_records = {}
    errors = []
    failed_pages = []

    for book_url, source_page in unique_books:
        try:
            raw_record = extract_book_record(book_url, source_page)
        except FetchError as error:
            # One bad page must not kill the run: log it and move on.
            print(f"   FAILED PAGE: {error}")
            failed_pages.append({"url": book_url, "reason": error.reason})
            continue

        valid_record, error_reason = validate_record(raw_record)
        if valid_record:
            valid_records[valid_record["product_url"]] = valid_record
        else:
            errors.append({"product_url": book_url, "reason": error_reason,
                            "raw_record": raw_record})

    books_list = list(valid_records.values())
    save_json(BOOKS_FILE, books_list)
    save_json(ERRORS_FILE, errors)

    end_time = datetime.now(timezone.utc)
    duration_seconds = round((end_time - start_time).total_seconds(), 2)

    report = {
        "start_time": start_time.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "duration_seconds": duration_seconds,
        "pages_attempted": len(unique_books),
        "cache_hits": cache_hit_count,
        "valid_records": len(books_list),
        "invalid_records": len(errors),
        "failed_pages": len(failed_pages),
        "failed_page_details": failed_pages,
    }
    save_json(REPORT_FILE, report)

    print(f"\n===== RUN REPORT =====")
    print(json.dumps(report, indent=2))
    print(f"\nbooks.json: {len(books_list)} records")
    print(f"errors.json: {len(errors)} records")
    print(f"run-report.json saved to: {REPORT_FILE}")

    if books_list:
        print("\nOne complete clean record, as proof:")
        print(books_list[0])


if __name__ == "__main__":
    main()
