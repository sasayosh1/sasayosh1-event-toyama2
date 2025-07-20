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
from datetime import datetime, date, timedelta
from typing import Generator, Iterable, Optional
from difflib import SequenceMatcher

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


def normalize_title(title: str) -> str:
    """Ultra-aggressive event title normalization for duplicate detection."""
    # Convert to lowercase for processing
    normalized = title.lower()
    
    # Japanese-English festival name mappings (expanded)
    ja_en_mappings = {
        'tanabata': '七夕',
        'matsuri': 'まつり',
        'festival': 'まつり',
        'hanabi': '花火',
        'fireworks': '花火',
        'owara': 'おわら',
        'kaze': '風',
        'bon': '盆',
        'bon festival': '風の盆',
        'toyama': '富山',
        'takaoka': '高岡',
        'toide': '戸出',
        'uozu': '魚津',
        'kurobe': '黒部',
        'namerikawa': '滑川',
        'imizu': '射水',
        'himi': '氷見',
        'nanto': '南砺',
        'tonami': '砺波',
        'market': 'マーケット',
        'marche': 'マルシェ',
        'asaichi': '朝市',
        'pool': 'プール',
        'open': 'オープン',
        'summer': '夏',
        'natsu': '夏',
        'aki': '秋',
        'fuyu': '冬',
        'haru': '春'
    }
    
    # Apply Japanese-English mappings
    for en, ja in ja_en_mappings.items():
        normalized = normalized.replace(en, ja)
    
    # Ultra-aggressive removal patterns
    removal_patterns = [
        # Numbers and years (more comprehensive)
        r'^第\d+回\s*', r'\s*第\d+回$',  # 第XX回
        r'^令和\d+年?\s*', r'\s*令和\d+年?$',  # 令和X年
        r'^平成\d+年?\s*', r'\s*平成\d+年?$',  # 平成X年  
        r'^20\d{2}年?\s*', r'\s*20\d{2}年?$',  # 20XX年
        r'^\d{4}年?\s*', r'\s*\d{4}年?$',  # YYYY年
        r'^市制\d+周年記念\s*', r'\s*市制\d+周年記念$',  # 市制XX周年記念
        
        # Event details and descriptions (expanded)
        r'\s*～.*$', r'\s*-.*$', r'\s*\–.*$', r'\s*—.*$',  # Remove everything after separators
        r'\s*【[^】]*】.*$', r'^【[^】]*】\s*',  # Remove detailed descriptions
        r'\s*［[^］]*］.*$', r'^［[^］]*］\s*',  # Remove brackets
        r'\s*〈[^〉]*〉.*$', r'^〈[^〉]*〉\s*',  # Remove angle brackets
        r'\s*\([^)]*\)$', r'^\([^)]*\)\s*',  # Remove parentheses content
        r'\s*（[^）]*）$',  # Remove Japanese parentheses at end only
        
        # Location and venue specifics (moderate removal)
        r'^（[^）]*）\s*',  # Remove city/location prefixes at start only
        r'\s*会場.*$', r'\s*にて.*$', r'\s*で開催.*$',  # Remove venue info
        r'\s*at\s+.*$', r'\s*in\s+.*$',  # Remove English venue info
        
        # Time and schedule details (expanded)
        r'\s*\d{1,2}:\d{2}.*$',  # Remove time information
        r'\s*午前\d+時.*$', r'\s*午後\d+時.*$',  # Remove Japanese time
        r'\s*\d+月\d+日.*$',  # Remove specific dates from title
        r'\s*開催期間.*$', r'\s*開催日.*$',  # Remove schedule info
        
        # Additional event details (expanded)
        r'\s*予約.*$', r'\s*受付.*$', r'\s*販売.*$',  # Remove booking info
        r'\s*with\s+.*$', r'\s*&\s+.*$',  # Remove collaboration details
        r'\s*チケット.*$', r'\s*入場.*$',  # Remove ticket info
        r'\s*他\s*\d+件.*$',  # Remove "other X events" info
        r'\s*\d+件.*$',  # Remove count info
    ]
    
    for pattern in removal_patterns:
        normalized = re.sub(pattern, '', normalized)
    
    # Normalize punctuation and whitespace (more aggressive)
    normalized = re.sub(r'[　\s]+', ' ', normalized)  # Normalize whitespace
    normalized = re.sub(r'[・·•\-\–\—〜～]', '', normalized)  # Remove separators
    normalized = re.sub(r'[！!？?。、，,：:；;]', '', normalized)  # Remove punctuation
    normalized = re.sub(r'["\'"\'"]', '', normalized)  # Remove quotes
    normalized = re.sub(r'[『』「」]', '', normalized)  # Remove Japanese quotes
    
    # Remove only administrative location indicators, not event-specific places
    location_removal = [
        r'\s*富山県\s*', r'\s*高岡市\s*', r'\s*魚津市\s*', r'\s*黒部市\s*',
        r'\s*滑川市\s*', r'\s*射水市\s*', r'\s*氷見市\s*', r'\s*南砺市\s*',
        r'\s*砺波市\s*', r'\s*小矢部市\s*', r'\s*上市町\s*', r'\s*立山町\s*',
        r'\s*通り\s*', r'\s*商店街\s*',
        # Keep place names that are part of event identity like '戸出', '八尾', etc.
    ]
    
    for pattern in location_removal:
        normalized = re.sub(pattern, '', normalized)
    
    # Final cleanup (more thorough)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Remove single character artifacts
    if len(normalized) <= 1:
        return normalized
    
    return normalized


