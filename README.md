# The Polite Scraper

FlyRank Internship · Backend Track · Week 5 · Assignment A9

A small, polite scraping pipeline that downloads the first three catalogue
pages of [Books to Scrape](https://books.toscrape.com), visits all 60 book
pages, and turns messy HTML into clean, schema-checked JSON — without
crashing on a broken page, and with an honest report at the end of every run.

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

## Lane and installation

**Lane:** Python 3.10+

**Install:**
```bash
git clone https://github.com/Nidaamir083/The-Polite-Scrapper.git
cd The-Polite-Scrapper
pip install -r requirements.txt
```

## Run it

One command runs the entire pipeline — fetch, extract, normalize, validate,
store, and report:

```bash
python src/main.py
```

First run fetches 63 pages from the live site (3 catalogue + 60 book pages),
politely spaced half a second apart — takes roughly 30-40 seconds. Every run
after that reads from `cache/` instead, finishing in about a second, until
the cache is cleared.

**Output:**
- `output/books.json` — 60 clean, validated book records
- `output/errors.json` — any record that failed validation, with a reason (empty on a normal run)
- `output/run-report.json` — honest numbers from the run (see below)

## Record schema

Every record in `books.json` is checked against this shape (defined with
Pydantic in `src/main.py`) before it's allowed to be stored:

| Field | Type | Notes |
|---|---|---|
| `title` | string | |
| `product_url` | string | the canonical URL — this book's identity |
| `price_text` | string | original text, e.g. `"£51.77"` |
| `price_gbp` | float | cleaned number, e.g. `51.77` |
| `availability_text` | string | e.g. `"In stock (22 available)"` |
| `rating_text` | string or null | e.g. `"Three"` |
| `description` | string or null | `null` if the book has no description — never invented |
| `source_page` | string | which catalogue page this book was found on |
| `fetched_at` | string | UTC timestamp of when this record was scraped |

A record that doesn't fit this shape is rejected and written to
`errors.json` with a reason — it never silently enters `books.json`.

## Politeness rules followed

- **User-agent:** every request identifies itself as
  `FlyRankInternshipA9/1.0 (+https://github.com/Nidaamir083/The-Polite-Scrapper)`
- **Timeout:** every request gives up after 10 seconds rather than hanging forever
- **Delay:** at least 500ms between real requests to the site (cached pages need no delay)
- **Status check:** only a `200` is trusted as "the page arrived"; anything
  else is treated as a failed fetch, not HTML to parse
- **Cache:** every page is saved to `cache/` after its first real fetch, so
  re-running the script during development never re-asks the site for the
  same page twice
- **Smart retries:** a timeout or server error (5xx) is retried once after a
  short wait; a 404 or 403 is never retried, since asking again won't change
  the answer

## Run report (real proof)

This is actual output from a real run, with one deliberately fake book URL
added on purpose to prove the pipeline survives a broken page without
crashing (see "Stage 5" testing in `BUILDLOG` below — the fake URL was
removed before the final commit):

```json
{
  "start_time": "2026-10-03T05:25:36Z",
  "duration_seconds": 2.59,
  "pages_attempted": 61,
  "cache_hits": 63,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1,
  "failed_page_details": [
    {
      "url": "https://books.toscrape.com/catalogue/this-book-does-not-exist_0000/index.html",
      "reason": "status 404, not retried"
    }
  ]
}
```

The 60 real, valid books were unaffected by the one broken page — the run
finished normally and reported exactly what happened.

## Why this assignment needed no browser

Every piece of data this scraper collects (title, price, availability,
rating, description) is already present in the plain HTML the server sends
back — nothing is loaded afterward by JavaScript. A tool like Playwright,
which runs a full browser, would only add cost (memory, time, complexity)
here with no benefit, since there's no hidden data layer to wait for or
render.

## Honest limitations

1. **A real mistake I caught and fixed:** An early version of the
   page-discovery logic followed the site's "next" link with no upper
   bound, intending to stop after 3 pages but never actually enforcing
   that limit in code. Running it caused the script to crawl the entire
   site — all 50 catalogue pages and 1,000 book links — instead of the
   intended 3 pages and 60 books. I caught this by comparing the printed
   `catalogue_pages=` count against what the assignment expected, added an
   explicit `MAX_PAGES = 3` check to the loop, and reran it to confirm the
   corrected output (`catalogue_pages=3 discovered=60 unique_urls=60`).
   Lesson: "follow the next link" needs an explicit stopping condition in
   code, not just a comment saying where it should stop.

2. **A source-data quality issue, found and deliberately left as-is:** At
   least one book's description (*A Light in the Attic*) contains duplicated
   text directly in the site's own HTML — verified by inspecting the raw
   `<p>` tag in the cached page, not just our parsed output. The duplication
   exists in the real page itself, not in our extraction code. This was
   preserved exactly as scraped rather than corrected, since silently
   editing scraped content would violate the "trust nothing you scraped,
   never invent text" principle this assignment is built around.

3. **Small-scale retry logic.** Stage 5's retry rule is a single retry after
   a flat 1-second wait — simple and working, as the assignment asks for at
   this stage. Real production scraping (next week's assignment, A16) calls
   for proper exponential backoff and respecting a `Retry-After` header,
   which this version does not yet implement.

## Ethics note

This scraper only touches a site explicitly built and offered for scraping
practice. In general, I would: use an official API instead of scraping
whenever one exists; never bypass a login, paywall, or an explicit block;
and only collect the specific data actually needed for the task at hand —
not everything a page happens to contain.

## Project files

- `src/main.py` — the full pipeline (fetch, extract, normalize, validate, store, report)
- `output/books.json` — the 60 validated book records
- `output/errors.json` — any records that failed validation
- `output/run-report.json` — the latest run's honest numbers
- `requirements.txt` — Python dependencies
- `cache/` — saved HTML pages (not committed — see `.gitignore`)
