#!/usr/bin/env python3
"""
Fix existing Google Calendar events with toyama-life.com URLs.

This script identifies events that currently have generic toyama-life.com URLs
and updates them with specific event detail URLs by re-scraping the current data.
"""

import os
import base64
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from scrape import fetch_toyamalife, HEADERS

# Calendar ID (same as in gcal_sync.py)
CALENDAR_ID = "6a7ccfd766517b3ca44ceb7c79a51a77e4b3511003b2b6c86a3ba3e0e1e0e88f@group.calendar.google.com"

def get_google_credentials():
    """Get Google API credentials from environment variables."""
    token_b64 = os.environ.get("GOOGLE_TOKEN_B64")
    credentials_b64 = os.environ.get("GOOGLE_CREDENTIALS_B64")
    
    if not token_b64:
        # Try reading from local file
        try:
            with open("token.json", "r") as f:
                token_data = json.load(f)
        except FileNotFoundError:
            raise Exception("No token.json file found and GOOGLE_TOKEN_B64 not set")
    else:
        token_data = json.loads(base64.b64decode(token_b64).decode())
    
    creds = Credentials.from_authorized_user_info(token_data)
    
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("Credentials are not valid and cannot be refreshed")
    
    return creds

def get_calendar_events_with_toyama_life_urls(service, days_back=90):
    """Get calendar events that have toyama-life.com URLs from the past N days."""
    now = datetime.utcnow()
    time_min = (now - timedelta(days=days_back)).isoformat() + 'Z'
    time_max = (now + timedelta(days=30)).isoformat() + 'Z'  # Include future events too
    
    print(f"Fetching calendar events from {days_back} days ago to 30 days in the future...")
    
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    toyama_life_events = []
    
    for event in events:
        description = event.get('description', '')
        if 'toyama-life.com/event-calendar-toyama/' in description:
            toyama_life_events.append(event)
    
    print(f"Found {len(toyama_life_events)} events with toyama-life.com URLs out of {len(events)} total events")
    return toyama_life_events

def create_url_mapping():
    """Create a mapping of event titles to their correct URLs by scraping current data."""
    print("Scraping current toyama-life.com data to build URL mapping...")
    
    url_mapping = {}
    current_events = list(fetch_toyamalife())
    
    for event in current_events:
        title = event['title']
        url = event['url']
        
        # Clean up title for matching
        clean_title = re.sub(r'[（(][^)）]*[)）]', '', title).strip()
        url_mapping[clean_title] = url
        url_mapping[title] = url  # Also store original title
        
        # Store variations
        title_variations = [
            title.replace('（', '(').replace('）', ')'),
            title.replace('(', '（').replace(')', '）'),
            re.sub(r'[（(][^)）]*[)）]', '', title).strip(),
            title.lower(),
            clean_title.lower()
        ]
        
        for variation in title_variations:
            if variation and variation not in url_mapping:
                url_mapping[variation] = url
    
    print(f"Built URL mapping with {len(current_events)} events and {len(url_mapping)} title variations")
    return url_mapping

def find_matching_url(event_title: str, url_mapping: Dict[str, str]) -> Optional[str]:
    """Find the best matching URL for an event title."""
    # Try exact match first
    if event_title in url_mapping:
        return url_mapping[event_title]
    
    # Try without parentheses
    clean_title = re.sub(r'[（(][^)）]*[)）]', '', event_title).strip()
    if clean_title in url_mapping:
        return url_mapping[clean_title]
    
    # Try case-insensitive
    title_lower = event_title.lower()
    if title_lower in url_mapping:
        return url_mapping[title_lower]
    
    # Try partial matches
    for mapped_title, mapped_url in url_mapping.items():
        if (mapped_title.lower() in title_lower or 
            title_lower in mapped_title.lower()):
            return mapped_url
    
    return None

def update_event_url(service, event, new_url: str, dry_run: bool = True):
    """Update an event's URL in its description."""
    event_id = event['id']
    summary = event.get('summary', '')
    description = event.get('description', '')
    
    # Replace the old URL with the new one
    old_pattern = r'https://toyama-life\.com/event-calendar-toyama/[^\s\n]*'
    new_description = re.sub(old_pattern, new_url, description)
    
    if dry_run:
        print(f"[DRY RUN] Would update event: {summary}")
        print(f"  Old description snippet: ...{description[-100:]}")
        print(f"  New URL: {new_url}")
        return True
    else:
        try:
            updated_event = {
                'description': new_description
            }
            
            service.events().patch(
                calendarId=CALENDAR_ID,
                eventId=event_id,
                body=updated_event
            ).execute()
            
            print(f"✅ Updated event: {summary}")
            print(f"  New URL: {new_url}")
            return True
        except Exception as e:
            print(f"❌ Failed to update event {summary}: {e}")
            return False

def main():
    """Main function to fix existing URLs."""
    import sys
    
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    days_back = 90
    
    if "--days" in sys.argv:
        days_idx = sys.argv.index("--days")
        if days_idx + 1 < len(sys.argv):
            days_back = int(sys.argv[days_idx + 1])
    
    print("🔧 Fixing existing toyama-life.com URLs in Google Calendar")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Looking back {days_back} days")
    print()
    
    # Get credentials and service
    try:
        creds = get_google_credentials()
        service = build('calendar', 'v3', credentials=creds)
        print("✅ Google Calendar API authenticated successfully")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return
    
    # Get events with toyama-life URLs
    events_to_fix = get_calendar_events_with_toyama_life_urls(service, days_back)
    
    if not events_to_fix:
        print("✅ No events found with toyama-life.com URLs that need fixing")
        return
    
    # Create URL mapping from current data
    url_mapping = create_url_mapping()
    
    # Process each event
    fixed_count = 0
    failed_count = 0
    no_match_count = 0
    
    print(f"\n🔍 Processing {len(events_to_fix)} events...")
    print()
    
    for event in events_to_fix:
        summary = event.get('summary', '')
        
        # Try to find matching URL
        new_url = find_matching_url(summary, url_mapping)
        
        if new_url and new_url != 'https://toyama-life.com/event-calendar-toyama/':
            if update_event_url(service, event, new_url, dry_run):
                fixed_count += 1
            else:
                failed_count += 1
        else:
            print(f"⚠️  No specific URL found for: {summary}")
            no_match_count += 1
        
        print()
    
    # Summary
    print("📊 Summary:")
    print(f"  Events processed: {len(events_to_fix)}")
    print(f"  Successfully fixed: {fixed_count}")
    print(f"  Failed to fix: {failed_count}")
    print(f"  No specific URL found: {no_match_count}")
    
    if dry_run:
        print("\n💡 This was a dry run. To actually update the events, run:")
        print("   python fix_existing_urls.py")
    else:
        print("\n✅ URL fixing complete!")

if __name__ == "__main__":
    main()