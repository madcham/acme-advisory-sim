"""
Tests for Enron email corpus calibration.

These tests verify the Enron loader and calibrator work correctly
to derive behavioral exhaust parameters from real organizational emails.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from calibration.enron_loader import (
    EnronLoader,
    EnronEmail,
    KnowledgeTransferPattern,
    EnronOrgProfile,
)
from calibration.enron_calibrator import (
    EnronCalibrator,
    BehavioralExhaustParameters,
    EnronCalibrationResult,
)


class TestEnronEmail:
    """Tests for EnronEmail dataclass."""

    def test_email_extracts_username(self):
        """Test username extraction from email address."""
        email = EnronEmail(
            message_id="test-123",
            date=None,
            from_email="john.smith@enron.com",
            from_name="John Smith",
            to_email="jane.doe@enron.com",
            to_name="Jane Doe",
            subject="Test subject",
            body="Test body",
            file_path="/test/path",
        )

        assert email.from_username == "john.smith"
        assert email.to_username == "jane.doe"

    def test_email_handles_missing_email(self):
        """Test graceful handling of missing email addresses."""
        email = EnronEmail(
            message_id="test-123",
            date=None,
            from_email="",
            from_name="",
            to_email="",
            to_name="",
            subject="",
            body="",
            file_path="",
        )

        assert email.from_username == ""
        assert email.to_username == ""


class TestKnowledgeTransferPattern:
    """Tests for KnowledgeTransferPattern dataclass."""

    def test_pattern_defaults(self):
        """Test pattern has correct defaults."""
        pattern = KnowledgeTransferPattern(
            pattern_type="instruction",
            from_person="Senior",
            to_person="Junior",
            subject_entity=None,
            content="Test content",
            confidence=0.8,
            source_email_id="test-123",
        )

        assert pattern.has_question is False
        assert pattern.has_instruction is False
        assert pattern.has_exception is False
        assert pattern.has_approval_chain is False


class TestEnronOrgProfile:
    """Tests for EnronOrgProfile dataclass."""

    def test_profile_defaults(self):
        """Test profile has correct defaults."""
        profile = EnronOrgProfile(
            email="test@enron.com",
            name="Test User",
            username="test",
        )

        assert profile.email_count == 0
        assert profile.sent_count == 0
        assert profile.received_count == 0
        assert profile.estimated_seniority == 0.5


class TestEnronLoader:
    """Tests for EnronLoader class."""

    def test_loader_initialization(self, tmp_path):
        """Test loader initializes correctly."""
        loader = EnronLoader(str(tmp_path / "test.csv"))

        assert loader.emails == []
        assert loader.profiles == {}

    def test_loader_has_pattern_detection(self, tmp_path):
        """Test loader has pattern detection regex lists."""
        loader = EnronLoader(str(tmp_path / "test.csv"))

        assert len(loader.question_patterns) > 0
        assert len(loader.instruction_patterns) > 0
        assert len(loader.exception_patterns) > 0
        assert len(loader.approval_patterns) > 0

    def test_update_profile_creates_sender(self, tmp_path):
        """Test profile creation for email sender."""
        loader = EnronLoader(str(tmp_path / "test.csv"))

        email = EnronEmail(
            message_id="test-123",
            date=None,
            from_email="sender@enron.com",
            from_name="Sender Name",
            to_email="recipient@enron.com",
            to_name="Recipient Name",
            subject="Test",
            body="Test body",
            file_path="/test",
        )

        loader._update_profile(email)

        assert "sender@enron.com" in loader.profiles
        assert loader.profiles["sender@enron.com"].sent_count == 1

    def test_update_profile_creates_recipient(self, tmp_path):
        """Test profile creation for email recipient."""
        loader = EnronLoader(str(tmp_path / "test.csv"))

        email = EnronEmail(
            message_id="test-123",
            date=None,
            from_email="sender@enron.com",
            from_name="Sender",
            to_email="recipient@enron.com",
            to_name="Recipient",
            subject="Test",
            body="Test body",
            file_path="/test",
        )

        loader._update_profile(email)

        assert "recipient@enron.com" in loader.profiles
        assert loader.profiles["recipient@enron.com"].received_count == 1


class TestEnronCalibrator:
    """Tests for EnronCalibrator class."""

    def test_calibrator_initialization(self, tmp_path):
        """Test calibrator initializes with loader."""
        loader = EnronLoader(str(tmp_path / "test.csv"))
        calibrator = EnronCalibrator(loader)

        assert calibrator.loader == loader
        assert calibrator.patterns == []

    def test_calibrate_empty_returns_zero_confidence(self, tmp_path):
        """Test calibration with no emails returns zero confidence."""
        loader = EnronLoader(str(tmp_path / "test.csv"))
        calibrator = EnronCalibrator(loader)

        result = calibrator.calibrate()

        assert result.confidence == 0.0
        assert result.sample_size == 0

    def test_calibrate_returns_parameters(self, tmp_path):
        """Test calibration returns BehavioralExhaustParameters."""
        loader = EnronLoader(str(tmp_path / "test.csv"))

        # Add some mock emails with bodies
        for i in range(10):
            email = EnronEmail(
                message_id=f"test-{i}",
                date=None,
                from_email=f"sender{i}@enron.com",
                from_name=f"Sender {i}",
                to_email=f"recipient{i}@enron.com",
                to_name=f"Recipient {i}",
                subject="Test",
                body="Can you please help me with this? Make sure to always check the approval process.",
                file_path="/test",
            )
            loader.emails.append(email)
            loader._update_profile(email)

        calibrator = EnronCalibrator(loader)
        result = calibrator.calibrate()

        assert isinstance(result.parameters, BehavioralExhaustParameters)
        assert result.sample_size == 10


class TestBehavioralExhaustParameters:
    """Tests for BehavioralExhaustParameters dataclass."""

    def test_parameters_defaults(self):
        """Test parameters have correct defaults."""
        params = BehavioralExhaustParameters()

        assert params.question_rate == 0.0
        assert params.instruction_rate == 0.0
        assert params.exception_rate == 0.0
        assert params.approval_rate == 0.0
        assert params.senior_to_junior_ratio == 0.5
        assert params.avg_message_length == 100
        assert params.formal_vs_informal == 0.5


class TestEnronCalibrationResult:
    """Tests for EnronCalibrationResult dataclass."""

    def test_result_defaults(self):
        """Test result has correct structure."""
        result = EnronCalibrationResult(
            parameters=BehavioralExhaustParameters(),
            sample_size=100,
            pattern_counts={"question_answer": 30, "instruction": 10},
            confidence=0.5,
        )

        assert result.sample_size == 100
        assert result.confidence == 0.5
        assert len(result.calibration_notes) == 0


class TestCalibratedGenerator:
    """Tests for generator with Enron calibration."""

    def test_generator_accepts_calibration(self):
        """Test BehavioralExhaustGenerator accepts calibration params."""
        from generators.behavioral_exhaust import BehavioralExhaustGenerator

        params = BehavioralExhaustParameters(
            question_rate=0.4,
            instruction_rate=0.1,
            exception_rate=0.05,
            approval_rate=0.08,
        )

        gen = BehavioralExhaustGenerator(seed=42, calibration=params)

        assert gen._calibration_applied is True
        summary = gen.get_calibration_summary()
        assert summary["source"] == "enron"
        assert summary["question_rate"] == 0.4

    def test_generator_without_calibration(self):
        """Test generator works without calibration."""
        from generators.behavioral_exhaust import BehavioralExhaustGenerator

        gen = BehavioralExhaustGenerator(seed=42)

        assert gen._calibration_applied is False
        summary = gen.get_calibration_summary()
        assert summary["source"] == "default"


class TestPatternExtraction:
    """Tests for pattern extraction from emails."""

    def test_extract_question_pattern(self, tmp_path):
        """Test extraction of question patterns."""
        loader = EnronLoader(str(tmp_path / "test.csv"))

        email = EnronEmail(
            message_id="test-123",
            date=None,
            from_email="junior@enron.com",
            from_name="Junior Person",
            to_email="senior@enron.com",
            to_name="Senior Person",
            subject="Question",
            body="Can you help me understand the approval process? What is the timeline?",
            file_path="/test",
        )
        loader.emails.append(email)

        patterns = loader.extract_knowledge_patterns()

        assert len(patterns) > 0
        assert any(p.pattern_type == "question_answer" for p in patterns)

    def test_extract_instruction_pattern(self, tmp_path):
        """Test extraction of instruction patterns."""
        loader = EnronLoader(str(tmp_path / "test.csv"))

        email = EnronEmail(
            message_id="test-123",
            date=None,
            from_email="senior@enron.com",
            from_name="Senior Person",
            to_email="junior@enron.com",
            to_name="Junior Person",
            subject="Instructions",
            body="Always make sure to get approval before proceeding. Never skip the review step.",
            file_path="/test",
        )
        loader.emails.append(email)

        patterns = loader.extract_knowledge_patterns()

        assert len(patterns) > 0
        # Should detect instruction pattern
        instruction_patterns = [p for p in patterns if p.has_instruction]
        assert len(instruction_patterns) > 0

    def test_extract_exception_pattern(self, tmp_path):
        """Test extraction of exception patterns."""
        loader = EnronLoader(str(tmp_path / "test.csv"))

        email = EnronEmail(
            message_id="test-123",
            date=None,
            from_email="senior@enron.com",
            from_name="Senior Person",
            to_email="junior@enron.com",
            to_name="Junior Person",
            subject="Special case",
            body="Always follow the standard process, except when dealing with VIP clients. Unless you have written approval, don't make exceptions.",
            file_path="/test",
        )
        loader.emails.append(email)

        patterns = loader.extract_knowledge_patterns()

        assert len(patterns) > 0
        exception_patterns = [p for p in patterns if p.has_exception]
        assert len(exception_patterns) > 0
