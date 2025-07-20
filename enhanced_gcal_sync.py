"""Enhanced Google Calendar Synchronization System

This module extends the original gcal_sync.py with advanced features:
- Quality-based sync prioritization
- Enhanced event metadata synchronization
- Schedule conflict detection and reporting
- Batch operations with error recovery
- Detailed sync analytics and reporting
- Support for enhanced event format

Usage:
    python enhanced_gcal_sync.py --enhanced     # Use enhanced processing
    python enhanced_gcal_sync.py --report       # Generate sync report
    python enhanced_gcal_sync.py --dry-run      # Preview changes without syncing
"""

from __future__ import annotations

import os
import base64
import hashlib
import json
import sqlite3
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Import both legacy and enhanced modules
import scrape
import gcal_sync
from enhanced_scrape import EnhancedEventProcessor
from enhanced_parser import EnhancedEvent
from quality_validator import EventQualityValidator
from smart_scheduler import SmartScheduler

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CAL_ID = "primary"  # Change if you want to use a secondary calendar
DB_PATH = Path(__file__).with_name("events.db")


class EnhancedCalendarSync:
    """Enhanced Google Calendar synchronization with advanced features."""
    
    def __init__(self, dry_run: bool = False, debug: bool = False):
        """Initialize enhanced sync system."""
        self.dry_run = dry_run
        self.debug = debug
        self.service = None
        self.conn = None
        
        # Processing components
        self.processor = EnhancedEventProcessor(debug=debug)
        self.validator = EventQualityValidator()
        self.scheduler = SmartScheduler()
        
        # Sync statistics
        self.stats = {
            'start_time': None,
            'end_time': None,
            'events_processed': 0,
            'events_inserted': 0,
            'events_updated': 0,
            'events_skipped': 0,
            'errors': [],
            'quality_filtered': 0,
            'conflicts_detected': 0
        }
    
    def initialize_services(self):
        """Initialize Google Calendar service and database connection."""
        if self.debug:
            print("🔐 Initializing authentication and database...")
        
        self.service = self._authenticate()
        self.conn = sqlite3.connect(DB_PATH)
        self._ensure_enhanced_db()
    
    def _authenticate(self):
        """Authenticate with Google Calendar API (same as original)."""
        # Use the same authentication logic as gcal_sync.py
        return gcal_sync._auth()
    
    def _ensure_enhanced_db(self):
        """Ensure database has enhanced tables for metadata tracking."""
        # Create original events table
        gcal_sync._ensure_db(self.conn)
        
        # Add enhanced metadata table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS event_metadata (
                key TEXT PRIMARY KEY,
                quality_score REAL,
                confidence_score REAL,
                category TEXT,
                source_site TEXT,
                last_updated TIMESTAMP,
                sync_priority INTEGER DEFAULT 0,
                conflict_flags TEXT,
                FOREIGN KEY (key) REFERENCES events (key)
            )
        """)
        
        # Add sync analytics table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_date TIMESTAMP,
                events_processed INTEGER,
                events_inserted INTEGER,
                events_updated INTEGER,
                events_skipped INTEGER,
                quality_filtered INTEGER,
                conflicts_detected INTEGER,
                processing_time REAL,
                report_data TEXT
            )
        """)
        
        self.conn.commit()
    
    def sync_enhanced_events(self, min_quality_score: float = 60.0) -> Dict[str, Any]:
        """Sync events using enhanced processing pipeline."""
        self.stats['start_time'] = datetime.now()
        
        try:
            # Step 1: Get processed events from enhanced pipeline
            if self.debug:
                print("🔄 Step 1: Processing events with enhanced pipeline...")
            
            pipeline_result = self.processor.run_full_pipeline()
            
            if not pipeline_result['success']:
                raise Exception(f"Enhanced processing failed: {pipeline_result.get('error')}")
            
            enhanced_events = pipeline_result['enhanced_events']
            self.stats['events_processed'] = len(enhanced_events)
            
            if self.debug:
                print(f"   Processed {len(enhanced_events)} events")
            
            # Step 2: Filter by quality score
            if self.debug:
                print(f"🎯 Step 2: Filtering events by quality score (>= {min_quality_score})...")
            
            quality_events = [
                event for event in enhanced_events 
                if event.quality_score >= min_quality_score
            ]
            
            self.stats['quality_filtered'] = len(enhanced_events) - len(quality_events)
            
            if self.debug:
                print(f"   Kept {len(quality_events)} events, filtered {self.stats['quality_filtered']} low-quality events")
            
            # Step 3: Detect and handle conflicts
            if self.debug:
                print("⚠️  Step 3: Detecting schedule conflicts...")
            
            conflicts = self.scheduler.detect_conflicts(quality_events)
            self.stats['conflicts_detected'] = len(conflicts)
            
            if self.debug and conflicts:
                print(f"   Found {len(conflicts)} schedule conflicts")
                for conflict in conflicts[:3]:  # Show first 3
                    print(f"     • {conflict.conflict_type.value}: {conflict.description}")
            
            # Step 4: Sync to Google Calendar
            if self.debug:
                print("📅 Step 4: Synchronizing to Google Calendar...")
            
            sync_results = self._sync_events_to_calendar(quality_events, conflicts)
            
            # Step 5: Update metadata and analytics
            if self.debug:
                print("📊 Step 5: Updating metadata and analytics...")
            
            self._update_event_metadata(quality_events, conflicts)
            self._save_sync_analytics(pipeline_result['reports'])
            
            self.stats['end_time'] = datetime.now()
            
            return {
                'success': True,
                'statistics': self.stats,
                'conflicts': conflicts,
                'pipeline_reports': pipeline_result['reports'],
                'sync_results': sync_results
            }
            
        except Exception as e:
            self.stats['end_time'] = datetime.now()
            self.stats['errors'].append(str(e))
            
            if self.debug:
                print(f"❌ Enhanced sync failed: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'statistics': self.stats
            }
    
    def _sync_events_to_calendar(self, events: List[EnhancedEvent], 
                               conflicts: List) -> Dict[str, Any]:
        """Sync enhanced events to Google Calendar."""
        sync_results = {
            'inserted': [],
            'updated': [],
            'skipped': [],
            'errors': []
        }
        
        # Sort events by priority (quality score + conflict penalties)
        prioritized_events = self._prioritize_events(events, conflicts)
        
        for event in prioritized_events:
            try:
                result = self._sync_single_event(event, conflicts)
                
                if result['action'] == 'inserted':
                    sync_results['inserted'].append(result)
                    self.stats['events_inserted'] += 1
                elif result['action'] == 'updated':
                    sync_results['updated'].append(result)
                    self.stats['events_updated'] += 1
                elif result['action'] == 'skipped':
                    sync_results['skipped'].append(result)
                    self.stats['events_skipped'] += 1
                    
            except Exception as e:
                error_info = {
                    'event_title': event.title,
                    'error': str(e)
                }
                sync_results['errors'].append(error_info)
                self.stats['errors'].append(f"Event '{event.title}': {e}")
                
                if self.debug:
                    print(f"   ⚠️  Error syncing '{event.title}': {e}")
        
        return sync_results
    
    def _prioritize_events(self, events: List[EnhancedEvent], conflicts: List) -> List[EnhancedEvent]:
        """Prioritize events for syncing based on quality and conflicts."""
        def calculate_priority(event: EnhancedEvent) -> float:
            priority = event.quality_score
            
            # Boost priority for festivals and major events
            if event.category.value == 'festival':
                priority += 10
            
            # Penalty for events involved in conflicts
            event_conflicts = [c for c in conflicts if c.event1 == event or c.event2 == event]
            priority -= len(event_conflicts) * 5
            
            # Boost for events with complete information
            if event.location and event.location.address:
                priority += 5
            if event.contact and (event.contact.phone or event.contact.email):
                priority += 5
            
            return priority
        
        return sorted(events, key=calculate_priority, reverse=True)
    
    def _sync_single_event(self, event: EnhancedEvent, conflicts: List) -> Dict[str, Any]:
        """Sync a single enhanced event to Google Calendar."""
        # Generate event key (same logic as original)
        key = self._event_key(event)
        
        # Check if event already exists
        cur = self.conn.cursor()
        cur.execute("SELECT gcal_id FROM events WHERE key=?", (key,))
        row = cur.fetchone()
        
        # Create enhanced event body
        body = self._create_enhanced_event_body(event, conflicts)
        
        if body is None:
            return {
                'action': 'skipped',
                'event_title': event.title,
                'reason': 'Invalid event data'
            }
        
        if self.dry_run:
            action = 'would_update' if row else 'would_insert'
            return {
                'action': action,
                'event_title': event.title,
                'event_data': body
            }
        
        if row:
            # Update existing event
            gcal_event = self.service.events().update(
                calendarId=CAL_ID, 
                eventId=row[0], 
                body=body
            ).execute()
            
            return {
                'action': 'updated',
                'event_title': event.title,
                'gcal_id': gcal_event['id'],
                'quality_score': event.quality_score
            }
        else:
            # Insert new event
            gcal_event = self.service.events().insert(
                calendarId=CAL_ID, 
                body=body
            ).execute()
            
            # Store in database
            cur.execute(
                "INSERT OR REPLACE INTO events(key, gcal_id) VALUES(?,?)", 
                (key, gcal_event["id"])
            )
            self.conn.commit()
            
            return {
                'action': 'inserted',
                'event_title': event.title,
                'gcal_id': gcal_event['id'],
                'quality_score': event.quality_score
            }
    
    def _event_key(self, event: EnhancedEvent) -> str:
        """Generate event key (same as original logic)."""
        raw = f"{event.title}{event.timing.start_date if event.timing else ''}"
        return hashlib.sha256(raw.encode()).hexdigest()
    
    def _create_enhanced_event_body(self, event: EnhancedEvent, conflicts: List) -> Optional[Dict[str, Any]]:
        """Create enhanced Google Calendar event body."""
        if not event.timing:
            return None
        
        # Basic timing setup (same logic as original gcal_sync.py)
        start_date = event.timing.start_date
        end_date = event.timing.end_date or start_date
        
        # For all-day events, end date should be next day
        if event.timing.is_all_day:
            if end_date == start_date:
                end_date = start_date + timedelta(days=1)
            else:
                end_date = end_date + timedelta(days=1)
            
            body = {
                "summary": event.title,
                "start": {"date": start_date.isoformat()},
                "end": {"date": end_date.isoformat()},
            }
        else:
            # Timed events
            start_datetime = datetime.combine(start_date, event.timing.start_time or datetime.min.time())
            end_datetime = datetime.combine(end_date, event.timing.end_time or datetime.max.time())
            
            body = {
                "summary": event.title,
                "start": {"dateTime": start_datetime.isoformat(), "timeZone": "Asia/Tokyo"},
                "end": {"dateTime": end_datetime.isoformat(), "timeZone": "Asia/Tokyo"},
            }
        
        # Enhanced metadata in description
        description_parts = []
        
        if event.description:
            description_parts.append(event.description)
        
        # Add quality and source information
        description_parts.append(f"\n📊 品質スコア: {event.quality_score:.1f}/100")
        description_parts.append(f"🏷️ カテゴリー: {event.category.value}")
        
        if event.source_site:
            description_parts.append(f"📰 情報源: {event.source_site}")
        
        # Add conflict warnings
        event_conflicts = [c for c in conflicts if c.event1 == event or c.event2 == event]
        if event_conflicts:
            description_parts.append("\n⚠️ スケジュール注意:")
            for conflict in event_conflicts[:3]:  # Show up to 3 conflicts
                description_parts.append(f"  • {conflict.description}")
        
        # Add contact information
        if event.contact:
            contact_info = []
            if event.contact.phone:
                contact_info.append(f"📞 {event.contact.phone}")
            if event.contact.email:
                contact_info.append(f"📧 {event.contact.email}")
            if event.contact.organizer:
                contact_info.append(f"👥 主催: {event.contact.organizer}")
            
            if contact_info:
                description_parts.append("\n📞 連絡先:")
                description_parts.extend(f"  {info}" for info in contact_info)
        
        # Add pricing information
        if event.pricing and not event.pricing.is_free:
            description_parts.append("\n💰 料金:")
            if event.pricing.adult_price:
                description_parts.append(f"  大人: {event.pricing.adult_price:,}円")
            if event.pricing.child_price:
                description_parts.append(f"  子供: {event.pricing.child_price:,}円")
        elif event.pricing and event.pricing.is_free:
            description_parts.append("\n💰 参加費: 無料")
        
        body["description"] = "\n".join(description_parts)
        
        # Enhanced location
        if event.location:
            location_text = event.location.name
            if event.location.address:
                location_text += f", {event.location.address}"
            body["location"] = location_text
        
        # Source information
        body["source"] = {
            "title": event.source_site or "Event Source",
            "url": event.source_url or "",
        }
        
        # Custom extended properties for metadata
        body["extendedProperties"] = {
            "private": {
                "quality_score": str(event.quality_score),
                "category": event.category.value,
                "source_site": event.source_site or "",
                "event_hash": event.hash_id,
                "has_conflicts": "yes" if event_conflicts else "no"
            }
        }
        
        return body
    
    def _update_event_metadata(self, events: List[EnhancedEvent], conflicts: List):
        """Update enhanced metadata in database."""
        cur = self.conn.cursor()
        
        for event in events:
            key = self._event_key(event)
            event_conflicts = [c for c in conflicts if c.event1 == event or c.event2 == event]
            conflict_flags = json.dumps([c.conflict_type.value for c in event_conflicts])
            
            # Determine sync priority
            priority = self.scheduler.determine_event_priority(event).value
            
            cur.execute("""
                INSERT OR REPLACE INTO event_metadata 
                (key, quality_score, confidence_score, category, source_site, 
                 last_updated, sync_priority, conflict_flags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key,
                event.quality_score,
                event.confidence_score,
                event.category.value,
                event.source_site,
                datetime.now(),
                priority,
                conflict_flags
            ))
        
        self.conn.commit()
    
    def _save_sync_analytics(self, reports: Dict[str, Any]):
        """Save sync analytics to database."""
        processing_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO sync_analytics 
            (sync_date, events_processed, events_inserted, events_updated, 
             events_skipped, quality_filtered, conflicts_detected, 
             processing_time, report_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.stats['start_time'],
            self.stats['events_processed'],
            self.stats['events_inserted'],
            self.stats['events_updated'],
            self.stats['events_skipped'],
            self.stats['quality_filtered'],
            self.stats['conflicts_detected'],
            processing_time,
            json.dumps(reports, default=str)
        ))
        
        self.conn.commit()
    
    def generate_sync_report(self) -> Dict[str, Any]:
        """Generate comprehensive sync report."""
        processing_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        # Get historical sync data
        cur = self.conn.cursor()
        cur.execute("""
            SELECT sync_date, events_processed, events_inserted, events_updated,
                   quality_filtered, conflicts_detected, processing_time
            FROM sync_analytics 
            ORDER BY sync_date DESC 
            LIMIT 10
        """)
        
        history = [
            {
                'date': row[0],
                'events_processed': row[1],
                'events_inserted': row[2],
                'events_updated': row[3],
                'quality_filtered': row[4],
                'conflicts_detected': row[5],
                'processing_time': row[6]
            }
            for row in cur.fetchall()
        ]
        
        # Get current quality distribution
        cur.execute("""
            SELECT category, AVG(quality_score), COUNT(*)
            FROM event_metadata 
            GROUP BY category 
            ORDER BY AVG(quality_score) DESC
        """)
        
        quality_by_category = [
            {
                'category': row[0],
                'avg_quality': row[1],
                'count': row[2]
            }
            for row in cur.fetchall()
        ]
        
        return {
            'current_sync': {
                'timestamp': self.stats['start_time'].isoformat(),
                'events_processed': self.stats['events_processed'],
                'events_inserted': self.stats['events_inserted'],
                'events_updated': self.stats['events_updated'],
                'events_skipped': self.stats['events_skipped'],
                'quality_filtered': self.stats['quality_filtered'],
                'conflicts_detected': self.stats['conflicts_detected'],
                'processing_time': processing_time,
                'success_rate': (self.stats['events_inserted'] + self.stats['events_updated']) / max(self.stats['events_processed'], 1)
            },
            'historical_data': history,
            'quality_analysis': quality_by_category,
            'errors': self.stats['errors']
        }
    
    def cleanup(self):
        """Clean up resources."""
        if self.conn:
            self.conn.close()


def main():
    """Main entry point for enhanced calendar sync."""
    parser = argparse.ArgumentParser(description='Enhanced Google Calendar Sync')
    parser.add_argument('--enhanced', action='store_true', help='Use enhanced processing pipeline')
    parser.add_argument('--legacy', action='store_true', help='Use legacy sync (same as original gcal_sync.py)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without syncing')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--report', action='store_true', help='Generate sync report')
    parser.add_argument('--min-quality', type=float, default=60.0, help='Minimum quality score for sync')
    
    args = parser.parse_args()
    
    if args.legacy:
        # Run original gcal_sync.py logic
        print("🔄 Running legacy Google Calendar sync...")
        gcal_sync.main()
        return
    
    # Initialize enhanced sync system
    sync_system = EnhancedCalendarSync(dry_run=args.dry_run, debug=args.debug)
    
    try:
        sync_system.initialize_services()
        
        if args.enhanced or not args.report:
            # Run enhanced sync
            print("🚀 Starting Enhanced Google Calendar Sync")
            print("=" * 60)
            
            result = sync_system.sync_enhanced_events(min_quality_score=args.min_quality)
            
            if result['success']:
                stats = result['statistics']
                print(f"\n✅ Sync completed successfully!")
                print(f"📊 Sync Statistics:")
                print(f"   • Events processed: {stats['events_processed']}")
                print(f"   • Events inserted: {stats['events_inserted']}")
                print(f"   • Events updated: {stats['events_updated']}")
                print(f"   • Events skipped: {stats['events_skipped']}")
                print(f"   • Quality filtered: {stats['quality_filtered']}")
                print(f"   • Conflicts detected: {stats['conflicts_detected']}")
                
                processing_time = (stats['end_time'] - stats['start_time']).total_seconds()
                print(f"   • Processing time: {processing_time:.1f} seconds")
                
                if args.dry_run:
                    print(f"\n🔍 Dry run completed - no changes made to calendar")
                
            else:
                print(f"\n❌ Sync failed: {result['error']}")
                sys.exit(1)
        
        if args.report:
            # Generate and display report
            print(f"\n📋 Generating sync report...")
            report = sync_system.generate_sync_report()
            print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    
    finally:
        sync_system.cleanup()


if __name__ == "__main__":
    main()