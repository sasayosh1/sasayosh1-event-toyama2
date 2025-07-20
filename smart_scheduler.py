"""Smart Event Scheduling and Conflict Detection System

This module provides intelligent scheduling capabilities including:
- Time conflict detection and resolution
- Venue capacity management
- Priority-based scheduling
- Smart event grouping and categorization
- Calendar optimization
- Travel time estimation between venues
"""

from __future__ import annotations

import re
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import math

from enhanced_parser import EnhancedEvent, EventTiming, EventLocation, EventCategory


class ConflictType(Enum):
    """Types of scheduling conflicts."""
    TIME_OVERLAP = "time_overlap"
    VENUE_CAPACITY = "venue_capacity"
    RESOURCE_CONFLICT = "resource_conflict"
    TRAVEL_TIME = "travel_time"
    CATEGORY_CLASH = "category_clash"


class Priority(Enum):
    """Event priority levels."""
    CRITICAL = 5    # Major festivals, official events
    HIGH = 4        # Popular events, limited capacity
    MEDIUM = 3      # Regular events
    LOW = 2         # Minor events, recurring
    FLEXIBLE = 1    # Events that can be moved easily


@dataclass
class ScheduleConflict:
    """Represents a scheduling conflict between events."""
    event1: EnhancedEvent
    event2: EnhancedEvent
    conflict_type: ConflictType
    severity: float  # 0.0 - 1.0
    description: str
    suggestions: List[str] = field(default_factory=list)
    auto_resolvable: bool = False


@dataclass
class VenueInfo:
    """Information about event venues."""
    name: str
    capacity: Optional[int] = None
    venue_type: str = ""
    address: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    operating_hours: Dict[str, Tuple[time, time]] = field(default_factory=dict)
    amenities: List[str] = field(default_factory=list)
    booking_restrictions: List[str] = field(default_factory=list)


@dataclass
class ScheduleOptimization:
    """Results of schedule optimization."""
    optimized_events: List[EnhancedEvent]
    conflicts_resolved: List[ScheduleConflict]
    remaining_conflicts: List[ScheduleConflict]
    optimization_score: float
    recommendations: List[str]


