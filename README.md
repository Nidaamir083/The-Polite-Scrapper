# The-Polite-Scrapper
Build a small, polite scraping pipeline
## Target Classification

**Site:** https://books.toscrape.com

**Why this site:** The site's homepage explicitly states: "This is a demo website
for web scraping purposes. Prices and ratings here were randomly assigned and
have no real meaning." This confirms it is a sandbox built specifically for
scraping practice, not a real business whose data I'd be taking without
permission.

**Scope:** The first 3 catalogue pages only, and the ~60 individual book pages
linked from them. No other pages on the site will be visited.

**robots.txt result:** Requested `https://books.toscrape.com/robots.txt` —
result: 404 Not Found. No robots file exists for this site. A missing robots
file is not the same as permission; it simply means there is no explicit
machine-readable rule to follow. My permission to scrape this site comes from
its own stated purpose as a scraping sandbox (see above), not from the absence
of a robots.txt file.

**What data is collected:** For each book: title, product URL, price, stock
availability, star rating, and description — all data already publicly
displayed on the page itself.

I will not reuse this code on another site without checking its rules and
terms first.