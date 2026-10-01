"""
main.py - Stage 1: Fetch once, cache once

What this does, in plain words:
- Downloads catalogue page 1 from Books to Scrape
- Sends an honest user-agent (introduces itself, like a polite visitor)
- Gives up after a few seconds if the site doesn't respond (a timeout)
- Checks the response is really OK (status code 200) before trusting it
- Saves the page to a "cache" folder, so next time we run this, we read the
  saved copy instead of bothering the site again

Run it with:
    python src/main.py
Run it TWICE - the first time should say FETCH, the second should say CACHE HIT.
"""

import os
import requests

# Our honest, polite user-agent. Replace the URL with your own repo link.
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/Nidaamir083/The-Polite-Scrapper)"

TIMEOUT_SECONDS = 10
CACHE_FOLDER = "cache"
PAGE_URL = "https://books.toscrape.com/catalogue/page-1.html"
CACHE_FILE = os.path.join(CACHE_FOLDER, "catalogue-page-1.html")


def fetch_page(url, cache_path):
    """Returns the page's HTML text. Uses the cache if we already have it."""

    # If we've already saved this page before, just read it back - no need
    # to ask the website again.
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            html = f.read()
        print(f"CACHE HIT: {cache_path} ({len(html)} bytes)")
        return html

    # Otherwise, go fetch it for real, politely.
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)

    # Only trust a 200. Anything else means something went wrong.
    if response.status_code != 200:
        raise Exception(f"Fetch failed: got status {response.status_code} for {url}")

    html = response.text

    # Save it so we don't have to ask again next time.
    os.makedirs(CACHE_FOLDER, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"FETCH: {url} -> saved to {cache_path} ({len(html)} bytes)")
    return html


def main():
    fetch_page(PAGE_URL, CACHE_FILE)


if __name__ == "__main__":
    main()