def events_similar(event1: dict, event2: dict) -> bool:
    """Ultra-aggressive duplicate detection with multiple criteria."""
    # Normalize titles
    title1 = normalize_title(event1['title'])
    title2 = normalize_title(event2['title'])
    
    # Skip if either title is empty after normalization
    if not title1 or not title2:
        return False
    
    # Calculate title similarity
    similarity = SequenceMatcher(None, title1, title2).ratio()
    
    # Check date proximity (same date or within 7 days for recurring events)
    date_diff = abs((event1['start'] - event2['start']).days)
    date_similar = date_diff <= 7
    
    # Check if one title contains the other (subset matching)
    longer_title = title1 if len(title1) >= len(title2) else title2
    shorter_title = title2 if title1 == longer_title else title1
    contains_other = shorter_title in longer_title
    
    # Additional ultra-aggressive checks
    # Check if titles are very similar even after different normalization
    title1_basic = event1['title'].lower().strip()
    title2_basic = event2['title'].lower().strip()
    basic_similarity = SequenceMatcher(None, title1_basic, title2_basic).ratio()
    
    # Check for common event patterns (朝市, まつり, etc.)
    common_patterns = ['朝市', 'まつり', 'マーケット', 'マルシェ', 'プール', 'オープン', '花火大会']
    has_common_pattern = any(pattern in title1 and pattern in title2 for pattern in common_patterns)
    
    # Ultra-aggressive: Check for exact title match even if from different sites
    # (This catches cases like "戸出七夕まつり" vs "（高岡市）第60回 戸出七夕まつり")
    raw_title1 = event1['title'].replace('（', '').replace('）', '').replace('第', '').replace('回', '')
    raw_title2 = event2['title'].replace('（', '').replace('）', '').replace('第', '').replace('回', '')
    raw_similarity = SequenceMatcher(None, raw_title1.lower(), raw_title2.lower()).ratio()
    
    # Consider them duplicates if:
    # 1. Exact match after normalization
    # 2. High title similarity (>0.75) and same/close dates
    # 3. Very high title similarity (>0.8) regardless of date
    # 4. One title contains the other and dates are similar
    # 5. Basic similarity very high (>0.85) even without normalization
    # 6. Common pattern + high similarity + date proximity
    # 7. Raw similarity very high (>0.9) - catches prefixed versions
    if title1 == title2:
        return True
    elif contains_other and date_similar and len(shorter_title) >= 2:
        return True
    elif similarity > 0.8:
        return True  
    elif similarity > 0.75 and date_similar:
        return True
    elif basic_similarity > 0.85 and date_similar:
        return True
    elif has_common_pattern and similarity > 0.6 and date_similar:
        return True
    elif raw_similarity > 0.9 and date_similar:
        return True
    
    return False


