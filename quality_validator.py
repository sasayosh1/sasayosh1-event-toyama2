"""Event Quality Validation System

This module provides comprehensive event data quality validation including:
- Data completeness and integrity checks
- Anomaly detection for suspicious events
- Reliability scoring based on multiple factors
- Automatic correction suggestions
- Quality improvement recommendations
- Comprehensive quality reporting
"""

from __future__ import annotations

import re
import json
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import statistics
import hashlib

from enhanced_parser import EnhancedEvent, EventTiming, EventLocation, EventCategory, EventQuality


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    CRITICAL = "critical"    # Data corruption, invalid dates
    HIGH = "high"           # Missing critical information
    MEDIUM = "medium"       # Incomplete information
    LOW = "low"            # Minor formatting issues
    INFO = "info"          # Informational notices


class ValidationCategory(Enum):
    """Categories of validation issues."""
    DATA_INTEGRITY = "data_integrity"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    ACCURACY = "accuracy"
    FORMATTING = "formatting"
    BUSINESS_LOGIC = "business_logic"
    SUSPICIOUS_DATA = "suspicious_data"


@dataclass
class ValidationIssue:
    """Represents a data quality issue."""
    event_id: str
    event_title: str
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    field: str
    current_value: Any
    suggested_fix: Optional[str] = None
    auto_fixable: bool = False
    confidence: float = 1.0  # Confidence in the issue detection


