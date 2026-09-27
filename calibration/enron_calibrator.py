"""
Enron-Calibrated Behavioral Exhaust Generator.

Maps Enron email corpus patterns to behavioral exhaust parameters,
giving the simulation realistic "texture" based on actual organizational
communication dynamics from a large enterprise.

Key Calibration Dimensions:
1. Question frequency → Help request rates
2. Instruction patterns → Knowledge transfer volume
3. Exception mentions → Edge case documentation rate
4. Approval chains → Escalation patterns
5. Seniority communication → Mentorship signals

This replaces synthetic/guessed behavioral parameters with empirically-derived
values from real organizational communication.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import Counter
import re

from calibration.enron_loader import (
    EnronLoader,
    KnowledgeTransferPattern,
    EnronOrgProfile,
)


@dataclass
class BehavioralExhaustParameters:
    """
    Parameters for behavioral exhaust generation, calibrated from Enron corpus.

    These parameters control how the simulation generates behavioral exhaust
    that reflects realistic organizational communication patterns.
    """

    # Question/Help patterns
    question_rate: float = 0.0  # Fraction of communications that are questions
    help_request_keywords: List[str] = field(default_factory=list)

    # Knowledge transfer patterns
    instruction_rate: float = 0.0  # Fraction with explicit instructions
    instruction_keywords: List[str] = field(default_factory=list)

    # Exception handling patterns
    exception_rate: float = 0.0  # Fraction mentioning exceptions/edge cases
    exception_keywords: List[str] = field(default_factory=list)

    # Approval/escalation patterns
    approval_rate: float = 0.0  # Fraction involving approval chains
    escalation_keywords: List[str] = field(default_factory=list)

    # Seniority dynamics
    senior_to_junior_ratio: float = 0.5  # How often seniors communicate to juniors
    mentorship_indicators: List[str] = field(default_factory=list)

    # Communication style
    avg_message_length: int = 100  # Characters
    formal_vs_informal: float = 0.5  # 0 = very informal, 1 = very formal

    # Entity references
    common_entity_types: List[str] = field(default_factory=list)
    entity_mention_rate: float = 0.0


@dataclass
class EnronCalibrationResult:
    """Results from calibrating against Enron corpus."""
    parameters: BehavioralExhaustParameters
    sample_size: int
    pattern_counts: Dict[str, int]
    confidence: float  # How confident we are in these parameters
    calibration_notes: List[str] = field(default_factory=list)


class EnronCalibrator:
    """
    Calibrates behavioral exhaust parameters from Enron email patterns.

    Usage:
        loader = EnronLoader("path/to/enron.csv")
        loader.load()

        calibrator = EnronCalibrator(loader)
        result = calibrator.calibrate()

        # Use result.parameters in behavioral exhaust generator
    """

    def __init__(self, loader: EnronLoader):
        """
        Initialize calibrator with loaded Enron data.

        Args:
            loader: EnronLoader instance with emails already loaded
        """
        self.loader = loader
        self.patterns: List[KnowledgeTransferPattern] = []

    def calibrate(self) -> EnronCalibrationResult:
        """
        Extract calibration parameters from loaded Enron corpus.

        Returns:
            EnronCalibrationResult with derived parameters
        """
        # Extract patterns if not already done
        if not self.patterns:
            self.patterns = self.loader.extract_knowledge_patterns()

        params = BehavioralExhaustParameters()
        notes: List[str] = []

        total_emails = len(self.loader.emails)
        emails_with_body = len([e for e in self.loader.emails if e.body])

        if emails_with_body == 0:
            return EnronCalibrationResult(
                parameters=params,
                sample_size=0,
                pattern_counts={},
                confidence=0.0,
                calibration_notes=["No emails with body content found"],
            )

        # Count pattern types
        pattern_counts = Counter(p.pattern_type for p in self.patterns)

        # Calculate rates (normalized to emails with bodies)
        params.question_rate = pattern_counts.get("question_answer", 0) / emails_with_body
        params.instruction_rate = pattern_counts.get("instruction", 0) / emails_with_body
        params.exception_rate = pattern_counts.get("exception_warning", 0) / emails_with_body
        params.approval_rate = pattern_counts.get("approval_chain", 0) / emails_with_body

        notes.append(f"Calibrated from {emails_with_body} emails with body content")
        notes.append(f"Found {len(self.patterns)} knowledge transfer patterns")

        # Extract common keywords from patterns
        params.help_request_keywords = self._extract_keywords(
            [p for p in self.patterns if p.has_question],
            ["can you", "could you", "please", "help", "need", "how do"]
        )

        params.instruction_keywords = self._extract_keywords(
            [p for p in self.patterns if p.has_instruction],
            ["always", "never", "make sure", "remember", "must", "should"]
        )

        params.exception_keywords = self._extract_keywords(
            [p for p in self.patterns if p.has_exception],
            ["except", "unless", "but not", "only if", "special case"]
        )

        params.escalation_keywords = self._extract_keywords(
            [p for p in self.patterns if p.has_approval_chain],
            ["cc", "copy", "approval", "sign off", "authorize"]
        )

        # Calculate seniority dynamics
        senior_junior_exchanges = self.loader.get_senior_junior_exchanges()
        if senior_junior_exchanges:
            params.senior_to_junior_ratio = len(senior_junior_exchanges) / emails_with_body
            notes.append(f"Found {len(senior_junior_exchanges)} senior→junior exchanges")

        # Extract mentorship indicators from senior→junior communications
        params.mentorship_indicators = self._extract_mentorship_indicators(senior_junior_exchanges)

        # Calculate message length statistics
        body_lengths = [len(e.body) for e in self.loader.emails if e.body]
        if body_lengths:
            params.avg_message_length = sum(body_lengths) // len(body_lengths)

        # Estimate formality (simple heuristic)
        params.formal_vs_informal = self._estimate_formality()

        # Extract common entity types mentioned
        params.common_entity_types = self._extract_entity_types()
        params.entity_mention_rate = len([p for p in self.patterns if p.subject_entity]) / max(len(self.patterns), 1)

        # Calculate confidence based on sample size
        confidence = min(1.0, emails_with_body / 1000)  # Full confidence at 1000+ emails
        if len(self.patterns) < 10:
            confidence *= 0.5
            notes.append("Warning: Low pattern count reduces confidence")

        return EnronCalibrationResult(
            parameters=params,
            sample_size=emails_with_body,
            pattern_counts=dict(pattern_counts),
            confidence=confidence,
            calibration_notes=notes,
        )

    def _extract_keywords(
        self,
        patterns: List[KnowledgeTransferPattern],
        seed_keywords: List[str],
    ) -> List[str]:
        """Extract most common keywords from pattern content."""
        if not patterns:
            return seed_keywords[:3]

        # Count word frequency across pattern content
        word_counts: Counter = Counter()
        for p in patterns:
            words = re.findall(r'\b[a-z]{4,}\b', p.content.lower())
            word_counts.update(words)

        # Filter to meaningful words (not stopwords)
        stopwords = {
            "that", "this", "with", "from", "have", "been", "would", "could",
            "should", "will", "about", "their", "there", "which", "when",
            "what", "your", "into", "also", "more", "than", "some", "these",
            "they", "then", "them", "here", "very", "just", "only", "like",
        }

        meaningful = [
            word for word, count in word_counts.most_common(20)
            if word not in stopwords and count >= 2
        ]

        # Combine with seed keywords
        result = list(set(seed_keywords + meaningful[:5]))
        return result[:10]

    def _extract_mentorship_indicators(
        self,
        exchanges: List[Tuple],
    ) -> List[str]:
        """Extract phrases that indicate mentorship/knowledge transfer."""
        indicators = [
            "let me know",
            "if you have questions",
            "feel free to",
            "don't hesitate",
            "here's how",
            "the way to",
            "keep in mind",
            "important to",
        ]

        # Could enhance by analyzing actual exchange content
        # For now, return common indicators
        return indicators

    def _estimate_formality(self) -> float:
        """
        Estimate communication formality level.

        Returns:
            Float 0-1 where 0 = very informal, 1 = very formal
        """
        formal_indicators = [
            r'\bregards\b', r'\bsincerely\b', r'\brespectfully\b',
            r'\bdear\b', r'\bplease be advised\b', r'\bper our\b',
        ]
        informal_indicators = [
            r'\bhey\b', r'\bthanks!\b', r'\bfyi\b', r'\basap\b',
            r'\bbtw\b', r'!!!', r'\blol\b', r'\bhaha\b',
        ]

        formal_count = 0
        informal_count = 0

        for email in self.loader.emails:
            if not email.body:
                continue
            body_lower = email.body.lower()

            for pattern in formal_indicators:
                if re.search(pattern, body_lower):
                    formal_count += 1
                    break

            for pattern in informal_indicators:
                if re.search(pattern, body_lower):
                    informal_count += 1
                    break

        total = formal_count + informal_count
        if total == 0:
            return 0.5  # Neutral

        return formal_count / total

    def _extract_entity_types(self) -> List[str]:
        """Extract common entity types mentioned in emails."""
        entity_types = []

        # Look for common business entity patterns
        patterns_found: Counter = Counter()

        entity_patterns = {
            "vendor": r'\b(?:vendor|supplier|contractor)\b',
            "client": r'\b(?:client|customer|account)\b',
            "project": r'\b(?:project|deal|initiative)\b',
            "department": r'\b(?:department|team|group|division)\b',
            "process": r'\b(?:process|procedure|workflow|system)\b',
            "document": r'\b(?:document|file|report|spreadsheet)\b',
        }

        for email in self.loader.emails:
            if not email.body:
                continue
            body_lower = email.body.lower()

            for entity_type, pattern in entity_patterns.items():
                if re.search(pattern, body_lower):
                    patterns_found[entity_type] += 1

        # Return types found in at least 5% of emails
        threshold = len(self.loader.emails) * 0.05
        entity_types = [
            etype for etype, count in patterns_found.most_common()
            if count >= threshold
        ]

        return entity_types if entity_types else ["project", "client", "process"]


def calibrate_from_enron(data_path: str) -> EnronCalibrationResult:
    """
    Convenience function to calibrate behavioral exhaust from Enron data.

    Args:
        data_path: Path to Enron CSV or maildir

    Returns:
        EnronCalibrationResult with calibrated parameters
    """
    from calibration.enron_loader import load_enron_dataset

    loader = load_enron_dataset(data_path)
    calibrator = EnronCalibrator(loader)
    return calibrator.calibrate()