def merge_events(event1: dict, event2: dict) -> dict:
    """Merge two similar events, keeping the best information."""
    # Prefer the event with more complete information
    def event_completeness_score(ev):
        score = 0
        if ev.get('location') and ev['location'].strip():
            score += 2
        if ev.get('url') and ev['url'].startswith('http'):
            score += 1
        if ev.get('end') is not None:
            score += 1
        score += len(ev.get('title', '')) / 100  # Longer titles often more descriptive
        return score
    
    score1 = event_completeness_score(event1)
    score2 = event_completeness_score(event2)
    
    # Use the event with higher completeness score as base
    if score1 >= score2:
        base, other = event1, event2
    else:
        base, other = event2, event1
    
    # Merge information
    merged = base.copy()
    
    # Use better location if available
    if not merged.get('location') and other.get('location'):
        merged['location'] = other['location']
    
    # Use earlier start date
    if other['start'] < merged['start']:
        merged['start'] = other['start']
    
    # Use later end date if both have end dates
    if merged.get('end') and other.get('end'):
        if other['end'] > merged['end']:
            merged['end'] = other['end']
    elif not merged.get('end') and other.get('end'):
        merged['end'] = other['end']
    
    # Combine site information
    if 'sites' not in merged:
        merged['sites'] = [merged['site']]
    if other['site'] not in merged['sites']:
        merged['sites'].append(other['site'])
    
    return merged


def _parse_single_date(text: str, debug: bool = False) -> date:
    """Parse Japanese/ISO date strings like '2025年7月20日', '7/20', '2025-07-20'."""
    original_text = text
    
    # Replace Japanese characters that confuse parser
    cleaned = re.sub(r"[（(][^)）]*[)）]", "", text)  # remove (土) 等
    # Remove special Japanese weekday characters (㈪㈫㈬㈭㈮㈯㈰)
    cleaned = re.sub(r"[㈪㈫㈬㈭㈮㈯㈰]", "", cleaned)
    cleaned = (
        cleaned.replace("年", "/")
        .replace("月", "/")
        .replace("日", "")
        .replace(".", "/")
        .strip()
    )
    
    if debug:
        print(f"Date parsing: '{original_text}' -> '{cleaned}'")

    try:
        # Smart year inference for month/day only formats
        if re.match(r"^\d{1,2}/\d{1,2}$", cleaned):
            month, day = map(int, cleaned.split("/"))
            current = date.today()
            current_year = current.year
            
            if debug:
                print(f"  Inferring year for {month}/{day} (today: {current})")
            
            # Try current year first
            try:
                candidate = date(current_year, month, day)
                original_candidate = candidate
                
                # If the date is in the past (more than 30 days ago), try next year
                # Exception: If we're in November/December and the date is Jan-April, 
                # it's likely a next year event
                if current.month >= 11 and month <= 4:
                    candidate = date(current_year + 1, month, day)
                    if debug:
                        print(f"  Year-end rule: {original_candidate} -> {candidate}")
                elif candidate < current - timedelta(days=30):
                    candidate = date(current_year + 1, month, day)
                    if debug:
                        print(f"  Past date rule: {original_candidate} -> {candidate}")
                
                cleaned = candidate.strftime("%Y/%m/%d")
                if debug:
                    print(f"  Final inferred date: {candidate}")
            except ValueError:
                # Invalid date (e.g., Feb 30), try next year
                try:
                    candidate = date(current_year + 1, month, day)
                    cleaned = candidate.strftime("%Y/%m/%d")
                    if debug:
                        print(f"  Invalid current year, using next year: {candidate}")
                except ValueError:
                    # Still invalid, let dateutil handle the error
                    cleaned = f"{current_year}/{cleaned}"
                    if debug:
                        print(f"  Still invalid, falling back to: {cleaned}")
        
        parsed_date = dtparser.parse(cleaned, fuzzy=True).date()
        
        # Final validation: reject dates more than 2 years in the future
        if parsed_date > date.today() + timedelta(days=730):
            raise ValueError(f"Date too far in future: {parsed_date}")
            
        return parsed_date
    except (ValueError, OverflowError) as e:
        raise ValueError(f"Could not parse date string: '{text}' -> '{cleaned}': {e}")


