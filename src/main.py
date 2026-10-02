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
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Our honest, polite user-agent. Replace the URL with your own repo link.
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/Nidaamir083/The-Polite-Scrapper)"

TIMEOUT_SECONDS = 10
CACHE_FOLDER = "cache"
DELAY_BETWEEN_REQUESTS = 0.5  # half a second, as the assignment requires

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_PAGES = 3  # the assignment's scope: only the first 3 catalogue pages, ever


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
    unique book URL found along the way."""
    all_links = []
    page_count = 0
    current_url = START_URL

    # Stop at MAX_PAGES even if the site has a "next" link beyond that -
    # our scope is the first 3 catalogue pages only, never more.
    while current_url and page_count < MAX_PAGES:
        html = fetch_page(current_url)
        page_count += 1

        links_on_this_page = find_book_links(html, current_url)
        all_links.extend(links_on_this_page)

        current_url = find_next_page_url(html, current_url)

    # Remove duplicates, while keeping the order they were first found in.
    unique_links = list(dict.fromkeys(all_links))

    print(f"catalogue_pages={page_count} discovered={len(all_links)} "
          f"unique_urls={len(unique_links)}")
    return unique_links


def main():
    book_urls = discover_all_book_links()
    # Just a peek, so we can see it actually worked - not the full list.
    print("First 3 book URLs found:")
    for url in book_urls[:3]:
        print(f"  {url}")


if __name__ == "__main__":
    main()
