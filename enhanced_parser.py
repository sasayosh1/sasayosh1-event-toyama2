"""Enhanced Event Parser for Toyama Events

This module provides advanced event parsing capabilities including:
- Time-specific event parsing (not just all-day events)
- Enhanced metadata extraction (pricing, contact info, categories)
- Natural language processing for better description parsing
- Location standardization and geocoding support
- Event quality scoring and validation
"""

from __future__ import annotations

import re
import json
from datetime import datetime, date, time, timedelta
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

# Optional imports for enhanced functionality
try:
    import geocoder
    HAS_GEOCODER = True
except ImportError:
    HAS_GEOCODER = False

try:
    from fuzzywuzzy import fuzz
    HAS_FUZZYWUZZY = True
except ImportError:
    HAS_FUZZYWUZZY = False


class EventCategory(Enum):
    """Event categories for better organization."""
    FESTIVAL = "festival"
    MARKET = "market"
    SPORTS = "sports"
    CULTURE = "culture"
    FOOD = "food"
    NATURE = "nature"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    BUSINESS = "business"
    OTHER = "other"


class EventQuality(Enum):
    """Event data quality levels."""
    HIGH = "high"      # Complete information with validation
    MEDIUM = "medium"  # Most information present
    LOW = "low"        # Minimal information
    POOR = "poor"      # Incomplete or suspicious data


@dataclass
class EventLocation:
    """Enhanced location information."""
    name: str = ""
    address: str = ""
    city: str = ""
    prefecture: str = "富山県"
    postal_code: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    venue_type: str = ""  # 公園, ホール, 屋外, etc.


@dataclass
class EventTiming:
    """Enhanced timing information."""
    start_date: date
    end_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_all_day: bool = True
    timezone: str = "Asia/Tokyo"
    recurring_pattern: str = ""  # daily, weekly, monthly, etc.
    duration_minutes: Optional[int] = None


@dataclass
class EventPricing:
    """Event pricing information."""
    is_free: bool = True
    adult_price: Optional[int] = None
    child_price: Optional[int] = None
    senior_price: Optional[int] = None
    advance_price: Optional[int] = None
    currency: str = "JPY"
    pricing_notes: str = ""


@dataclass
class EventContact:
    """Event contact information."""
    organizer: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    social_media: Dict[str, str] = None


@dataclass
class EnhancedEvent:
    """Enhanced event data structure."""
    # Basic information
    title: str
    description: str = ""
    category: EventCategory = EventCategory.OTHER
    
    # Timing
    timing: EventTiming = None
    
    # Location
    location: EventLocation = None
    
    # Additional details
    pricing: EventPricing = None
    contact: EventContact = None
    
    # Metadata
    source_url: str = ""
    source_site: str = ""
    images: List[str] = None
    tags: List[str] = None
    capacity: Optional[int] = None
    
    # Quality and processing
    quality_score: float = 0.0
    quality_level: EventQuality = EventQuality.POOR
    confidence_score: float = 0.0
    
    # System
    created_at: datetime = None
    updated_at: datetime = None
    hash_id: str = ""
    
    def __post_init__(self):
        """Initialize defaults and compute hash."""
        if self.images is None:
            self.images = []
        if self.tags is None:
            self.tags = []
        if self.contact is None:
            self.contact = EventContact()
        if self.contact.social_media is None:
            self.contact.social_media = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at
            
        # Generate hash ID
        self.hash_id = self._generate_hash()
        
        # Calculate quality metrics
        self.quality_score = self._calculate_quality_score()
        self.quality_level = self._determine_quality_level()
    
    def _generate_hash(self) -> str:
        """Generate unique hash for the event."""
        content = f"{self.title}{self.timing.start_date if self.timing else ''}{self.location.name if self.location else ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _calculate_quality_score(self) -> float:
        """Calculate event data quality score (0-100)."""
        score = 0.0
        
        # Title quality (20 points)
        if self.title and len(self.title.strip()) > 3:
            score += 20
            if len(self.title) > 10:
                score += 5
        
        # Timing quality (25 points)
        if self.timing:
            score += 15
            if self.timing.start_time:
                score += 5
            if self.timing.end_date or self.timing.end_time:
                score += 5
        
        # Location quality (20 points)
        if self.location and self.location.name:
            score += 10
            if self.location.address:
                score += 5
            if self.location.latitude and self.location.longitude:
                score += 5
        
        # Description quality (15 points)
        if self.description and len(self.description.strip()) > 10:
            score += 10
            if len(self.description) > 50:
                score += 5
        
        # Contact/pricing quality (10 points)
        if self.contact and (self.contact.phone or self.contact.email):
            score += 5
        if self.pricing and not self.pricing.is_free:
            score += 5
        
        # Source quality (10 points)
        if self.source_url and self.source_url.startswith('http'):
            score += 5
        if self.category != EventCategory.OTHER:
            score += 5
        
        return min(score, 100.0)
    
    def _determine_quality_level(self) -> EventQuality:
        """Determine quality level based on score."""
        if self.quality_score >= 80:
            return EventQuality.HIGH
        elif self.quality_score >= 60:
            return EventQuality.MEDIUM
        elif self.quality_score >= 40:
            return EventQuality.LOW
        else:
            return EventQuality.POOR
    
    def to_legacy_format(self) -> Dict[str, Any]:
        """Convert to legacy event format for compatibility."""
        return {
            "title": self.title,
            "start": self.timing.start_date if self.timing else date.today(),
            "end": self.timing.end_date if self.timing else None,
            "location": self.location.name if self.location else "",
            "url": self.source_url,
            "site": self.source_site,
            # Enhanced fields
            "description": self.description,
            "category": self.category.value,
            "quality_score": self.quality_score,
            "confidence": self.confidence_score,
            "hash_id": self.hash_id
        }