def parse_date_range(text: str, debug: bool = False) -> tuple[date, Optional[date]]:
    """Return (start, end) date tuple.

    Accepts strings like:
        '7/20(土) ～ 7/22(月)'
        '2025年7月20日 – 7月22日'
        '2025/07/20' (single date)
        '2025年8月1日㈮、2日㈯、3日㈰' (multiple dates)
    """
    if debug:
        print(f"Parsing date range: '{text}'")
    
    # Remove extra information after specific patterns
    text = re.sub(r'[※。].+$', '', text)  # Remove notes starting with ※ or 。
    text = re.sub(r'\s+[^0-9年月日\(\)（）～〜\-–—]+は[^。]*', '', text)  # Remove "XXXは..." explanations
    
    # Handle adjacent date format like "2025年7月26日（土）27日（日）"
    adjacent_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)[^0-9]*(\d{1,2}日)', text)
    if adjacent_match:
        try:
            first_date_str = adjacent_match.group(1)
            second_date_str = adjacent_match.group(2)
            
            if debug:
                print(f"  Adjacent dates found: '{first_date_str}' and '{second_date_str}'")
            
            start = _parse_single_date(first_date_str, debug)
            
            # Add month and year to second date
            second_with_month = f"{start.year}年{start.month}月{second_date_str}"
            end = _parse_single_date(second_with_month, debug)
            
            if end >= start:
                return start, end
        except ValueError:
            pass  # Fall through to normal processing
    
    # Handle multiple dates separated by ・ or 、
    if '・' in text or '、' in text:
        # Extract first date as start, try to find last reasonable date as end
        multi_parts = re.split(r'[・、]', text)
        if len(multi_parts) >= 2:
            try:
                first_part = multi_parts[0].strip()
                # Find the last part that looks like a date
                last_part = None
                for part in reversed(multi_parts[1:]):
                    part = part.strip()
                    if re.search(r'\d+日?', part):
                        last_part = part
                        break
                
                if last_part and debug:
                    print(f"  Multiple dates found: '{first_part}' and '{last_part}'")
                
                start = _parse_single_date(first_part, debug)
                
                if last_part:
                    # Handle cases like "2日㈯" where we need to add month/year from start
                    if re.match(r'^\d+日?', last_part):
                        last_part = f"{start.month}月{last_part}"
                    if re.match(r'^\d+月\d+日?', last_part):
                        last_part = f"{start.year}年{last_part}"
                    
                    try:
                        end = _parse_single_date(last_part, debug)
                        if end >= start:  # Ensure valid range
                            return start, end
                    except ValueError:
                        pass
                
                return start, None
            except ValueError:
                pass  # Fall through to normal processing
    
    # Normalise separator variants
    norm = (
        text.replace("〜", "~")
        .replace("～", "~")
        .replace("–", "~")
        .replace("—", "~")
        .replace("-", "~")
    )
    parts = [p.strip() for p in norm.split("~") if p.strip()]
    
    if debug:
        print(f"  Split into parts: {parts}")

    if len(parts) == 1:
        start = _parse_single_date(parts[0], debug)
        if debug:
            print(f"  Single date result: {start}")
        return start, None

    # Determine start first
    start = _parse_single_date(parts[0], debug)
    if debug:
        print(f"  Start date: {start}")

    second = parts[1]
    original_second = second
    
    # If second part lacks month info like "7日", prepend month from start
    if re.match(r"^\d{1,2}日?$", second):
        second = f"{start.month}月{second}"
        if debug:
            print(f"  Added month to end date: '{original_second}' -> '{second}'")
    # If also lacks year, prepend
    if re.match(r"^\d{1,2}月\d{1,2}日?$", second):
        second = f"{start.year}年{second}"
        if debug:
            print(f"  Added year to end date: -> '{second}'")

    try:
        end = _parse_single_date(second, debug)
        if debug:
            print(f"  End date: {end}")
    except ValueError as e:
        if debug:
            print(f"  Failed to parse end date '{second}': {e}")
        end = None
    
    if debug:
        print(f"  Final range: {start} -> {end}")
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
        date_text = date_el.get_text(" ", strip=True)
        try:
            start, end = parse_date_range(date_text, debug=False)
        except ValueError as e:
            print(f"Warning: Skipping event '{title}' - date parse error: {e}")
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
            start, end = parse_date_range(date_text, debug=False)
        except ValueError as e:
            print(f"Warning: Skipping event '{title}' - date parse error: {e}")
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

        # Find event detail URL from any link in the table
        event_url = url  # Default to main page
        for tr in table.select("tr"):
            # Look for links in all table cells
            links = tr.find_all("a", href=True)
            for link in links:
                href = link.get("href")
                link_text = link.get_text(strip=True)
                # Skip if it's just the page anchor or if text is too generic
                if (href and href.startswith("http") and 
                    not href.startswith(url) and 
                    link_text and len(link_text) > 3 and
                    not re.search(r"^(こちら|詳細|more|→)$", link_text, re.I)):
                    event_url = href
                    break
            if event_url != url:
                break

        yield {
            "title": title,
            "start": start,
            "end": end,
            "location": location,
            "url": event_url,
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
            start, end = parse_date_range(date_text, debug=False)
        except ValueError as e:
            print(f"Warning: Skipping event '{title}' - date parse error: {e}")
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
    """Yield intelligently de-duplicated events aggregated from all scrapers."""
    
    events_list = []
    
    # Collect all events first
    for fetcher in (fetch_info_toyama, fetch_toyamalife, fetch_toyamadays):
        for ev in fetcher():
            events_list.append(ev)
    
    # Advanced deduplication
    deduplicated = []
    
    for current_event in events_list:
        # Check if current event is similar to any existing deduplicated event
        merged_with_existing = False
        
        for i, existing_event in enumerate(deduplicated):
            if events_similar(current_event, existing_event):
                # Merge the events and replace the existing one
                merged_event = merge_events(existing_event, current_event)
                deduplicated[i] = merged_event
                merged_with_existing = True
                break
        
        # If not merged with existing, add as new event
        if not merged_with_existing:
            deduplicated.append(current_event)
    
    # Sort by start date
    deduplicated.sort(key=lambda ev: ev['start'])
    
    for ev in deduplicated:
        yield ev


if __name__ == "__main__":
    import json, sys
    
    # Enable debug mode if --debug flag is provided
    debug_mode = "--debug" in sys.argv
    
    if debug_mode:
        print("=== DEBUG MODE ENABLED ===")
        print(f"Current date: {date.today()}")
        print()
    
    # Test date parsing if --test-dates flag is provided
    if "--test-dates" in sys.argv:
        test_dates = [
            "7/20", "12/25", "1/15", "2025年8月10日", 
            "7/20(土)～7/22(月)", "2025年12月31日～2026年1月3日"
        ]
        for test_date in test_dates:
            try:
                if "～" in test_date or "-" in test_date:
                    start, end = parse_date_range(test_date, debug=True)
                    print(f"Range: {test_date} -> {start} to {end}")
                else:
                    result = _parse_single_date(test_date, debug=True)
                    print(f"Single: {test_date} -> {result}")
                print()
            except Exception as e:
                print(f"ERROR: {test_date} -> {e}")
                print()
        sys.exit(0)
    
    # Test deduplication if --test-dedup flag is provided
    if "--test-dedup" in sys.argv:
        print("=== TESTING DEDUPLICATION ===")
        
        # Test examples
        test_events = [
            {"title": "第71回北日本新聞納涼花火高岡会場", "start": date(2025, 8, 4), "end": None, "location": "", "url": "http://test1.com", "site": "site1"},
            {"title": "北日本新聞納涼花火大会　高岡会場", "start": date(2025, 8, 4), "end": None, "location": "高岡市", "url": "http://test2.com", "site": "site2"},
            {"title": "越中八尾 おわら風の盆", "start": date(2025, 9, 1), "end": date(2025, 9, 3), "location": "", "url": "http://test3.com", "site": "site1"},
            {"title": "おわら風の盆", "start": date(2025, 9, 1), "end": None, "location": "八尾町", "url": "http://test4.com", "site": "site2"},
        ]
        
        for i, ev1 in enumerate(test_events):
            for j, ev2 in enumerate(test_events[i+1:], i+1):
                similar = events_similar(ev1, ev2)
                print(f"Event {i+1} vs Event {j+1}:")
                print(f"  '{ev1['title']}' vs '{ev2['title']}'")
                print(f"  Normalized: '{normalize_title(ev1['title'])}' vs '{normalize_title(ev2['title'])}'")
                print(f"  Similar: {similar}")
                if similar:
                    merged = merge_events(ev1, ev2)
                    print(f"  Merged: {merged}")
                print()
        
        sys.exit(0)

    events = list(all_events())
    
    if debug_mode:
        print(f"\n=== FOUND {len(events)} EVENTS AFTER DEDUPLICATION ===")
        for i, event in enumerate(events, 1):
            print(f"{i}. {event['title']}")
            print(f"   Date: {event['start']} - {event['end']}")
            if event.get('location'):
                print(f"   Location: {event['location']}")
            if event.get('sites'):
                print(f"   Sources: {', '.join(event['sites'])}")
            else:
                print(f"   Site: {event['site']}")
            print(f"   URL: {event['url']}")
            print()
    
    json.dump(events, sys.stdout, ensure_ascii=False, indent=2, default=str)
