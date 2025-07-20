"""Enhanced Event Scraping and Processing System

This module integrates all advanced event processing capabilities:
- Original scraping functionality from scrape.py
- Enhanced event parsing with detailed metadata extraction
- Intelligent deduplication with machine learning features
- Comprehensive quality validation and auto-correction
- Smart scheduling and conflict detection
- Detailed reporting and analytics

Usage:
    python enhanced_scrape.py --full-pipeline    # Run complete processing
    python enhanced_scrape.py --debug           # Run with debug output
    python enhanced_scrape.py --report          # Generate detailed report
    python enhanced_scrape.py --validate-only   # Only validate existing data
"""

from __future__ import annotations

import json
import sys
import time
import argparse
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from pathlib import Path

# Import original scraping functionality
import scrape

# Import new enhanced modules
from enhanced_parser import (
    EnhancedEvent, EnhancedEventParser, EventTiming, EventLocation, 
    EventCategory, convert_legacy_to_enhanced
)
from intelligent_deduplicator import IntelligentDeduplicator, DeduplicationResult
from quality_validator import EventQualityValidator, ValidationResult
from smart_scheduler import SmartScheduler, ScheduleOptimization


class EnhancedEventProcessor:
    """Main processor that orchestrates all event processing steps."""
    
    def __init__(self, debug: bool = False, auto_fix: bool = True):
        """Initialize the enhanced processor."""
        self.debug = debug
        self.auto_fix = auto_fix
        
        # Initialize all processing components
        self.parser = EnhancedEventParser()
        self.deduplicator = IntelligentDeduplicator()
        self.validator = EventQualityValidator(auto_fix=auto_fix)
        self.scheduler = SmartScheduler()
        
        # Processing statistics
        self.stats = {
            'start_time': None,
            'end_time': None,
            'steps_completed': [],
            'events_processed': 0,
            'issues_found': 0,
            'auto_fixes_applied': 0,
            'duplicates_removed': 0
        }
    
    def run_full_pipeline(self) -> Dict[str, Any]:
        """Run the complete event processing pipeline."""
        self.stats['start_time'] = datetime.now()
        
        try:
            # Step 1: Scrape events using original functionality
            if self.debug:
                print("🔍 Step 1: Scraping events from websites...")
            
            legacy_events = self._scrape_legacy_events()
            self.stats['events_processed'] = len(legacy_events)
            self.stats['steps_completed'].append('scraping')
            
            if self.debug:
                print(f"   Found {len(legacy_events)} events from {self._count_sources(legacy_events)} sources")
            
            # Step 2: Convert to enhanced format
            if self.debug:
                print("🔄 Step 2: Converting to enhanced event format...")
            
            enhanced_events = self._convert_to_enhanced(legacy_events)
            self.stats['steps_completed'].append('conversion')
            
            if self.debug:
                print(f"   Converted {len(enhanced_events)} events to enhanced format")
            
            # Step 3: Quality validation and auto-correction
            if self.debug:
                print("✅ Step 3: Validating event quality...")
            
            validation_result = self._validate_events(enhanced_events)
            self.stats['issues_found'] = len(validation_result.issues)
            self.stats['auto_fixes_applied'] = validation_result.auto_fixes_applied
            self.stats['steps_completed'].append('validation')
            
            if self.debug:
                print(f"   Found {len(validation_result.issues)} issues, applied {validation_result.auto_fixes_applied} auto-fixes")
                print(f"   Overall quality score: {validation_result.metrics.overall_score:.1f}/100")
            
            # Step 4: Intelligent deduplication
            if self.debug:
                print("🔄 Step 4: Removing duplicates...")
            
            dedup_result = self._deduplicate_events(enhanced_events)
            self.stats['duplicates_removed'] = dedup_result.original_count - dedup_result.deduplicated_count
            self.stats['steps_completed'].append('deduplication')
            
            if self.debug:
                print(f"   Removed {self.stats['duplicates_removed']} duplicates ({len(dedup_result.merged_events)} events remaining)")
            
            # Step 5: Schedule optimization
            if self.debug:
                print("📅 Step 5: Optimizing schedule...")
            
            schedule_optimization = self._optimize_schedule(dedup_result.merged_events)
            self.stats['steps_completed'].append('scheduling')
            
            if self.debug:
                print(f"   Found {len(schedule_optimization.remaining_conflicts)} scheduling conflicts")
                print(f"   Schedule optimization score: {schedule_optimization.optimization_score:.2f}")
            
            # Step 6: Prepare final results
            if self.debug:
                print("📊 Step 6: Generating reports...")
            
            final_events = schedule_optimization.optimized_events
            reports = self._generate_comprehensive_report(
                legacy_events, enhanced_events, validation_result, 
                dedup_result, schedule_optimization
            )
            self.stats['steps_completed'].append('reporting')
            
            if self.debug:
                print(f"   Generated comprehensive analysis report")
            
            self.stats['end_time'] = datetime.now()
            
            return {
                'events': [event.to_legacy_format() for event in final_events],
                'enhanced_events': final_events,
                'reports': reports,
                'statistics': self.stats,
                'success': True
            }
            
        except Exception as e:
            self.stats['end_time'] = datetime.now()
            if self.debug:
                print(f"❌ Error in pipeline: {e}")
            
            return {
                'events': [],
                'enhanced_events': [],
                'reports': {},
                'statistics': self.stats,
                'success': False,
                'error': str(e)
            }
    
    def _scrape_legacy_events(self) -> List[Dict[str, Any]]:
        """Scrape events using the original scrape.py functionality."""
        try:
            # Use the original all_events generator
            events = list(scrape.all_events())
            return events
        except Exception as e:
            if self.debug:
                print(f"   Warning: Scraping error: {e}")
            return []
    
    def _count_sources(self, events: List[Dict[str, Any]]) -> int:
        """Count unique sources in event list."""
        sources = set()
        for event in events:
            if 'site' in event:
                sources.add(event['site'])
        return len(sources)
    
    def _convert_to_enhanced(self, legacy_events: List[Dict[str, Any]]) -> List[EnhancedEvent]:
        """Convert legacy events to enhanced format with detailed parsing."""
        enhanced_events = []
        
        for legacy_event in legacy_events:
            try:
                # Extract basic information
                title = legacy_event.get('title', '')
                url = legacy_event.get('url', '')
                site = legacy_event.get('site', '')
                location_text = legacy_event.get('location', '')
                
                # Create date text for parsing
                start_date = legacy_event.get('start')
                end_date = legacy_event.get('end')
                date_text = str(start_date)
                if end_date and end_date != start_date:
                    date_text += f" ～ {end_date}"
                
                # Use enhanced parser for detailed analysis
                enhanced_event = self.parser.parse_enhanced_event(
                    title=title,
                    description="",  # Legacy events don't have descriptions
                    date_text=date_text,
                    location_text=location_text,
                    source_url=url,
                    source_site=site
                )
                
                # Override timing with legacy data (more reliable)
                if start_date:
                    enhanced_event.timing.start_date = start_date
                if end_date:
                    enhanced_event.timing.end_date = end_date
                
                enhanced_events.append(enhanced_event)
                
            except Exception as e:
                if self.debug:
                    print(f"   Warning: Failed to enhance event '{title}': {e}")
                continue
        
        return enhanced_events
    
    def _validate_events(self, events: List[EnhancedEvent]) -> ValidationResult:
        """Validate event quality and apply auto-fixes."""
        return self.validator.validate_events(events)
    
    def _deduplicate_events(self, events: List[EnhancedEvent]) -> DeduplicationResult:
        """Remove duplicate events using intelligent matching."""
        return self.deduplicator.deduplicate_events(events, auto_merge=True)
    
    def _optimize_schedule(self, events: List[EnhancedEvent]) -> ScheduleOptimization:
        """Optimize event scheduling and detect conflicts."""
        return self.scheduler.optimize_schedule(events)
    
    def _generate_comprehensive_report(self, 
                                     legacy_events: List[Dict[str, Any]],
                                     enhanced_events: List[EnhancedEvent],
                                     validation_result: ValidationResult,
                                     dedup_result: DeduplicationResult,
                                     schedule_optimization: ScheduleOptimization) -> Dict[str, Any]:
        """Generate comprehensive analysis report."""
        
        # Processing summary
        if self.stats['end_time'] and self.stats['start_time']:
            processing_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        else:
            processing_time = 0.0
        
        summary = {
            'processing_summary': {
                'total_processing_time': processing_time,
                'steps_completed': self.stats['steps_completed'],
                'original_events': len(legacy_events),
                'final_events': len(schedule_optimization.optimized_events),
                'events_removed': len(legacy_events) - len(schedule_optimization.optimized_events),
                'auto_fixes_applied': self.stats['auto_fixes_applied'],
                'duplicates_removed': self.stats['duplicates_removed']
            }
        }
        
        # Quality analysis
        quality_report = self.validator.generate_quality_report(validation_result)
        
        # Deduplication analysis
        dedup_report = self.deduplicator.generate_deduplication_report(dedup_result)
        
        # Schedule analysis
        schedule_report = self.scheduler.generate_schedule_report(schedule_optimization.optimized_events)
        
        # Event distribution analysis
        category_dist = {}
        quality_dist = {}
        source_dist = {}
        date_dist = {}
        
        for event in schedule_optimization.optimized_events:
            # Category distribution
            cat = event.category.value
            category_dist[cat] = category_dist.get(cat, 0) + 1
            
            # Quality distribution
            qual = event.quality_level.value
            quality_dist[qual] = quality_dist.get(qual, 0) + 1
            
            # Source distribution
            source = event.source_site
            source_dist[source] = source_dist.get(source, 0) + 1
            
            # Date distribution (by month)
            if event.timing and event.timing.start_date:
                month_key = event.timing.start_date.strftime('%Y-%m')
                date_dist[month_key] = date_dist.get(month_key, 0) + 1
        
        distribution = {
            'by_category': category_dist,
            'by_quality': quality_dist,
            'by_source': source_dist,
            'by_month': date_dist
        }
        
        # Top events (highest quality)
        top_events = sorted(
            schedule_optimization.optimized_events,
            key=lambda e: e.quality_score,
            reverse=True
        )[:10]
        
        top_events_info = [
            {
                'title': event.title,
                'date': event.timing.start_date.isoformat() if event.timing else None,
                'location': event.location.name if event.location else '',
                'category': event.category.value,
                'quality_score': event.quality_score,
                'source': event.source_site
            }
            for event in top_events
        ]
        
        # Recommendations
        recommendations = []
        
        if validation_result.metrics.overall_score < 70:
            recommendations.append("データ品質が低いです。より多くの詳細情報の収集を検討してください。")
        
        if len(dedup_result.matches_found) > len(legacy_events) * 0.1:
            recommendations.append("重複が多く検出されました。データソースの重複チェックを強化してください。")
        
        if len(schedule_optimization.remaining_conflicts) > 0:
            recommendations.append("スケジュール競合があります。イベントの時間調整を検討してください。")
        
        if source_dist:
            source_counts = list(source_dist.values())
            if max(source_counts) > sum(source_counts) * 0.7:
                recommendations.append("特定のソースに依存度が高いです。情報源の多様化を検討してください。")
        
        return {
            **summary,
            'quality_analysis': quality_report,
            'deduplication_analysis': dedup_report,
            'schedule_analysis': schedule_report,
            'distribution_analysis': distribution,
            'top_events': top_events_info,
            'recommendations': recommendations
        }