class SmartScheduler:
    """Smart event scheduling and conflict management system."""
    
    def __init__(self):
        """Initialize the smart scheduler."""
        self.venues: Dict[str, VenueInfo] = self._init_default_venues()
        self.priority_weights = self._init_priority_weights()
        self.category_weights = self._init_category_weights()
        self.max_travel_time_minutes = 30  # Maximum reasonable travel time
        
    def _init_default_venues(self) -> Dict[str, VenueInfo]:
        """Initialize default venue information for Toyama."""
        venues = {}
        
        # Major venues in Toyama
        toyama_venues = [
            VenueInfo(
                name="富山市民会館",
                capacity=2000,
                venue_type="ホール",
                address="富山市新総曲輪4-18",
                operating_hours={
                    "weekday": (time(9, 0), time(22, 0)),
                    "weekend": (time(9, 0), time(22, 0))
                },
                amenities=["駐車場", "バリアフリー", "音響設備"]
            ),
            VenueInfo(
                name="高岡市民会館",
                capacity=1500,
                venue_type="ホール",
                address="高岡市中川1-1-25",
                operating_hours={
                    "weekday": (time(9, 0), time(22, 0)),
                    "weekend": (time(9, 0), time(22, 0))
                },
                amenities=["駐車場", "音響設備"]
            ),
            VenueInfo(
                name="富山城址公園",
                capacity=10000,
                venue_type="公園",
                address="富山市本丸1",
                operating_hours={
                    "all": (time(6, 0), time(21, 0))
                },
                amenities=["屋外", "大型イベント対応"]
            ),
            VenueInfo(
                name="環水公園",
                capacity=5000,
                venue_type="公園",
                address="富山市湊入船町",
                operating_hours={
                    "all": (time(0, 0), time(23, 59))
                },
                amenities=["屋外", "水辺", "夜間利用可"]
            )
        ]
        
        for venue in toyama_venues:
            venues[venue.name] = venue
            
        return venues
    
    def _init_priority_weights(self) -> Dict[Priority, float]:
        """Initialize priority weights for scheduling."""
        return {
            Priority.CRITICAL: 1.0,
            Priority.HIGH: 0.8,
            Priority.MEDIUM: 0.6,
            Priority.LOW: 0.4,
            Priority.FLEXIBLE: 0.2
        }
    
    def _init_category_weights(self) -> Dict[EventCategory, float]:
        """Initialize category weights for scheduling."""
        return {
            EventCategory.FESTIVAL: 1.0,
            EventCategory.CULTURE: 0.9,
            EventCategory.SPORTS: 0.8,
            EventCategory.ENTERTAINMENT: 0.7,
            EventCategory.EDUCATION: 0.6,
            EventCategory.BUSINESS: 0.5,
            EventCategory.MARKET: 0.7,
            EventCategory.FOOD: 0.6,
            EventCategory.NATURE: 0.8,
            EventCategory.OTHER: 0.3
        }
    
    def determine_event_priority(self, event: EnhancedEvent) -> Priority:
        """Determine priority level for an event."""
        title_lower = event.title.lower()
        
        # Critical events
        critical_patterns = [
            r'第\d+回.*まつり', r'花火大会', r'おわら風の盆', 
            r'官公庁', r'市制.*周年', r'県.*主催'
        ]
        
        for pattern in critical_patterns:
            if re.search(pattern, event.title):
                return Priority.CRITICAL
        
        # High priority events
        high_patterns = [
            r'まつり', r'フェスティバル', r'コンサート',
            r'展示会', r'限定', r'特別'
        ]
        
        for pattern in high_patterns:
            if re.search(pattern, title_lower):
                return Priority.HIGH
        
        # Check by category
        if event.category == EventCategory.FESTIVAL:
            return Priority.HIGH
        elif event.category in [EventCategory.CULTURE, EventCategory.SPORTS]:
            return Priority.MEDIUM
        elif event.category in [EventCategory.MARKET, EventCategory.FOOD]:
            return Priority.LOW
        
        # Default based on quality score
        if event.quality_score >= 80:
            return Priority.MEDIUM
        elif event.quality_score >= 60:
            return Priority.LOW
        else:
            return Priority.FLEXIBLE
    
    def detect_conflicts(self, events: List[EnhancedEvent]) -> List[ScheduleConflict]:
        """Detect all types of conflicts between events."""
        conflicts = []
        
        for i, event1 in enumerate(events):
            for event2 in events[i+1:]:
                # Time overlap conflicts
                time_conflict = self._check_time_overlap(event1, event2)
                if time_conflict:
                    conflicts.append(time_conflict)
                
                # Venue capacity conflicts
                venue_conflict = self._check_venue_capacity(event1, event2)
                if venue_conflict:
                    conflicts.append(venue_conflict)
                
                # Travel time conflicts
                travel_conflict = self._check_travel_time(event1, event2)
                if travel_conflict:
                    conflicts.append(travel_conflict)
                
                # Category clash conflicts
                category_conflict = self._check_category_clash(event1, event2)
                if category_conflict:
                    conflicts.append(category_conflict)
        
        return conflicts
    
    def _check_time_overlap(self, event1: EnhancedEvent, event2: EnhancedEvent) -> Optional[ScheduleConflict]:
        """Check for time overlap between two events."""
        if not event1.timing or not event2.timing:
            return None
        
        t1 = event1.timing
        t2 = event2.timing
        
        # Check date overlap
        start1 = t1.start_date
        end1 = t1.end_date or t1.start_date
        start2 = t2.start_date
        end2 = t2.end_date or t2.start_date
        
        # No date overlap
        if end1 < start2 or end2 < start1:
            return None
        
        # If they're on the same day and both have specific times
        if (start1 == start2 and 
            t1.start_time and t1.end_time and 
            t2.start_time and t2.end_time):
            
            # Check time overlap
            if (t1.end_time <= t2.start_time or t2.end_time <= t1.start_time):
                return None  # No time overlap
            
            # Calculate overlap severity
            overlap_start = max(t1.start_time, t2.start_time)
            overlap_end = min(t1.end_time, t2.end_time)
            
            if overlap_start < overlap_end:
                overlap_minutes = (
                    datetime.combine(date.today(), overlap_end) - 
                    datetime.combine(date.today(), overlap_start)
                ).total_seconds() / 60
                
                total_duration = max(
                    (datetime.combine(date.today(), t1.end_time) - 
                     datetime.combine(date.today(), t1.start_time)).total_seconds() / 60,
                    (datetime.combine(date.today(), t2.end_time) - 
                     datetime.combine(date.today(), t2.start_time)).total_seconds() / 60
                )
                
                severity = min(overlap_minutes / total_duration, 1.0)
                
                return ScheduleConflict(
                    event1=event1,
                    event2=event2,
                    conflict_type=ConflictType.TIME_OVERLAP,
                    severity=severity,
                    description=f"イベントが{overlap_minutes:.0f}分間重複しています",
                    suggestions=[
                        "イベント時間を調整する",
                        "どちらか一方の日程を変更する",
                        "イベントを短縮する"
                    ],
                    auto_resolvable=(severity < 0.3)
                )
        
        # All-day events on same day
        elif start1 == start2:
            return ScheduleConflict(
                event1=event1,
                event2=event2,
                conflict_type=ConflictType.TIME_OVERLAP,
                severity=0.8,
                description="同日に終日イベントが重複しています",
                suggestions=[
                    "日程を分散する",
                    "時間を指定して分割開催する",
                    "会場を分ける"
                ],
                auto_resolvable=False
            )
        
        return None
    
    def _check_venue_capacity(self, event1: EnhancedEvent, event2: EnhancedEvent) -> Optional[ScheduleConflict]:
        """Check for venue capacity conflicts."""
        if not event1.location or not event2.location:
            return None
        
        # If same venue and overlapping time
        if (event1.location.name == event2.location.name and 
            self._events_time_overlap(event1, event2)):
            
            venue_info = self.venues.get(event1.location.name)
            if venue_info and venue_info.capacity:
                # Estimate attendance (this could be improved with historical data)
                estimated_attendance = self._estimate_attendance(event1) + self._estimate_attendance(event2)
                
                if estimated_attendance > venue_info.capacity:
                    severity = min(estimated_attendance / venue_info.capacity - 1.0, 1.0)
                    
                    return ScheduleConflict(
                        event1=event1,
                        event2=event2,
                        conflict_type=ConflictType.VENUE_CAPACITY,
                        severity=severity,
                        description=f"会場定員({venue_info.capacity}名)を超過する可能性があります",
                        suggestions=[
                            "より大きな会場に変更する",
                            "時間を分けて開催する",
                            "事前予約制にする"
                        ],
                        auto_resolvable=False
                    )
        
        return None
    
    def _check_travel_time(self, event1: EnhancedEvent, event2: EnhancedEvent) -> Optional[ScheduleConflict]:
        """Check for travel time conflicts between sequential events."""
        if not event1.timing or not event2.timing or not event1.location or not event2.location:
            return None
        
        # Only check if events are on the same day
        if event1.timing.start_date != event2.timing.start_date:
            return None
        
        # Only check if both have specific times
        if not event1.timing.end_time or not event2.timing.start_time:
            return None
        
        # Calculate travel time between venues
        travel_time = self._calculate_travel_time(event1.location, event2.location)
        
        if travel_time > 0:
            # Time gap between events
            gap_minutes = (
                datetime.combine(date.today(), event2.timing.start_time) - 
                datetime.combine(date.today(), event1.timing.end_time)
            ).total_seconds() / 60
            
            if gap_minutes < travel_time:
                severity = min((travel_time - gap_minutes) / travel_time, 1.0)
                
                return ScheduleConflict(
                    event1=event1,
                    event2=event2,
                    conflict_type=ConflictType.TRAVEL_TIME,
                    severity=severity,
                    description=f"移動時間({travel_time:.0f}分)が不足しています",
                    suggestions=[
                        "イベント間の時間を増やす",
                        "近い会場に変更する",
                        "移動手段を確保する"
                    ],
                    auto_resolvable=(severity < 0.5)
                )
        
        return None
    
    def _check_category_clash(self, event1: EnhancedEvent, event2: EnhancedEvent) -> Optional[ScheduleConflict]:
        """Check for category-based conflicts (competing events)."""
        if not self._events_time_overlap(event1, event2):
            return None
        
        # Events in same category might compete for audience
        if event1.category == event2.category and event1.category != EventCategory.OTHER:
            
            # Higher conflict for entertainment/festival events
            high_conflict_categories = [
                EventCategory.FESTIVAL, 
                EventCategory.ENTERTAINMENT, 
                EventCategory.MARKET
            ]
            
            if event1.category in high_conflict_categories:
                severity = 0.6
                description = f"同じカテゴリー({event1.category.value})のイベントが競合しています"
                
                return ScheduleConflict(
                    event1=event1,
                    event2=event2,
                    conflict_type=ConflictType.CATEGORY_CLASH,
                    severity=severity,
                    description=description,
                    suggestions=[
                        "ターゲット層を分ける",
                        "連携してイベントを合同開催する",
                        "日程を調整する"
                    ],
                    auto_resolvable=False
                )
        
        return None
    
    def _events_time_overlap(self, event1: EnhancedEvent, event2: EnhancedEvent) -> bool:
        """Check if two events have any time overlap."""
        if not event1.timing or not event2.timing:
            return False
        
        start1 = event1.timing.start_date
        end1 = event1.timing.end_date or event1.timing.start_date
        start2 = event2.timing.start_date
        end2 = event2.timing.end_date or event2.timing.start_date
        
        return not (end1 < start2 or end2 < start1)
    
    def _estimate_attendance(self, event: EnhancedEvent) -> int:
        """Estimate event attendance based on various factors."""
        base_attendance = 100  # Base attendance
        
        # Adjust by category
        category_multipliers = {
            EventCategory.FESTIVAL: 5.0,
            EventCategory.ENTERTAINMENT: 3.0,
            EventCategory.CULTURE: 2.0,
            EventCategory.SPORTS: 2.5,
            EventCategory.MARKET: 1.5,
            EventCategory.FOOD: 2.0,
            EventCategory.NATURE: 1.8,
            EventCategory.EDUCATION: 1.2,
            EventCategory.BUSINESS: 1.0,
            EventCategory.OTHER: 0.8
        }
        
        multiplier = category_multipliers.get(event.category, 1.0)
        
        # Adjust by quality score
        quality_factor = event.quality_score / 100.0
        
        # Adjust by pricing
        if event.pricing and not event.pricing.is_free:
            if event.pricing.adult_price and event.pricing.adult_price > 1000:
                multiplier *= 0.7  # Expensive events have lower attendance
        
        # Adjust by day of week (if we can determine it)
        if event.timing and event.timing.start_date:
            weekday = event.timing.start_date.weekday()
            if weekday >= 5:  # Weekend
                multiplier *= 1.5
        
        estimated = int(base_attendance * multiplier * quality_factor)
        return max(estimated, 10)  # Minimum 10 people
    
    def _calculate_travel_time(self, location1: EventLocation, location2: EventLocation) -> float:
        """Calculate travel time between two locations in minutes."""
        if not location1.name or not location2.name:
            return 0.0
        
        # If same location, no travel time
        if location1.name == location2.name:
            return 0.0
        
        # If we have coordinates, calculate distance
        if (location1.latitude and location1.longitude and 
            location2.latitude and location2.longitude):
            
            distance_km = self._haversine_distance(
                location1.latitude, location1.longitude,
                location2.latitude, location2.longitude
            )
            
            # Estimate travel time (assuming 30km/h average in city)
            travel_time_minutes = (distance_km / 30.0) * 60
            return travel_time_minutes
        
        # Default estimation based on location names
        if location1.city and location2.city and location1.city != location2.city:
            return 45.0  # Inter-city travel
        
        # Same city, different venues
        return 15.0  # Intra-city travel
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance between two points on Earth."""
        R = 6371  # Earth's radius in kilometers
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2) * math.sin(dlon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def optimize_schedule(self, events: List[EnhancedEvent]) -> ScheduleOptimization:
        """Optimize event schedule to minimize conflicts."""
        conflicts = self.detect_conflicts(events)
        optimized_events = events.copy()
        resolved_conflicts = []
        remaining_conflicts = []
        
        # Sort conflicts by severity (highest first)
        conflicts.sort(key=lambda c: c.severity, reverse=True)
        
        for conflict in conflicts:
            if conflict.auto_resolvable:
                # Try to auto-resolve the conflict
                if self._try_auto_resolve(conflict, optimized_events):
                    resolved_conflicts.append(conflict)
                else:
                    remaining_conflicts.append(conflict)
            else:
                remaining_conflicts.append(conflict)
        
        # Calculate optimization score
        initial_conflict_score = sum(c.severity for c in conflicts)
        remaining_conflict_score = sum(c.severity for c in remaining_conflicts)
        
        if initial_conflict_score > 0:
            optimization_score = 1.0 - (remaining_conflict_score / initial_conflict_score)
        else:
            optimization_score = 1.0
        
        # Generate recommendations
        recommendations = self._generate_recommendations(remaining_conflicts)
        
        return ScheduleOptimization(
            optimized_events=optimized_events,
            conflicts_resolved=resolved_conflicts,
            remaining_conflicts=remaining_conflicts,
            optimization_score=optimization_score,
            recommendations=recommendations
        )
    
    def _try_auto_resolve(self, conflict: ScheduleConflict, events: List[EnhancedEvent]) -> bool:
        """Try to automatically resolve a conflict."""
        if conflict.conflict_type == ConflictType.TIME_OVERLAP and conflict.severity < 0.3:
            # Try to adjust event times slightly
            return self._adjust_event_times(conflict, events)
        
        return False
    
    def _adjust_event_times(self, conflict: ScheduleConflict, events: List[EnhancedEvent]) -> bool:
        """Try to adjust event times to resolve minor conflicts."""
        event1 = conflict.event1
        event2 = conflict.event2
        
        if not event1.timing or not event2.timing:
            return False
        
        # Only adjust if both events have specific times
        if not (event1.timing.start_time and event1.timing.end_time and 
                event2.timing.start_time and event2.timing.end_time):
            return False
        
        # Determine which event has lower priority
        priority1 = self.determine_event_priority(event1)
        priority2 = self.determine_event_priority(event2)
        
        if priority1.value > priority2.value:
            # Adjust event2
            adjustment_minutes = 30
            new_start = (datetime.combine(date.today(), event2.timing.start_time) + 
                        timedelta(minutes=adjustment_minutes)).time()
            new_end = (datetime.combine(date.today(), event2.timing.end_time) + 
                      timedelta(minutes=adjustment_minutes)).time()
            
            event2.timing.start_time = new_start
            event2.timing.end_time = new_end
            return True
        
        elif priority2.value > priority1.value:
            # Adjust event1
            adjustment_minutes = 30
            new_start = (datetime.combine(date.today(), event1.timing.start_time) + 
                        timedelta(minutes=adjustment_minutes)).time()
            new_end = (datetime.combine(date.today(), event1.timing.end_time) + 
                      timedelta(minutes=adjustment_minutes)).time()
            
            event1.timing.start_time = new_start
            event1.timing.end_time = new_end
            return True
        
        return False
    
    def _generate_recommendations(self, conflicts: List[ScheduleConflict]) -> List[str]:
        """Generate recommendations based on remaining conflicts."""
        recommendations = []
        
        conflict_types = {}
        for conflict in conflicts:
            conflict_type = conflict.conflict_type
            if conflict_type not in conflict_types:
                conflict_types[conflict_type] = []
            conflict_types[conflict_type].append(conflict)
        
        if ConflictType.TIME_OVERLAP in conflict_types:
            count = len(conflict_types[ConflictType.TIME_OVERLAP])
            recommendations.append(f"{count}件の時間重複があります。イベント時間の調整を検討してください。")
        
        if ConflictType.VENUE_CAPACITY in conflict_types:
            count = len(conflict_types[ConflictType.VENUE_CAPACITY])
            recommendations.append(f"{count}件の会場定員不足があります。より大きな会場への変更を検討してください。")
        
        if ConflictType.TRAVEL_TIME in conflict_types:
            count = len(conflict_types[ConflictType.TRAVEL_TIME])
            recommendations.append(f"{count}件の移動時間不足があります。イベント間の時間調整を検討してください。")
        
        if ConflictType.CATEGORY_CLASH in conflict_types:
            count = len(conflict_types[ConflictType.CATEGORY_CLASH])
            recommendations.append(f"{count}件のカテゴリー競合があります。イベントの連携や差別化を検討してください。")
        
        return recommendations
    
    def generate_schedule_report(self, events: List[EnhancedEvent]) -> Dict[str, Any]:
        """Generate comprehensive schedule analysis report."""
        optimization = self.optimize_schedule(events)
        
        # Event statistics
        total_events = len(events)
        events_by_category = {}
        events_by_date = {}
        quality_distribution = {"high": 0, "medium": 0, "low": 0, "poor": 0}
        
        for event in events:
            # Category distribution
            category = event.category.value
            events_by_category[category] = events_by_category.get(category, 0) + 1
            
            # Date distribution
            if event.timing:
                date_str = event.timing.start_date.isoformat()
                events_by_date[date_str] = events_by_date.get(date_str, 0) + 1
            
            # Quality distribution
            quality_distribution[event.quality_level.value] += 1
        
        # Generate insights
        insights = []
        
        # Peak days
        if events_by_date:
            peak_date = max(events_by_date, key=events_by_date.get)
            peak_count = events_by_date[peak_date]
            if peak_count > 3:
                insights.append(f"{peak_date}に{peak_count}件のイベントが集中しています")
        
        # Category insights
        top_category = max(events_by_category, key=events_by_category.get) if events_by_category else None
        if top_category:
            count = events_by_category[top_category]
            insights.append(f"{top_category}カテゴリーが最多で{count}件です")
        
        # Quality insights
        low_quality_count = quality_distribution["low"] + quality_distribution["poor"]
        if low_quality_count > total_events * 0.3:
            insights.append(f"データ品質の低いイベントが{low_quality_count}件あります")
        
        return {
            "summary": {
                "total_events": total_events,
                "conflicts_detected": len(optimization.remaining_conflicts),
                "conflicts_resolved": len(optimization.conflicts_resolved),
                "optimization_score": optimization.optimization_score
            },
            "distribution": {
                "by_category": events_by_category,
                "by_date": events_by_date,
                "by_quality": quality_distribution
            },
            "conflicts": [
                {
                    "type": c.conflict_type.value,
                    "severity": c.severity,
                    "description": c.description,
                    "event1": c.event1.title,
                    "event2": c.event2.title
                }
                for c in optimization.remaining_conflicts
            ],
            "recommendations": optimization.recommendations,
            "insights": insights
        }


if __name__ == "__main__":
    # Test the smart scheduler
    from enhanced_parser import EnhancedEventParser, EventTiming, EventLocation
    
    # Create test events
    events = []
    
    # Create test event 1
    event1 = EnhancedEvent(
        title="高岡七夕まつり",
        timing=EventTiming(
            start_date=date(2025, 7, 7),
            start_time=time(10, 0),
            end_time=time(16, 0),
            is_all_day=False
        ),
        location=EventLocation(name="高岡市中心部", city="高岡市")
    )
    
    # Create test event 2 (overlapping time)
    event2 = EnhancedEvent(
        title="高岡花火大会",
        timing=EventTiming(
            start_date=date(2025, 7, 7),
            start_time=time(14, 0),
            end_time=time(20, 0),
            is_all_day=False
        ),
        location=EventLocation(name="高岡市民会館", city="高岡市")
    )
    
    events = [event1, event2]
    
    scheduler = SmartScheduler()
    conflicts = scheduler.detect_conflicts(events)
    
    print(f"Detected {len(conflicts)} conflicts:")
    for conflict in conflicts:
        print(f"- {conflict.conflict_type.value}: {conflict.description} (severity: {conflict.severity:.2f})")
    
    # Generate schedule report
    report = scheduler.generate_schedule_report(events)
    print(f"\nSchedule Report:")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))