class EnhancedEventParser:
    """Enhanced event parser with advanced text processing."""
    
    def __init__(self):
        """Initialize parser with patterns and mappings."""
        self.category_patterns = self._init_category_patterns()
        self.location_patterns = self._init_location_patterns()
        self.time_patterns = self._init_time_patterns()
        self.price_patterns = self._init_price_patterns()
        self.contact_patterns = self._init_contact_patterns()
        
    def _init_category_patterns(self) -> Dict[EventCategory, List[str]]:
        """Initialize category detection patterns."""
        return {
            EventCategory.FESTIVAL: [
                r'まつり|祭り|festival|フェスティバル|盆踊り|花火|hanabi|fireworks',
                r'おわら|風の盆|七夕|tanabata|神楽|kagura|太鼓'
            ],
            EventCategory.MARKET: [
                r'朝市|市場|マーケット|market|マルシェ|marche|バザー|販売会',
                r'物産展|特産品|直売|farmers|産直'
            ],
            EventCategory.SPORTS: [
                r'スポーツ|運動|競技|sports|マラソン|marathon|サッカー|soccer',
                r'野球|baseball|テニス|tennis|ゴルフ|golf|水泳|swimming'
            ],
            EventCategory.CULTURE: [
                r'展示|exhibition|美術館|博物館|museum|アート|art|文化',
                r'コンサート|concert|演奏|音楽|music|劇場|theater'
            ],
            EventCategory.FOOD: [
                r'グルメ|料理|食べ物|food|レストラン|restaurant|酒|sake',
                r'ワイン|wine|ビール|beer|フード|食材|cooking'
            ],
            EventCategory.NATURE: [
                r'自然|nature|公園|park|山|mountain|川|river|海|beach',
                r'花|flower|桜|cherry|紅葉|autumn|ハイキング|hiking'
            ],
            EventCategory.ENTERTAINMENT: [
                r'エンターテイメント|entertainment|ショー|show|パフォーマンス',
                r'映画|movie|アニメ|anime|ゲーム|game|イルミネーション'
            ],
            EventCategory.EDUCATION: [
                r'講座|lecture|セミナー|seminar|教室|class|学習|learning',
                r'体験|experience|ワークショップ|workshop|教育|education'
            ],
            EventCategory.BUSINESS: [
                r'ビジネス|business|企業|company|会議|meeting|展示会',
                r'カンファレンス|conference|商談|networking|startup'
            ]
        }
    
    def _init_location_patterns(self) -> Dict[str, str]:
        """Initialize location standardization patterns."""
        return {
            # Venue types
            r'ホール|会館|センター': 'ホール',
            r'公園|パーク': '公園',
            r'広場|プラザ': '広場',
            r'体育館|アリーナ': '体育館',
            r'美術館|博物館|資料館': '文化施設',
            r'商店街|アーケード': '商店街',
            r'駅前|駅周辺': '駅周辺',
            r'海岸|ビーチ|浜': '海岸',
            r'山|高原|スキー場': '山間部',
            
            # City standardization
            r'富山市|富山駅': '富山市',
            r'高岡市|高岡駅': '高岡市',
            r'魚津市|魚津駅': '魚津市',
            r'氷見市|氷見駅': '氷見市',
            r'黒部市|黒部駅': '黒部市',
            r'砺波市|砺波駅': '砺波市',
            r'小矢部市|小矢部駅': '小矢部市',
            r'南砺市|南砺': '南砺市',
            r'射水市|射水': '射水市',
            r'滑川市|滑川': '滑川市',
            r'上市町|上市': '上市町',
            r'立山町|立山': '立山町',
            r'入善町|入善': '入善町',
            r'朝日町|朝日': '朝日町',
            r'舟橋村|舟橋': '舟橋村'
        }
    
    def _init_time_patterns(self) -> List[str]:
        """Initialize time extraction patterns."""
        return [
            r'(\d{1,2}):(\d{2})\s*[～〜\-–—]\s*(\d{1,2}):(\d{2})',  # 10:00～15:00
            r'(\d{1,2})時(\d{2})?分?\s*[～〜\-–—]\s*(\d{1,2})時(\d{2})?分?',  # 10時30分～15時
            r'午前(\d{1,2})時(\d{2})?分?\s*[～〜\-–—]\s*午後(\d{1,2})時(\d{2})?分?',  # 午前10時～午後3時
            r'(\d{1,2}):(\d{2})\s*開始',  # 10:00開始
            r'(\d{1,2})時(\d{2})?分?\s*開始',  # 10時30分開始
            r'午前(\d{1,2})時(\d{2})?分?',  # 午前10時
            r'午後(\d{1,2})時(\d{2})?分?',  # 午後3時
            r'(\d{1,2}):(\d{2})',  # 10:00
        ]
    
    def _init_price_patterns(self) -> List[str]:
        """Initialize pricing extraction patterns."""
        return [
            r'入場無料|無料|FREE|free',
            r'大人\s*(\d+)[円￥]',
            r'大人.*?(\d+)[円￥]',
            r'一般\s*(\d+)[円￥]',
            r'高校生以上\s*(\d+)[円￥]',
            r'子[ど供]?も\s*(\d+)[円￥]',
            r'小中学生\s*(\d+)[円￥]',
            r'シニア\s*(\d+)[円￥]',
            r'前売り?\s*(\d+)[円￥]',
            r'当日\s*(\d+)[円￥]',
            r'(\d+)[円￥]',
        ]
    
    def _init_contact_patterns(self) -> List[str]:
        """Initialize contact information patterns."""
        return [
            r'TEL[\s:：]*(\d{2,4}[\-\s]?\d{2,4}[\-\s]?\d{2,4})',
            r'電話[\s:：]*(\d{2,4}[\-\s]?\d{2,4}[\-\s]?\d{2,4})',
            r'tel[\s:：]*(\d{2,4}[\-\s]?\d{2,4}[\-\s]?\d{2,4})',
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'https?://[^\s\u3000]+',
            r'主催[\s:：]*([^\n\r\u3000]+)',
            r'問い?合わせ[\s:：]*([^\n\r\u3000]+)',
        ]
    
    def parse_enhanced_event(self, title: str, description: str = "", 
                           date_text: str = "", location_text: str = "",
                           source_url: str = "", source_site: str = "") -> EnhancedEvent:
        """Parse event information into enhanced format."""
        
        # Initialize enhanced event
        event = EnhancedEvent(
            title=title.strip(),
            description=description.strip(),
            source_url=source_url,
            source_site=source_site
        )
        
        # Parse timing information
        event.timing = self._parse_timing(date_text, description)
        
        # Parse location information
        event.location = self._parse_location(location_text, description, title)
        
        # Parse pricing information
        event.pricing = self._parse_pricing(description)
        
        # Parse contact information
        event.contact = self._parse_contact(description)
        
        # Determine category
        event.category = self._determine_category(title, description)
        
        # Extract tags
        event.tags = self._extract_tags(title, description)
        
        # Calculate confidence
        event.confidence_score = self._calculate_confidence(event)
        
        return event
    
    def _parse_timing(self, date_text: str, description: str) -> EventTiming:
        """Parse timing information from text."""
        from scrape import parse_date_range  # Use existing date parsing
        
        # Try to parse date range first
        try:
            start_date, end_date = parse_date_range(date_text)
        except:
            start_date = date.today()
            end_date = None
        
        timing = EventTiming(
            start_date=start_date,
            end_date=end_date,
            is_all_day=True
        )
        
        # Try to extract specific times
        combined_text = f"{date_text} {description}"
        start_time, end_time = self._extract_times(combined_text)
        
        if start_time:
            timing.start_time = start_time
            timing.is_all_day = False
        
        if end_time:
            timing.end_time = end_time
            timing.is_all_day = False
        
        # Calculate duration if both times available
        if start_time and end_time:
            start_dt = datetime.combine(start_date, start_time)
            end_dt = datetime.combine(end_date or start_date, end_time)
            if end_dt > start_dt:
                timing.duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
        
        return timing
    
    def _extract_times(self, text: str) -> Tuple[Optional[time], Optional[time]]:
        """Extract start and end times from text."""
        start_time = None
        end_time = None
        
        for pattern in self.time_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                
                if len(groups) >= 4 and groups[0] and groups[2]:  # Range pattern
                    try:
                        start_hour = int(groups[0])
                        start_min = int(groups[1]) if groups[1] else 0
                        end_hour = int(groups[2])
                        end_min = int(groups[3]) if groups[3] else 0
                        
                        start_time = time(start_hour, start_min)
                        end_time = time(end_hour, end_min)
                        break
                    except (ValueError, IndexError):
                        continue
                
                elif len(groups) >= 2 and groups[0]:  # Single time pattern
                    try:
                        hour = int(groups[0])
                        minute = int(groups[1]) if groups[1] else 0
                        start_time = time(hour, minute)
                        break
                    except (ValueError, IndexError):
                        continue
        
        return start_time, end_time
    
    def _parse_location(self, location_text: str, description: str, title: str) -> EventLocation:
        """Parse location information."""
        location = EventLocation()
        
        # Combine all text for location extraction
        combined_text = f"{location_text} {description} {title}"
        
        # Extract location name
        if location_text.strip():
            location.name = location_text.strip()
        else:
            # Try to extract from description or title
            for pattern, venue_type in self.location_patterns.items():
                if re.search(pattern, combined_text):
                    matches = re.findall(pattern, combined_text)
                    if matches:
                        location.name = matches[0]
                        location.venue_type = venue_type
                        break
        
        # Extract city information
        for pattern, city in self.location_patterns.items():
            if '市' in city or '町' in city or '村' in city:
                if re.search(pattern, combined_text):
                    location.city = city
                    break
        
        # Try to geocode if available
        if HAS_GEOCODER and location.name:
            try:
                full_address = f"{location.name} {location.city} 富山県"
                g = geocoder.google(full_address)
                if g.ok:
                    location.latitude = g.latlng[0]
                    location.longitude = g.latlng[1]
                    location.address = g.address
            except:
                pass  # Geocoding failed, continue without coordinates
        
        return location
    
    def _parse_pricing(self, description: str) -> EventPricing:
        """Parse pricing information from description."""
        pricing = EventPricing()
        
        # Check if free
        if re.search(r'入場無料|無料|FREE|free', description, re.IGNORECASE):
            pricing.is_free = True
            return pricing
        
        # Extract prices
        for pattern in self.price_patterns:
            matches = re.findall(pattern, description)
            if matches:
                if '大人' in pattern or '一般' in pattern:
                    try:
                        pricing.adult_price = int(matches[0])
                        pricing.is_free = False
                    except (ValueError, IndexError):
                        pass
                elif '子' in pattern or '小中学生' in pattern:
                    try:
                        pricing.child_price = int(matches[0])
                        pricing.is_free = False
                    except (ValueError, IndexError):
                        pass
                elif 'シニア' in pattern:
                    try:
                        pricing.senior_price = int(matches[0])
                        pricing.is_free = False
                    except (ValueError, IndexError):
                        pass
                elif '前売' in pattern:
                    try:
                        pricing.advance_price = int(matches[0])
                        pricing.is_free = False
                    except (ValueError, IndexError):
                        pass
        
        return pricing
    
    def _parse_contact(self, description: str) -> EventContact:
        """Parse contact information from description."""
        contact = EventContact()
        
        for pattern in self.contact_patterns:
            matches = re.findall(pattern, description)
            if matches:
                if 'TEL' in pattern or '電話' in pattern or 'tel' in pattern:
                    contact.phone = matches[0]
                elif '@' in pattern:
                    contact.email = matches[0]
                elif 'http' in pattern:
                    contact.website = matches[0]
                elif '主催' in pattern:
                    contact.organizer = matches[0]
        
        return contact
    
    def _determine_category(self, title: str, description: str) -> EventCategory:
        """Determine event category based on content."""
        combined_text = f"{title} {description}".lower()
        
        category_scores = {}
        
        for category, patterns in self.category_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, combined_text))
                score += matches
            category_scores[category] = score
        
        # Return category with highest score, or OTHER if no matches
        if category_scores and max(category_scores.values()) > 0:
            return max(category_scores, key=category_scores.get)
        
        return EventCategory.OTHER
    
    def _extract_tags(self, title: str, description: str) -> List[str]:
        """Extract relevant tags from content."""
        tags = []
        combined_text = f"{title} {description}"
        
        # Common event-related tags
        tag_patterns = {
            'outdoor': r'屋外|野外|アウトドア|outdoor',
            'indoor': r'屋内|室内|インドア|indoor|ホール',
            'family': r'家族|ファミリー|親子|family|子供',
            'adult': r'大人|成人|adult|18歳以上',
            'beginner': r'初心者|ビギナー|beginner|初級',
            'advanced': r'上級|アドバンス|advanced|プロ',
            'seasonal': r'季節|春|夏|秋|冬|seasonal',
            'traditional': r'伝統|和風|traditional|古典',
            'modern': r'現代|モダン|modern|新しい',
            'limited': r'限定|special|期間限定|数量限定'
        }
        
        for tag, pattern in tag_patterns.items():
            if re.search(pattern, combined_text, re.IGNORECASE):
                tags.append(tag)
        
        return tags
    
    def _calculate_confidence(self, event: EnhancedEvent) -> float:
        """Calculate confidence score for parsed data."""
        confidence = 0.0
        
        # Title confidence
        if event.title and len(event.title.strip()) > 5:
            confidence += 25
        
        # Timing confidence
        if event.timing and event.timing.start_date:
            confidence += 20
            if event.timing.start_time:
                confidence += 10
        
        # Location confidence
        if event.location and event.location.name:
            confidence += 20
            if event.location.city:
                confidence += 10
        
        # Content confidence
        if event.description and len(event.description) > 20:
            confidence += 15
        
        return min(confidence, 100.0)