@dataclass
class QualityMetrics:
    """Quality metrics for an event or dataset."""
    completeness_score: float  # 0-100%
    accuracy_score: float      # 0-100%
    consistency_score: float   # 0-100%
    reliability_score: float   # 0-100%
    overall_score: float       # 0-100%
    issues_count: Dict[ValidationSeverity, int] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Results of quality validation process."""
    total_events: int
    validated_events: int
    issues: List[ValidationIssue]
    metrics: QualityMetrics
    suggestions: List[str]
    auto_fixes_applied: int = 0
    processing_time: float = 0.0


class DataValidator:
    """Core data validation engine."""
    
    def __init__(self):
        """Initialize validator with rules and patterns."""
        self.date_range_years = 5  # Valid event date range
        self.max_title_length = 200
        self.min_title_length = 3
        self.suspicious_patterns = self._init_suspicious_patterns()
        self.common_typos = self._init_common_typos()
        self.valid_prefectures = self._init_valid_prefectures()
        
    def _init_suspicious_patterns(self) -> List[Tuple[str, str]]:
        """Initialize patterns that indicate suspicious data."""
        return [
            (r'test|テスト|TEST', "テストデータの可能性"),
            (r'sample|サンプル|SAMPLE', "サンプルデータの可能性"),
            (r'dummy|ダミー|DUMMY', "ダミーデータの可能性"),
            (r'example|例|EXAMPLE', "例示データの可能性"),
            (r'^\d+$', "数字のみのタイトル"),
            (r'^[a-zA-Z]+$', "英字のみのタイトル"),
            (r'(.)\1{5,}', "同一文字の連続"),
            (r'未定|未確定|TBD|TBA', "未確定情報"),
        ]
    
    def _init_common_typos(self) -> Dict[str, str]:
        """Initialize common typos and corrections."""
        return {
            'まつり': 'まつり',
            'ﾏﾂﾘ': 'まつり',
            'マツリ': 'まつり',
            'Festival': 'フェスティバル',
            'festival': 'フェスティバル',
            '富山県富山県': '富山県',
            '富山市富山市': '富山市',
            'ー': 'ー',  # Full-width vs half-width
            '－': 'ー',
        }
    
    def _init_valid_prefectures(self) -> Set[str]:
        """Initialize valid prefecture names."""
        return {
            '富山県', '富山', '石川県', '石川', '福井県', '福井',
            '新潟県', '新潟', '長野県', '長野', '岐阜県', '岐阜'
        }
    
    def validate_event(self, event: EnhancedEvent) -> List[ValidationIssue]:
        """Validate a single event and return issues."""
        issues = []
        event_id = event.hash_id or f"event_{id(event)}"
        
        # Data integrity checks
        issues.extend(self._validate_data_integrity(event, event_id))
        
        # Completeness checks
        issues.extend(self._validate_completeness(event, event_id))
        
        # Consistency checks
        issues.extend(self._validate_consistency(event, event_id))
        
        # Accuracy checks
        issues.extend(self._validate_accuracy(event, event_id))
        
        # Format checks
        issues.extend(self._validate_formatting(event, event_id))
        
        # Business logic checks
        issues.extend(self._validate_business_logic(event, event_id))
        
        # Suspicious data checks
        issues.extend(self._validate_suspicious_data(event, event_id))
        
        return issues
    
    def _validate_data_integrity(self, event: EnhancedEvent, event_id: str) -> List[ValidationIssue]:
        """Validate basic data integrity."""
        issues = []
        
        # Required fields
        if not event.title or not event.title.strip():
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title or "No Title",
                category=ValidationCategory.DATA_INTEGRITY,
                severity=ValidationSeverity.CRITICAL,
                message="タイトルが空です",
                field="title",
                current_value=event.title,
                suggested_fix="有効なタイトルを設定してください",
                auto_fixable=False
            ))
        
        # Date validation
        if event.timing:
            today = date.today()
            min_date = today - timedelta(days=30)  # Allow recent past events
            max_date = today + timedelta(days=365 * self.date_range_years)
            
            if event.timing.start_date < min_date:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.DATA_INTEGRITY,
                    severity=ValidationSeverity.HIGH,
                    message=f"開始日が過去すぎます: {event.timing.start_date}",
                    field="timing.start_date",
                    current_value=event.timing.start_date,
                    suggested_fix="現在または近い将来の日付に修正してください"
                ))
            
            if event.timing.start_date > max_date:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.DATA_INTEGRITY,
                    severity=ValidationSeverity.MEDIUM,
                    message=f"開始日が未来すぎます: {event.timing.start_date}",
                    field="timing.start_date",
                    current_value=event.timing.start_date,
                    suggested_fix="より近い将来の日付に修正してください"
                ))
            
            # End date validation
            if event.timing.end_date and event.timing.end_date < event.timing.start_date:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.DATA_INTEGRITY,
                    severity=ValidationSeverity.CRITICAL,
                    message="終了日が開始日より前です",
                    field="timing.end_date",
                    current_value=event.timing.end_date,
                    suggested_fix="終了日を開始日以降に設定してください",
                    auto_fixable=True
                ))
        
        return issues
    
    def _validate_completeness(self, event: EnhancedEvent, event_id: str) -> List[ValidationIssue]:
        """Validate data completeness."""
        issues = []
        
        # Check for missing critical information
        if not event.timing:
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.COMPLETENESS,
                severity=ValidationSeverity.HIGH,
                message="日時情報が不足しています",
                field="timing",
                current_value=None,
                suggested_fix="開始日時を設定してください"
            ))
        
        if not event.location or not event.location.name:
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.COMPLETENESS,
                severity=ValidationSeverity.HIGH,
                message="開催場所が不足しています",
                field="location.name",
                current_value=event.location.name if event.location else None,
                suggested_fix="開催場所を設定してください"
            ))
        
        # Check for missing optional but important information
        if not event.description or len(event.description.strip()) < 10:
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.COMPLETENESS,
                severity=ValidationSeverity.MEDIUM,
                message="説明文が不足または短すぎます",
                field="description",
                current_value=event.description,
                suggested_fix="詳細な説明を追加してください"
            ))
        
        if not event.source_url or not event.source_url.startswith('http'):
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.COMPLETENESS,
                severity=ValidationSeverity.LOW,
                message="有効なソースURLが設定されていません",
                field="source_url",
                current_value=event.source_url,
                suggested_fix="正しいURLを設定してください"
            ))
        
        return issues
    
    def _validate_consistency(self, event: EnhancedEvent, event_id: str) -> List[ValidationIssue]:
        """Validate data consistency."""
        issues = []
        
        # Check consistency between title and category
        if event.category == EventCategory.FESTIVAL:
            festival_patterns = [r'まつり', r'祭り', r'festival', r'フェスティバル']
            if not any(re.search(pattern, event.title, re.IGNORECASE) for pattern in festival_patterns):
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.CONSISTENCY,
                    severity=ValidationSeverity.LOW,
                    message="タイトルとカテゴリー(FESTIVAL)が一致していません",
                    field="category",
                    current_value=event.category.value,
                    suggested_fix="カテゴリーを見直すか、タイトルを確認してください"
                ))
        
        # Check location consistency
        if event.location and event.location.city:
            city_in_title = any(city in event.title for city in ['富山', '高岡', '魚津', '氷見', '黒部'])
            location_has_city = any(city in event.location.name for city in ['富山', '高岡', '魚津', '氷見', '黒部'])
            
            if city_in_title and location_has_city:
                # Extract cities from both
                title_cities = [city for city in ['富山', '高岡', '魚津', '氷見', '黒部'] if city in event.title]
                location_cities = [city for city in ['富山', '高岡', '魚津', '氷見', '黒部'] if city in event.location.name]
                
                if title_cities and location_cities and title_cities[0] != location_cities[0]:
                    issues.append(ValidationIssue(
                        event_id=event_id,
                        event_title=event.title,
                        category=ValidationCategory.CONSISTENCY,
                        severity=ValidationSeverity.MEDIUM,
                        message="タイトルと開催地の都市が一致していません",
                        field="location.city",
                        current_value=event.location.city,
                        suggested_fix="タイトルと開催地の都市を統一してください"
                    ))
        
        # Check time consistency
        if event.timing and event.timing.start_time and event.timing.end_time:
            if event.timing.start_time >= event.timing.end_time:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.CONSISTENCY,
                    severity=ValidationSeverity.HIGH,
                    message="開始時刻が終了時刻以降になっています",
                    field="timing.start_time",
                    current_value=event.timing.start_time,
                    suggested_fix="開始時刻を終了時刻より前に設定してください",
                    auto_fixable=True
                ))
        
        return issues
    
    def _validate_accuracy(self, event: EnhancedEvent, event_id: str) -> List[ValidationIssue]:
        """Validate data accuracy."""
        issues = []
        
        # Check for common typos in title
        corrected_title = event.title
        for typo, correction in self.common_typos.items():
            if typo in corrected_title:
                corrected_title = corrected_title.replace(typo, correction)
        
        if corrected_title != event.title:
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.ACCURACY,
                severity=ValidationSeverity.LOW,
                message="タイトルに一般的な誤字が含まれている可能性があります",
                field="title",
                current_value=event.title,
                suggested_fix=f"修正候補: {corrected_title}",
                auto_fixable=True
            ))
        
        # Check for reasonable pricing
        if event.pricing and not event.pricing.is_free:
            if event.pricing.adult_price and event.pricing.adult_price > 50000:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.ACCURACY,
                    severity=ValidationSeverity.MEDIUM,
                    message="料金が異常に高額です",
                    field="pricing.adult_price",
                    current_value=event.pricing.adult_price,
                    suggested_fix="料金を確認してください"
                ))
            
            if event.pricing.adult_price and event.pricing.adult_price < 0:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.ACCURACY,
                    severity=ValidationSeverity.HIGH,
                    message="料金が負の値です",
                    field="pricing.adult_price",
                    current_value=event.pricing.adult_price,
                    suggested_fix="正の値に修正してください",
                    auto_fixable=True
                ))
        
        return issues
    
    def _validate_formatting(self, event: EnhancedEvent, event_id: str) -> List[ValidationIssue]:
        """Validate data formatting."""
        issues = []
        
        # Title length validation
        if len(event.title) > self.max_title_length:
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.FORMATTING,
                severity=ValidationSeverity.MEDIUM,
                message=f"タイトルが長すぎます ({len(event.title)}文字)",
                field="title",
                current_value=event.title,
                suggested_fix=f"{self.max_title_length}文字以下に短縮してください"
            ))
        
        if len(event.title) < self.min_title_length:
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.FORMATTING,
                severity=ValidationSeverity.HIGH,
                message=f"タイトルが短すぎます ({len(event.title)}文字)",
                field="title",
                current_value=event.title,
                suggested_fix=f"{self.min_title_length}文字以上にしてください"
            ))
        
        # Check for excessive whitespace
        if re.search(r'\s{3,}', event.title):
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.FORMATTING,
                severity=ValidationSeverity.LOW,
                message="タイトルに余分な空白があります",
                field="title",
                current_value=event.title,
                suggested_fix="余分な空白を削除してください",
                auto_fixable=True
            ))
        
        # URL format validation
        if event.source_url and not re.match(r'https?://.+', event.source_url):
            issues.append(ValidationIssue(
                event_id=event_id,
                event_title=event.title,
                category=ValidationCategory.FORMATTING,
                severity=ValidationSeverity.MEDIUM,
                message="URLの形式が正しくありません",
                field="source_url",
                current_value=event.source_url,
                suggested_fix="http://またはhttps://で始まるURLにしてください"
            ))
        
        return issues
    
    def _validate_business_logic(self, event: EnhancedEvent, event_id: str) -> List[ValidationIssue]:
        """Validate business logic rules."""
        issues = []
        
        # Check for reasonable event duration
        if event.timing and event.timing.start_date and event.timing.end_date:
            duration_days = (event.timing.end_date - event.timing.start_date).days
            
            if duration_days > 365:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.BUSINESS_LOGIC,
                    severity=ValidationSeverity.MEDIUM,
                    message=f"イベント期間が異常に長いです ({duration_days}日)",
                    field="timing.end_date",
                    current_value=event.timing.end_date,
                    suggested_fix="期間を確認してください"
                ))
            
            if duration_days < 0:
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.BUSINESS_LOGIC,
                    severity=ValidationSeverity.CRITICAL,
                    message="終了日が開始日より前です",
                    field="timing.end_date",
                    current_value=event.timing.end_date,
                    suggested_fix="終了日を開始日以降に設定してください",
                    auto_fixable=True
                ))
        
        # Check for weekend vs weekday logic
        if event.timing and event.timing.start_date:
            weekday = event.timing.start_date.weekday()
            
            # Festivals usually happen on weekends
            if event.category == EventCategory.FESTIVAL and weekday < 5:  # Monday-Friday
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.BUSINESS_LOGIC,
                    severity=ValidationSeverity.INFO,
                    message="祭りイベントが平日に開催されます",
                    field="timing.start_date",
                    current_value=event.timing.start_date,
                    suggested_fix="日程を確認してください"
                ))
        
        return issues
    
    def _validate_suspicious_data(self, event: EnhancedEvent, event_id: str) -> List[ValidationIssue]:
        """Validate for suspicious or test data."""
        issues = []
        
        # Check title for suspicious patterns
        for pattern, description in self.suspicious_patterns:
            if re.search(pattern, event.title, re.IGNORECASE):
                issues.append(ValidationIssue(
                    event_id=event_id,
                    event_title=event.title,
                    category=ValidationCategory.SUSPICIOUS_DATA,
                    severity=ValidationSeverity.HIGH,
                    message=f"疑わしいデータ: {description}",
                    field="title",
                    current_value=event.title,
                    suggested_fix="実際のイベントデータかどうか確認してください"
                ))
        
        # Check for repeated events (same title, different dates)
        # This would need to be implemented at the dataset level
        
        return issues


class QualityAnalyzer:
    """Analyzes overall quality metrics for events."""
    
    def calculate_event_metrics(self, event: EnhancedEvent, issues: List[ValidationIssue]) -> QualityMetrics:
        """Calculate quality metrics for a single event."""
        # Count issues by severity
        issue_counts = {severity: 0 for severity in ValidationSeverity}
        for issue in issues:
            issue_counts[issue.severity] += 1
        
        # Calculate scores (0-100)
        completeness = self._calculate_completeness_score(event)
        accuracy = self._calculate_accuracy_score(event, issues)
        consistency = self._calculate_consistency_score(event, issues)
        reliability = self._calculate_reliability_score(event, issues)
        
        # Overall score (weighted average)
        overall = (
            completeness * 0.3 + 
            accuracy * 0.25 + 
            consistency * 0.25 + 
            reliability * 0.2
        )
        
        return QualityMetrics(
            completeness_score=completeness,
            accuracy_score=accuracy,
            consistency_score=consistency,
            reliability_score=reliability,
            overall_score=overall,
            issues_count=issue_counts
        )
    
    def _calculate_completeness_score(self, event: EnhancedEvent) -> float:
        """Calculate completeness score based on available fields."""
        total_fields = 10  # Total possible important fields
        filled_fields = 0
        
        if event.title and event.title.strip():
            filled_fields += 1
        if event.description and len(event.description.strip()) > 10:
            filled_fields += 1
        if event.timing and event.timing.start_date:
            filled_fields += 1
        if event.timing and event.timing.start_time:
            filled_fields += 1
        if event.location and event.location.name:
            filled_fields += 1
        if event.location and event.location.address:
            filled_fields += 1
        if event.contact and (event.contact.phone or event.contact.email):
            filled_fields += 1
        if event.pricing:
            filled_fields += 1
        if event.source_url and event.source_url.startswith('http'):
            filled_fields += 1
        if event.category != EventCategory.OTHER:
            filled_fields += 1
        
        return (filled_fields / total_fields) * 100
    
    def _calculate_accuracy_score(self, event: EnhancedEvent, issues: List[ValidationIssue]) -> float:
        """Calculate accuracy score based on validation issues."""
        accuracy_issues = [i for i in issues if i.category == ValidationCategory.ACCURACY]
        critical_issues = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
        
        # Start with perfect score and deduct for issues
        score = 100.0
        score -= len(critical_issues) * 30  # Critical issues heavily penalized
        score -= len(accuracy_issues) * 15  # Accuracy issues moderately penalized
        
        return max(0.0, score)
    
    def _calculate_consistency_score(self, event: EnhancedEvent, issues: List[ValidationIssue]) -> float:
        """Calculate consistency score."""
        consistency_issues = [i for i in issues if i.category == ValidationCategory.CONSISTENCY]
        
        score = 100.0
        score -= len(consistency_issues) * 20
        
        return max(0.0, score)
    
    def _calculate_reliability_score(self, event: EnhancedEvent, issues: List[ValidationIssue]) -> float:
        """Calculate reliability score based on source and overall quality."""
        score = 100.0
        
        # Deduct for suspicious data
        suspicious_issues = [i for i in issues if i.category == ValidationCategory.SUSPICIOUS_DATA]
        score -= len(suspicious_issues) * 25
        
        # Boost for good source information
        if event.source_url and event.source_url.startswith('https'):
            score += 5
        
        # Boost for complete contact information
        if event.contact and event.contact.phone and event.contact.email:
            score += 5
        
        return min(100.0, max(0.0, score))


class EventQualityValidator:
    """Main quality validation system."""
    
    def __init__(self, auto_fix: bool = False):
        """Initialize validator."""
        self.validator = DataValidator()
        self.analyzer = QualityAnalyzer()
        self.auto_fix = auto_fix
        
    def validate_events(self, events: List[EnhancedEvent]) -> ValidationResult:
        """Validate a list of events and return comprehensive results."""
        import time
        start_time = time.time()
        
        all_issues = []
        all_metrics = []
        auto_fixes_applied = 0
        
        for event in events:
            # Validate individual event
            issues = self.validator.validate_event(event)
            
            # Apply auto-fixes if enabled
            if self.auto_fix:
                fixes_applied = self._apply_auto_fixes(event, issues)
                auto_fixes_applied += fixes_applied
                
                # Re-validate after fixes
                issues = self.validator.validate_event(event)
            
            # Calculate metrics
            metrics = self.analyzer.calculate_event_metrics(event, issues)
            
            all_issues.extend(issues)
            all_metrics.append(metrics)
        
        # Calculate overall metrics
        overall_metrics = self._calculate_overall_metrics(all_metrics)
        
        # Generate suggestions
        suggestions = self._generate_suggestions(all_issues, overall_metrics)
        
        processing_time = time.time() - start_time
        
        return ValidationResult(
            total_events=len(events),
            validated_events=len(events),
            issues=all_issues,
            metrics=overall_metrics,
            suggestions=suggestions,
            auto_fixes_applied=auto_fixes_applied,
            processing_time=processing_time
        )
    
    def _apply_auto_fixes(self, event: EnhancedEvent, issues: List[ValidationIssue]) -> int:
        """Apply automatic fixes to an event."""
        fixes_applied = 0
        
        for issue in issues:
            if not issue.auto_fixable:
                continue
                
            if issue.field == "title" and "余分な空白" in issue.message:
                event.title = re.sub(r'\s+', ' ', event.title.strip())
                fixes_applied += 1
                
            elif issue.field == "timing.end_date" and issue.severity == ValidationSeverity.CRITICAL:
                # Fix invalid end date
                if event.timing and event.timing.end_date and event.timing.end_date < event.timing.start_date:
                    event.timing.end_date = event.timing.start_date
                    fixes_applied += 1
                    
            elif issue.field == "timing.start_time" and "開始時刻が終了時刻以降" in issue.message:
                # Swap start and end times if they're reversed
                if event.timing and event.timing.start_time and event.timing.end_time:
                    if event.timing.start_time >= event.timing.end_time:
                        event.timing.start_time, event.timing.end_time = event.timing.end_time, event.timing.start_time
                        fixes_applied += 1
                        
            elif issue.field == "pricing.adult_price" and "負の値" in issue.message:
                # Fix negative pricing
                if event.pricing and event.pricing.adult_price and event.pricing.adult_price < 0:
                    event.pricing.adult_price = abs(event.pricing.adult_price)
                    fixes_applied += 1
        
        return fixes_applied
    
    def _calculate_overall_metrics(self, metrics_list: List[QualityMetrics]) -> QualityMetrics:
        """Calculate overall metrics from individual event metrics."""
        if not metrics_list:
            return QualityMetrics(0, 0, 0, 0, 0)
        
        # Calculate averages
        completeness = statistics.mean(m.completeness_score for m in metrics_list)
        accuracy = statistics.mean(m.accuracy_score for m in metrics_list)
        consistency = statistics.mean(m.consistency_score for m in metrics_list)
        reliability = statistics.mean(m.reliability_score for m in metrics_list)
        overall = statistics.mean(m.overall_score for m in metrics_list)
        
        # Aggregate issue counts
        total_issues = {severity: 0 for severity in ValidationSeverity}
        for metrics in metrics_list:
            for severity, count in metrics.issues_count.items():
                total_issues[severity] += count
        
        return QualityMetrics(
            completeness_score=completeness,
            accuracy_score=accuracy,
            consistency_score=consistency,
            reliability_score=reliability,
            overall_score=overall,
            issues_count=total_issues
        )
    
    def _generate_suggestions(self, issues: List[ValidationIssue], 
                            metrics: QualityMetrics) -> List[str]:
        """Generate improvement suggestions based on validation results."""
        suggestions = []
        
        # Analyze issue patterns
        issue_by_category = {}
        for issue in issues:
            category = issue.category
            if category not in issue_by_category:
                issue_by_category[category] = []
            issue_by_category[category].append(issue)
        
        # Critical issues first
        critical_count = metrics.issues_count.get(ValidationSeverity.CRITICAL, 0)
        if critical_count > 0:
            suggestions.append(f"緊急対応が必要な問題が{critical_count}件あります。データ整合性を確認してください。")
        
        # Category-specific suggestions
        if ValidationCategory.COMPLETENESS in issue_by_category:
            count = len(issue_by_category[ValidationCategory.COMPLETENESS])
            suggestions.append(f"データの不完全性が{count}件検出されました。欠損情報の補完を検討してください。")
        
        if ValidationCategory.SUSPICIOUS_DATA in issue_by_category:
            count = len(issue_by_category[ValidationCategory.SUSPICIOUS_DATA])
            suggestions.append(f"疑わしいデータが{count}件検出されました。テストデータが混入していないか確認してください。")
        
        # Quality score based suggestions
        if metrics.overall_score < 70:
            suggestions.append("全体的なデータ品質が低いです。包括的な見直しを推奨します。")
        elif metrics.overall_score < 85:
            suggestions.append("データ品質は許容範囲ですが、改善の余地があります。")
        
        if metrics.completeness_score < 60:
            suggestions.append("データの完全性が不足しています。必須項目の入力を強化してください。")
        
        return suggestions
    
    def generate_quality_report(self, result: ValidationResult) -> Dict[str, Any]:
        """Generate comprehensive quality report."""
        # Issue distribution
        issues_by_category = {}
        issues_by_severity = {}
        
        for issue in result.issues:
            category = issue.category.value
            severity = issue.severity.value
            
            issues_by_category[category] = issues_by_category.get(category, 0) + 1
            issues_by_severity[severity] = issues_by_severity.get(severity, 0) + 1
        
        # Quality grade
        score = result.metrics.overall_score
        if score >= 90:
            grade = "A"
        elif score >= 80:
            grade = "B"
        elif score >= 70:
            grade = "C"
        elif score >= 60:
            grade = "D"
        else:
            grade = "F"
        
        return {
            "summary": {
                "total_events": result.total_events,
                "total_issues": len(result.issues),
                "auto_fixes_applied": result.auto_fixes_applied,
                "overall_score": result.metrics.overall_score,
                "quality_grade": grade,
                "processing_time": result.processing_time
            },
            "metrics": {
                "completeness": result.metrics.completeness_score,
                "accuracy": result.metrics.accuracy_score,
                "consistency": result.metrics.consistency_score,
                "reliability": result.metrics.reliability_score
            },
            "issues": {
                "by_category": issues_by_category,
                "by_severity": issues_by_severity,
                "critical_issues": [
                    {
                        "event": issue.event_title,
                        "message": issue.message,
                        "field": issue.field
                    }
                    for issue in result.issues
                    if issue.severity == ValidationSeverity.CRITICAL
                ]
            },
            "suggestions": result.suggestions
        }


if __name__ == "__main__":
    # Test the quality validator
    from enhanced_parser import EnhancedEvent, EventTiming, EventLocation, EventCategory
    
    # Create test events with various quality issues
    events = [
        # Good quality event
        EnhancedEvent(
            title="高岡七夕まつり",
            description="富山県高岡市で開催される伝統的な七夕祭り",
            timing=EventTiming(start_date=date(2025, 7, 7)),
            location=EventLocation(name="高岡市中心部", city="高岡市"),
            category=EventCategory.FESTIVAL,
            source_url="https://example.com/tanabata"
        ),
        
        # Poor quality event
        EnhancedEvent(
            title="テスト",  # Suspicious title
            description="",  # Empty description
            timing=EventTiming(start_date=date(2020, 1, 1)),  # Past date
            location=EventLocation(name="", city=""),  # Empty location
            category=EventCategory.OTHER,
            source_url="invalid-url"  # Invalid URL
        ),
        
        # Event with inconsistent data
        EnhancedEvent(
            title="富山花火大会",
            timing=EventTiming(
                start_date=date(2025, 8, 15),
                start_time=time(20, 0),
                end_time=time(19, 0)  # End before start
            ),
            location=EventLocation(name="高岡市民会館", city="魚津市"),  # Inconsistent city
            category=EventCategory.SPORTS  # Wrong category
        )
    ]
    
    validator = EventQualityValidator(auto_fix=True)
    result = validator.validate_events(events)
    
    print(f"Quality Validation Results:")
    print(f"Total events: {result.total_events}")
    print(f"Issues found: {len(result.issues)}")
    print(f"Auto-fixes applied: {result.auto_fixes_applied}")
    print(f"Overall quality score: {result.metrics.overall_score:.1f}")
    
    # Show some issues
    for issue in result.issues[:5]:  # Show first 5 issues
        print(f"\nIssue: {issue.severity.value} - {issue.message}")
        print(f"  Event: {issue.event_title}")
        print(f"  Field: {issue.field}")
        if issue.suggested_fix:
            print(f"  Fix: {issue.suggested_fix}")
    
    # Generate report
    report = validator.generate_quality_report(result)
    print(f"\nQuality Report:")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))