def main():
    """Main entry point for the enhanced scraping system."""
    parser = argparse.ArgumentParser(description='Enhanced Event Scraping and Processing System')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--full-pipeline', action='store_true', help='Run complete processing pipeline')
    parser.add_argument('--report', action='store_true', help='Generate detailed report')
    parser.add_argument('--validate-only', action='store_true', help='Only validate existing data')
    parser.add_argument('--auto-fix', action='store_true', default=True, help='Apply automatic fixes')
    parser.add_argument('--output', type=str, help='Output file for results')
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = EnhancedEventProcessor(debug=args.debug, auto_fix=args.auto_fix)
    
    if args.validate_only:
        # Only run validation on existing data
        print("🔍 Running validation on existing events...")
        try:
            legacy_events = list(scrape.all_events())
            enhanced_events = processor._convert_to_enhanced(legacy_events)
            validation_result = processor._validate_events(enhanced_events)
            
            quality_report = processor.validator.generate_quality_report(validation_result)
            print(json.dumps(quality_report, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"❌ Validation failed: {e}")
        return
    
    # Run full pipeline
    if args.full_pipeline or not any([args.report, args.validate_only]):
        print("🚀 Starting Enhanced Event Processing Pipeline")
        print("=" * 60)
        
        result = processor.run_full_pipeline()
        
        if result['success']:
            print("\n✅ Pipeline completed successfully!")
            print(f"📊 Final Statistics:")
            print(f"   • Events processed: {result['statistics']['events_processed']}")
            print(f"   • Final events: {len(result['events'])}")
            print(f"   • Duplicates removed: {result['statistics']['duplicates_removed']}")
            print(f"   • Issues found: {result['statistics']['issues_found']}")
            print(f"   • Auto-fixes applied: {result['statistics']['auto_fixes_applied']}")
            
            processing_time = (result['statistics']['end_time'] - result['statistics']['start_time']).total_seconds()
            print(f"   • Processing time: {processing_time:.1f} seconds")
            
            if args.report:
                print(f"\n📋 Detailed Report:")
                print(json.dumps(result['reports'], indent=2, ensure_ascii=False, default=str))
            
            # Output results
            if args.output:
                output_data = {
                    'events': result['events'],
                    'reports': result['reports'] if args.report else None,
                    'generated_at': datetime.now().isoformat()
                }
                
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
                print(f"📁 Results saved to: {args.output}")
            
            # For compatibility with existing gcal_sync.py, also output events in original format
            if not args.output:
                # Output events in the same format as original scrape.py
                for event in result['events']:
                    # Convert back to the format expected by gcal_sync.py
                    pass
                
                print(f"\n📋 Events ready for Google Calendar sync:")
                json.dump(result['events'], sys.stdout, ensure_ascii=False, indent=2, default=str)
        
        else:
            print(f"\n❌ Pipeline failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()