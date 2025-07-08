"""Scraping utilities for Toyama event sites.

This module provides site-specific scraping helpers and a single public
`all_events()` generator that yields normalised dictionaries for each
upcoming event found on the three target sites.

Returned dict structure
----------------------
{
    "title": str,
    "start": datetime.date,
    "end": datetime.date | None,
    "location": str,
    "url": str,          # Event detail page
    "site": str          # info-toyama | toyama-life | toyamadays
}
"""

from __future__ import annotations

import re
import hashlib
from datetime import datetime, date
from typing import Generator, Iterable, Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

_DEF_YEAR = datetime.now().year


def _parse_single_date(text: str) -> date:
    """Parse Japanese/ISO date strings like '2025年7月20日', '7/20', '2025-07-20'."""
    # Replace Japanese characters that confuse parser
    cleaned = re.sub(r"[（(][^)）]*[)）]", "", text)  # remove (土) 等
    cleaned = (
        cleaned.replace("年", "/")
        .replace("月", "/")
        .replace("日", "")
        .replace(".", "/")
        .strip()
    )

    try:
        # dateutil fails when year is missing; add current year
        if re.match(r"^\d{1,2}/\d{1,2}$", cleaned):
            cleaned = f"{_DEF_YEAR}/{cleaned}"
        return dtparser.parse(cleaned, fuzzy=True).date()
    except (ValueError, OverflowError):
        raise ValueError(f"Could not parse date string: '{text}'")


def parse_date_range(text: str) -> tuple[date, Optional[date]]:
    """Return (start, end) date tuple.

    Accepts strings like:
        '7/20(土) ～ 7/22(月)'
        '2025年7月20日 – 7月22日'
        '2025/07/20' (single date)
    """
    # Normalise separator variants
    norm = (
        text.replace("〜", "~")
        .replace("～", "~")
        .replace("–", "~")
        .replace("—", "~")
        .replace("-", "~")
    )
    parts = [p.strip() for p in norm.split("~") if p.strip()]

    if len(parts) == 1:
        start = _parse_single_date(parts[0])
        return start, None

    # Determine start first
    start = _parse_single_date(parts[0])

    second = parts[1]
    # If second part lacks month info like "7日", prepend month from start
    if re.match(r"^\d{1,2}日?$", second):
        second = f"{start.month}月{second}"
    # If also lacks year, prepend
    if re.match(r"^\d{1,2}月\d{1,2}日?$", second):
        second = f"{start.year}年{second}"

    try:
        end = _parse_single_date(second)
    except ValueError:
        end = None
    return start, end


# ---------------------------------------------------------------------------
# Site-specific scrapers
# ---------------------------------------------------------------------------

def fetch_info_toyama() -> Iterable[dict]:
    """Yield events from https://www.info-toyama.com/events

    ページには <div class="o-digest--tile"> 以下に <li class="o-digest--tile__item"> が
    並び、その中の <a class="o-digest--tile__anchor"> にタイトル・日付などが
    含まれている。
    """
    url = "https://www.info-toyama.com/events"
    html = requests.get(url, headers=HEADERS, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    for li in soup.select("li.o-digest--tile__item"):
        a = li.select_one("a.o-digest--tile__anchor")
        if not a:
            continue
        title_el = a.select_one("h2.o-digest--tile__title")
        date_el = a.select_one("dl.o-digest--list__date dd")
        if not title_el or not date_el:
            continue

        title = title_el.get_text(strip=True)
        try:
            start, end = parse_date_range(date_el.get_text(" ", strip=True))
        except ValueError:
            continue

        full_url = a.get("href")
        location = ""  # サマリーページに場所情報なし

        yield {
            "title": title,
            "start": start,
            "end": end,
            "location": location,
            "url": full_url,
            "site": "info-toyama",
        }


def fetch_toyamalife() -> Iterable[dict]:
    """Yield events from https://toyama-life.com/event-calendar-toyama/

    記事本文にイベントごとに <table> 要素が挿入され、1 行目 (td colspan)
    の <strong><span> にタイトル文字列、続く行の『日時』セルに開催日が入っている。
    """
    url = "https://toyama-life.com/event-calendar-toyama/"
    html = requests.get(url, headers=HEADERS, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.select("table"):
        header_td = table.select_one("tr td[colspan]")
        if not header_td:
            continue
        strong = header_td.find("strong") or header_td
        title = strong.get_text(" ", strip=True)
        if "【終了】" in title:
            continue

        # Find date row
        date_row = None
        for tr in table.select("tr"):
            first_td = tr.find("td")
            if first_td and re.search("日時|開催日", first_td.get_text(strip=True)):
                date_row = tr
                break
        if not date_row:
            continue
        cells = date_row.find_all("td")
        if len(cells) < 2:
            continue
        date_text = cells[1].get_text(" ", strip=True)
        try:
            start, end = parse_date_range(date_text)
        except ValueError:
            continue

        # location row
        location = ""
        for tr in table.select("tr"):
            first_td = tr.find("td")
            if first_td and re.search("会場|場所", first_td.get_text(strip=True)):
                tds = tr.find_all("td")
                if len(tds) >= 2:
                    location = tds[1].get_text(" ", strip=True)
                break

        yield {
            "title": title,
            "start": start,
            "end": end,
            "location": location,
            "url": url + "#" + re.sub(r"\s+", "-", title)[:30],
            "site": "toyama-life",
        }


def fetch_toyamadays() -> Iterable[dict]:
    """Yield events from https://toyamadays.com/event/ (livedoor blog)."""
    base = "https://toyamadays.com/event/"
    html = requests.get(base, headers=HEADERS, timeout=20).text
    soup = BeautifulSoup(html, "html.parser")

    for article in soup.select("article.article-archive"):
        title_el = article.select_one("h1.article-archive-title a")
        time_el = article.select_one("p.article-archive-date time[datetime]")
        if not title_el or not time_el:
            continue
        title = title_el.get_text(strip=True)
        date_text = time_el.get("datetime") or time_el.get_text(strip=True)
        try:
            start, end = parse_date_range(date_text)
        except ValueError:
            continue
        full_url = title_el.get("href")

        yield {
            "title": title,
            "start": start,
            "end": end,
            "location": "",
            "url": full_url,
            "site": "toyamadays",
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def all_events() -> Generator[dict, None, None]:
    """Yield de-duplicated events aggregated from all scrapers."""

    seen: set[str] = set()

    def _ev_key(ev: dict) -> str:
        raw = f"{ev['title']}{ev['start']}"
        return hashlib.sha256(raw.encode()).hexdigest()

    for fetcher in (fetch_info_toyama, fetch_toyamalife, fetch_toyamadays):
        for ev in fetcher():
            key = _ev_key(ev)
            if key in seen:
                continue
            seen.add(key)
            yield ev


if __name__ == "__main__":
    import json, sys

    events = list(all_events())
    json.dump(events, sys.stdout, ensure_ascii=False, indent=2, default=str)