def convert_legacy_to_enhanced(legacy_events: List[Dict]) -> List[EnhancedEvent]:
    """Convert legacy event format to enhanced format."""
    parser = EnhancedEventParser()
    enhanced_events = []
    
    for legacy_event in legacy_events:
        # Extract legacy fields
        title = legacy_event.get('title', '')
        start_date = legacy_event.get('start', date.today())
        end_date = legacy_event.get('end')
        location = legacy_event.get('location', '')
        url = legacy_event.get('url', '')
        site = legacy_event.get('site', '')
        
        # Create enhanced event
        enhanced = EnhancedEvent(
            title=title,
            source_url=url,
            source_site=site
        )
        
        # Set timing
        enhanced.timing = EventTiming(
            start_date=start_date,
            end_date=end_date,
            is_all_day=True
        )
        
        # Set location
        enhanced.location = EventLocation(name=location)
        
        # Determine category
        enhanced.category = parser._determine_category(title, "")
        
        # Initialize other fields
        enhanced.pricing = EventPricing()
        enhanced.contact = EventContact()
        
        enhanced_events.append(enhanced)
    
    return enhanced_events


if __name__ == "__main__":
    # Test the enhanced parser
    parser = EnhancedEventParser()
    
    # Test event
    test_event = parser.parse_enhanced_event(
        title="第71回北日本新聞納涼花火高岡会場",
        description="富山県高岡市で開催される夏の花火大会。午後7時30分開始、入場無料。お問い合わせ: 076-123-4567",
        date_text="2025年8月4日",
        location_text="高岡市中心部",
        source_url="https://example.com/event",
        source_site="info-toyama"
    )
    
    print(f"Enhanced Event: {test_event.title}")
    print(f"Category: {test_event.category.value}")
    print(f"Quality Score: {test_event.quality_score}")
    print(f"Quality Level: {test_event.quality_level.value}")
    print(f"Start Time: {test_event.timing.start_time}")
    print(f"Is Free: {test_event.pricing.is_free}")
    print(f"Location: {test_event.location.name}, {test_event.location.city}")
    print(f"Phone: {test_event.contact.phone}")