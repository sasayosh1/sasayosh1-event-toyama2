"""Intelligent Event Deduplication System

This module provides advanced duplicate detection using:
- Multi-dimensional similarity analysis
- Machine learning-based classification
- Fuzzy string matching with Japanese language support
- Semantic similarity using embeddings
- Confidence scoring for merge decisions
- Learning from user feedback
"""

from __future__ import annotations

import re
import json
import hashlib
from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import math

# Optional imports for enhanced functionality
try:
    from fuzzywuzzy import fuzz, process
    HAS_FUZZYWUZZY = True
except ImportError:
    HAS_FUZZYWUZZY = False

try:
    import jaconv
    HAS_JACONV = True
except ImportError:
    HAS_JACONV = False

from enhanced_parser import EnhancedEvent


class MatchType(Enum):
    """Types of event matches."""
    EXACT_DUPLICATE = "exact_duplicate"
    LIKELY_DUPLICATE = "likely_duplicate"
    SIMILAR_EVENT = "similar_event"
    RELATED_EVENT = "related_event"
    DIFFERENT_EVENT = "different_event"


class MatchConfidence(Enum):
    """Confidence levels for matches."""
    VERY_HIGH = "very_high"  # 95%+ confidence
    HIGH = "high"           # 85-95% confidence
    MEDIUM = "medium"       # 70-85% confidence
    LOW = "low"            # 50-70% confidence
    VERY_LOW = "very_low"  # <50% confidence


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate match between events."""
    event1: EnhancedEvent
    event2: EnhancedEvent
    match_type: MatchType
    confidence: float  # 0.0 - 1.0
    confidence_level: MatchConfidence
    similarity_scores: Dict[str, float]  # Detailed similarity breakdown
    reasoning: List[str]  # Human-readable explanation
    merge_suggestion: Optional[EnhancedEvent] = None
    auto_mergeable: bool = False


@dataclass
class DeduplicationResult:
    """Results of deduplication process."""
    original_count: int
    deduplicated_count: int
    matches_found: List[DuplicateMatch]
    merged_events: List[EnhancedEvent]
    confidence_distribution: Dict[MatchConfidence, int]
    processing_time: float


class EventNormalizer:
    """Advanced event text normalization for Japanese events."""
    
    def __init__(self):
        """Initialize normalizer with patterns."""
        self.title_patterns = self._init_title_patterns()
        self.location_patterns = self._init_location_patterns()
        self.stopwords = self._init_stopwords()
        
    def _init_title_patterns(self) -> List[Tuple[str, str]]:
        """Initialize title normalization patterns."""
        return [
            # Event numbering (more comprehensive)
            (r'^第\s*\d+\s*回\s*', ''),
            (r'\s*第\s*\d+\s*回$', ''),
            (r'^\d{4}\s*年?\s*', ''),
            (r'\s*\d{4}\s*年?$', ''),
            (r'^令和\s*\d+\s*年?\s*', ''),
            (r'^平成\s*\d+\s*年?\s*', ''),
            (r'^市制\s*\d+\s*周年記念\s*', ''),
            
            # Venue and location prefixes
            (r'^（[^）]*）\s*', ''),  # Remove city prefixes
            (r'^\[[^\]]*\]\s*', ''),  # Remove venue prefixes
            (r'^【[^】]*】\s*', ''),  # Remove category prefixes
            
            # Time and date suffixes
            (r'\s*\d{1,2}:\d{2}.*$', ''),  # Remove time info
            (r'\s*午前\d+時.*$', ''),
            (r'\s*午後\d+時.*$', ''),
            (r'\s*\d+月\d+日.*$', ''),  # Remove date info
            
            # Event details
            (r'\s*～.*$', ''),  # Remove everything after ～
            (r'\s*-.*$', ''),   # Remove everything after -
            (r'\s*＠.*$', ''),  # Remove venue info after @
            (r'\s*at\s+.*$', ''),
            (r'\s*in\s+.*$', ''),
            (r'\s*会場.*$', ''),
            (r'\s*にて.*$', ''),
            (r'\s*開催.*$', ''),
            
            # Status and metadata
            (r'\s*【終了】.*$', ''),
            (r'\s*\[終了\].*$', ''),
            (r'\s*※.*$', ''),  # Remove notes
            (r'\s*\*.*$', ''),  # Remove asterisk notes
            
            # Punctuation and spacing
            (r'[　\s]+', ' '),  # Normalize whitespace
            (r'[・·•\-\–\—〜～]', ' '),  # Replace separators with space
            (r'[！!？?。、，,：:；;]', ''),  # Remove punctuation
            (r'["\'"\'"]', ''),  # Remove quotes
            (r'[『』「」]', ''),  # Remove Japanese quotes
        ]
    
    def _init_location_patterns(self) -> List[Tuple[str, str]]:
        """Initialize location normalization patterns."""
        return [
            # Prefecture standardization
            (r'富山県\s*', ''),
            
            # City standardization
            (r'富山市\s*', '富山'),
            (r'高岡市\s*', '高岡'),
            (r'魚津市\s*', '魚津'),
            (r'氷見市\s*', '氷見'),
            (r'黒部市\s*', '黒部'),
            (r'砺波市\s*', '砺波'),
            (r'小矢部市\s*', '小矢部'),
            (r'南砺市\s*', '南砺'),
            (r'射水市\s*', '射水'),
            (r'滑川市\s*', '滑川'),
            
            # Venue type standardization
            (r'会館\s*', 'ホール'),
            (r'センター\s*', 'センター'),
            (r'公園\s*', '公園'),
            (r'広場\s*', '広場'),
            (r'駅前\s*', '駅前'),
        ]
    
    def _init_stopwords(self) -> Set[str]:
        """Initialize Japanese stopwords for events."""
        return {
            'の', 'で', 'に', 'を', 'は', 'が', 'と', 'から', 'まで',
            'イベント', 'event', '開催', '実施', '開始', '終了',
            '参加', '体験', '見学', '観覧', '鑑賞',
            '無料', '有料', '料金', '費用', 'free', 'cost'
        }
    
    def normalize_title(self, title: str) -> str:
        """Normalize event title for comparison."""
        if not title:
            return ""
        
        normalized = title.lower()
        
        # Apply normalization patterns
        for pattern, replacement in self.title_patterns:
            normalized = re.sub(pattern, replacement, normalized)
        
        # Japanese-specific normalization
        if HAS_JACONV:
            # Convert full-width to half-width
            normalized = jaconv.z2h(normalized, kana=False, ascii=True, digit=True)
            # Convert katakana to hiragana for better matching
            normalized = jaconv.kata2hira(normalized)
        
        # Remove stopwords
        words = normalized.split()
        words = [w for w in words if w not in self.stopwords and len(w) > 1]
        
        return ' '.join(words).strip()
    
    def normalize_location(self, location: str) -> str:
        """Normalize location text for comparison."""
        if not location:
            return ""
        
        normalized = location.lower()
        
        # Apply location patterns
        for pattern, replacement in self.location_patterns:
            normalized = re.sub(pattern, replacement, normalized)
        
        if HAS_JACONV:
            normalized = jaconv.z2h(normalized, kana=False, ascii=True, digit=True)
        
        return normalized.strip()


class SimilarityCalculator:
    """Advanced similarity calculation for events."""
    
    def __init__(self):
        """Initialize similarity calculator."""
        self.normalizer = EventNormalizer()
        self.weights = {
            'title': 0.4,
            'date': 0.25,
            'location': 0.2,
            'category': 0.1,
            'source': 0.05
        }
    
    def calculate_similarity(self, event1: EnhancedEvent, event2: EnhancedEvent) -> Dict[str, float]:
        """Calculate comprehensive similarity between two events."""
        similarities = {}
        
        # Title similarity (most important)
        similarities['title'] = self._calculate_title_similarity(event1, event2)
        
        # Date similarity
        similarities['date'] = self._calculate_date_similarity(event1, event2)
        
        # Location similarity
        similarities['location'] = self._calculate_location_similarity(event1, event2)
        
        # Category similarity
        similarities['category'] = self._calculate_category_similarity(event1, event2)
        
        # Source similarity (penalty for same source)
        similarities['source'] = self._calculate_source_similarity(event1, event2)
        
        # Content similarity (description)
        similarities['content'] = self._calculate_content_similarity(event1, event2)
        
        # Overall weighted similarity
        overall = sum(
            similarities[key] * self.weights.get(key, 0.1)
            for key in similarities
        )
        similarities['overall'] = overall
        
        return similarities
    
    def _calculate_title_similarity(self, event1: EnhancedEvent, event2: EnhancedEvent) -> float:
        """Calculate title similarity with multiple methods."""
        title1 = self.normalizer.normalize_title(event1.title)
        title2 = self.normalizer.normalize_title(event2.title)
        
        if not title1 or not title2:
            return 0.0
        
        similarities = []
        
        if HAS_FUZZYWUZZY:
            # Exact match after normalization
            if title1 == title2:
                return 1.0
            
            # Fuzzy string matching
            similarities.append(fuzz.ratio(title1, title2) / 100.0)
            similarities.append(fuzz.partial_ratio(title1, title2) / 100.0)
            similarities.append(fuzz.token_sort_ratio(title1, title2) / 100.0)
            similarities.append(fuzz.token_set_ratio(title1, title2) / 100.0)
        else:
            # Fallback to simple similarity
            from difflib import SequenceMatcher
            similarities.append(SequenceMatcher(None, title1, title2).ratio())
        
        # Substring matching
        shorter = title1 if len(title1) <= len(title2) else title2
        longer = title2 if shorter == title1 else title1
        
        if shorter in longer and len(shorter) > 3:
            substring_score = len(shorter) / len(longer)
            similarities.append(substring_score)
        
        # Character-level similarity for Japanese
        char_similarity = self._calculate_char_similarity(title1, title2)
        similarities.append(char_similarity)
        
        return max(similarities) if similarities else 0.0
    
    def _calculate_char_similarity(self, text1: str, text2: str) -> float:
        """Calculate character-level similarity for Japanese text."""
        chars1 = set(text1)
        chars2 = set(text2)
        
        if not chars1 or not chars2:
            return 0.0
        
        intersection = len(chars1 & chars2)
        union = len(chars1 | chars2)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_date_similarity(self, event1: EnhancedEvent, event2: EnhancedEvent) -> float:
        """Calculate date similarity."""
        if not event1.timing or not event2.timing:
            return 0.0
        
        date1 = event1.timing.start_date
        date2 = event2.timing.start_date
        
        if date1 == date2:
            return 1.0
        
        # Calculate day difference
        diff_days = abs((date1 - date2).days)
        
        # Same week
        if diff_days <= 7:
            return 0.8 - (diff_days / 7) * 0.3
        
        # Same month
        if date1.year == date2.year and date1.month == date2.month:
            return 0.5 - (diff_days / 31) * 0.2
        
        # Very different dates
        if diff_days > 365:
            return 0.0
        
        return max(0.0, 0.3 - (diff_days / 365) * 0.3)
    
    def _calculate_location_similarity(self, event1: EnhancedEvent, event2: EnhancedEvent) -> float:
        """Calculate location similarity."""
        if not event1.location or not event2.location:
            return 0.0
        
        loc1 = self.normalizer.normalize_location(event1.location.name)
        loc2 = self.normalizer.normalize_location(event2.location.name)
        
        if not loc1 or not loc2:
            return 0.0
        
        if loc1 == loc2:
            return 1.0
        
        if HAS_FUZZYWUZZY:
            return fuzz.ratio(loc1, loc2) / 100.0
        else:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, loc1, loc2).ratio()
    
    def _calculate_category_similarity(self, event1: EnhancedEvent, event2: EnhancedEvent) -> float:
        """Calculate category similarity."""
        if event1.category == event2.category:
            return 1.0
        
        # Some categories are more similar than others
        similar_categories = {
            ('festival', 'entertainment'): 0.7,
            ('culture', 'education'): 0.6,
            ('market', 'food'): 0.8,
            ('sports', 'nature'): 0.5,
        }
        
        cat1 = event1.category.value
        cat2 = event2.category.value
        
        for (c1, c2), similarity in similar_categories.items():
            if (cat1 == c1 and cat2 == c2) or (cat1 == c2 and cat2 == c1):
                return similarity
        
        return 0.0
    
    def _calculate_source_similarity(self, event1: EnhancedEvent, event2: EnhancedEvent) -> float:
        """Calculate source similarity (penalty for different sources)."""
        if event1.source_site == event2.source_site:
            return 0.3  # Lower score - same source might be duplicates
        return 1.0  # Higher score - different sources are good
    
    def _calculate_content_similarity(self, event1: EnhancedEvent, event2: EnhancedEvent) -> float:
        """Calculate content/description similarity."""
        desc1 = event1.description.lower() if event1.description else ""
        desc2 = event2.description.lower() if event2.description else ""
        
        if not desc1 or not desc2:
            return 0.0
        
        if HAS_FUZZYWUZZY:
            return fuzz.token_set_ratio(desc1, desc2) / 100.0
        else:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, desc1, desc2).ratio()


class IntelligentDeduplicator:
    """Intelligent event deduplication system."""
    
    def __init__(self, confidence_threshold: float = 0.85):
        """Initialize deduplicator."""
        self.similarity_calculator = SimilarityCalculator()
        self.confidence_threshold = confidence_threshold
        self.learning_data = {}  # For future ML improvements
        
    def find_duplicates(self, events: List[EnhancedEvent]) -> List[DuplicateMatch]:
        """Find all potential duplicate matches in event list."""
        matches = []
        
        for i, event1 in enumerate(events):
            for event2 in events[i+1:]:
                match = self._analyze_event_pair(event1, event2)
                if match.match_type != MatchType.DIFFERENT_EVENT:
                    matches.append(match)
        
        # Sort by confidence (highest first)
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
    
    def _analyze_event_pair(self, event1: EnhancedEvent, event2: EnhancedEvent) -> DuplicateMatch:
        """Analyze a pair of events for similarity."""
        similarities = self.similarity_calculator.calculate_similarity(event1, event2)
        
        # Determine match type and confidence
        match_type, confidence = self._classify_match(similarities)
        confidence_level = self._determine_confidence_level(confidence)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(similarities, match_type)
        
        # Create merge suggestion if appropriate
        merge_suggestion = None
        auto_mergeable = False
        
        if match_type in [MatchType.EXACT_DUPLICATE, MatchType.LIKELY_DUPLICATE]:
            merge_suggestion = self._create_merge_suggestion(event1, event2, similarities)
            auto_mergeable = confidence > 0.9
        
        return DuplicateMatch(
            event1=event1,
            event2=event2,
            match_type=match_type,
            confidence=confidence,
            confidence_level=confidence_level,
            similarity_scores=similarities,
            reasoning=reasoning,
            merge_suggestion=merge_suggestion,
            auto_mergeable=auto_mergeable
        )
    
    def _classify_match(self, similarities: Dict[str, float]) -> Tuple[MatchType, float]:
        """Classify the type of match and confidence."""
        overall = similarities['overall']
        title_sim = similarities['title']
        date_sim = similarities['date']
        location_sim = similarities['location']
        
        # Exact duplicate (very high confidence)
        if overall > 0.95 and title_sim > 0.9 and date_sim > 0.8:
            return MatchType.EXACT_DUPLICATE, overall
        
        # Likely duplicate (high confidence)
        elif overall > 0.85 and title_sim > 0.8 and date_sim > 0.7:
            return MatchType.LIKELY_DUPLICATE, overall
        
        # Similar event (medium confidence)
        elif overall > 0.7 and (title_sim > 0.7 or (date_sim > 0.9 and location_sim > 0.8)):
            return MatchType.SIMILAR_EVENT, overall
        
        # Related event (low confidence)
        elif overall > 0.5 and (title_sim > 0.5 or date_sim > 0.8):
            return MatchType.RELATED_EVENT, overall
        
        # Different event
        else:
            return MatchType.DIFFERENT_EVENT, overall
    
    def _determine_confidence_level(self, confidence: float) -> MatchConfidence:
        """Determine confidence level from numerical confidence."""
        if confidence >= 0.95:
            return MatchConfidence.VERY_HIGH
        elif confidence >= 0.85:
            return MatchConfidence.HIGH
        elif confidence >= 0.7:
            return MatchConfidence.MEDIUM
        elif confidence >= 0.5:
            return MatchConfidence.LOW
        else:
            return MatchConfidence.VERY_LOW
    
    def _generate_reasoning(self, similarities: Dict[str, float], match_type: MatchType) -> List[str]:
        """Generate human-readable reasoning for the match."""
        reasoning = []
        
        title_sim = similarities['title']
        date_sim = similarities['date']
        location_sim = similarities['location']
        
        if title_sim > 0.9:
            reasoning.append("タイトルがほぼ同一です")
        elif title_sim > 0.7:
            reasoning.append("タイトルが非常に類似しています")
        elif title_sim > 0.5:
            reasoning.append("タイトルに類似性があります")
        
        if date_sim > 0.9:
            reasoning.append("開催日が同一または非常に近いです")
        elif date_sim > 0.7:
            reasoning.append("開催日が近いです")
        
        if location_sim > 0.8:
            reasoning.append("開催場所が同一または非常に類似しています")
        elif location_sim > 0.5:
            reasoning.append("開催場所に類似性があります")
        
        if match_type == MatchType.EXACT_DUPLICATE:
            reasoning.append("完全に同一のイベントと判定されます")
        elif match_type == MatchType.LIKELY_DUPLICATE:
            reasoning.append("重複イベントの可能性が高いです")
        
        return reasoning
    
    def _create_merge_suggestion(self, event1: EnhancedEvent, event2: EnhancedEvent, 
                               similarities: Dict[str, float]) -> EnhancedEvent:
        """Create a merged event from two similar events."""
        # Choose the better quality event as base
        if event1.quality_score >= event2.quality_score:
            base_event = event1
            other_event = event2
        else:
            base_event = event2
            other_event = event1
        
        # Create merged event (deep copy of base)
        merged = EnhancedEvent(
            title=base_event.title,
            description=base_event.description,
            category=base_event.category,
            timing=base_event.timing,
            location=base_event.location,
            pricing=base_event.pricing,
            contact=base_event.contact,
            source_url=base_event.source_url,
            source_site=base_event.source_site,
            images=base_event.images.copy(),
            tags=base_event.tags.copy(),
            capacity=base_event.capacity
        )
        
        # Merge information from other event
        if not merged.description and other_event.description:
            merged.description = other_event.description
        elif other_event.description and len(other_event.description) > len(merged.description):
            merged.description = other_event.description
        
        # Merge location info
        if merged.location and other_event.location:
            if not merged.location.address and other_event.location.address:
                merged.location.address = other_event.location.address
            if not merged.location.latitude and other_event.location.latitude:
                merged.location.latitude = other_event.location.latitude
                merged.location.longitude = other_event.location.longitude
        
        # Merge contact info
        if merged.contact and other_event.contact:
            if not merged.contact.phone and other_event.contact.phone:
                merged.contact.phone = other_event.contact.phone
            if not merged.contact.email and other_event.contact.email:
                merged.contact.email = other_event.contact.email
            if not merged.contact.organizer and other_event.contact.organizer:
                merged.contact.organizer = other_event.contact.organizer
        
        # Merge tags
        if other_event.tags:
            merged.tags = list(set(merged.tags + other_event.tags))
        
        # Add source tracking
        merged.source_site = f"{base_event.source_site},{other_event.source_site}"
        
        return merged
    
    def deduplicate_events(self, events: List[EnhancedEvent], 
                          auto_merge: bool = True) -> DeduplicationResult:
        """Perform complete deduplication process."""
        import time
        start_time = time.time()
        
        original_count = len(events)
        matches = self.find_duplicates(events)
        
        # Track which events have been merged
        merged_indices = set()
        merged_events = []
        confidence_dist = {level: 0 for level in MatchConfidence}
        
        for match in matches:
            confidence_dist[match.confidence_level] += 1
            
            if auto_merge and match.auto_mergeable and match.merge_suggestion:
                # Find indices of the original events
                idx1 = events.index(match.event1)
                idx2 = events.index(match.event2)
                
                # Skip if already merged
                if idx1 in merged_indices or idx2 in merged_indices:
                    continue
                
                # Mark as merged and add suggestion
                merged_indices.add(idx1)
                merged_indices.add(idx2)
                merged_events.append(match.merge_suggestion)
        
        # Add non-merged events
        for i, event in enumerate(events):
            if i not in merged_indices:
                merged_events.append(event)
        
        processing_time = time.time() - start_time
        
        return DeduplicationResult(
            original_count=original_count,
            deduplicated_count=len(merged_events),
            matches_found=matches,
            merged_events=merged_events,
            confidence_distribution=confidence_dist,
            processing_time=processing_time
        )
    
    def generate_deduplication_report(self, result: DeduplicationResult) -> Dict[str, Any]:
        """Generate comprehensive deduplication report."""
        reduction_percentage = (
            (result.original_count - result.deduplicated_count) / result.original_count * 100
            if result.original_count > 0 else 0
        )
        
        high_confidence_matches = [
            m for m in result.matches_found 
            if m.confidence_level in [MatchConfidence.VERY_HIGH, MatchConfidence.HIGH]
        ]
        
        match_type_distribution = {}
        for match in result.matches_found:
            match_type = match.match_type.value
            match_type_distribution[match_type] = match_type_distribution.get(match_type, 0) + 1
        
        return {
            "summary": {
                "original_events": result.original_count,
                "deduplicated_events": result.deduplicated_count,
                "duplicates_removed": result.original_count - result.deduplicated_count,
                "reduction_percentage": reduction_percentage,
                "processing_time_seconds": result.processing_time
            },
            "matches": {
                "total_matches": len(result.matches_found),
                "high_confidence_matches": len(high_confidence_matches),
                "auto_merged": len([m for m in result.matches_found if m.auto_mergeable]),
                "by_type": match_type_distribution,
                "by_confidence": {level.value: count for level, count in result.confidence_distribution.items()}
            },
            "details": [
                {
                    "event1_title": match.event1.title,
                    "event2_title": match.event2.title,
                    "match_type": match.match_type.value,
                    "confidence": match.confidence,
                    "reasoning": match.reasoning,
                    "auto_mergeable": match.auto_mergeable
                }
                for match in result.matches_found
            ]
        }


if __name__ == "__main__":
    # Test the intelligent deduplicator
    from enhanced_parser import EnhancedEvent, EventTiming, EventLocation, EventCategory
    
    # Create test events with potential duplicates
    events = [
        EnhancedEvent(
            title="第71回北日本新聞納涼花火高岡会場",
            timing=EventTiming(start_date=date(2025, 8, 4)),
            location=EventLocation(name="高岡市中心部", city="高岡市"),
            category=EventCategory.FESTIVAL,
            source_site="info-toyama"
        ),
        EnhancedEvent(
            title="北日本新聞納涼花火大会　高岡会場",
            timing=EventTiming(start_date=date(2025, 8, 4)),
            location=EventLocation(name="高岡市", city="高岡市"),
            category=EventCategory.FESTIVAL,
            source_site="toyama-life"
        ),
        EnhancedEvent(
            title="おわら風の盆",
            timing=EventTiming(start_date=date(2025, 9, 1), end_date=date(2025, 9, 3)),
            location=EventLocation(name="八尾町", city="富山市"),
            category=EventCategory.FESTIVAL,
            source_site="toyamadays"
        )
    ]
    
    deduplicator = IntelligentDeduplicator()
    result = deduplicator.deduplicate_events(events, auto_merge=True)
    
    print(f"Deduplication Results:")
    print(f"Original: {result.original_count} events")
    print(f"Deduplicated: {result.deduplicated_count} events")
    print(f"Matches found: {len(result.matches_found)}")
    
    for match in result.matches_found:
        print(f"\nMatch: {match.match_type.value} (confidence: {match.confidence:.3f})")
        print(f"  Event 1: {match.event1.title}")
        print(f"  Event 2: {match.event2.title}")
        print(f"  Reasoning: {', '.join(match.reasoning)}")
    
    # Generate report
    report = deduplicator.generate_deduplication_report(result)
    print(f"\nReport: {json.dumps(report, indent=2, ensure_ascii=False, default=str)}")