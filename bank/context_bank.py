"""
Context Bank - Core storage and operations for Context Objects.

The Context Bank is the central repository for organizational memory.
It supports deposit, retrieval, update, and query operations with
confidence-weighted retrieval and contradiction detection.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
import json
import copy

from models.context_object import (
    ContextObject,
    ContextGrade,
    OrgLineage,
    SourceType,
    AgentAction,
    ProvenanceLink,
)
from .contradiction import ContradictionDetector, Contradiction
from .validation import (
    ExhaustValidator,
    ValidationResult,
    ValidationStatus,
    validate_before_deposit,
    create_validator_suite,
)


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


@dataclass
class DepositResult:
    """Result of depositing a context object."""
    success: bool
    object_id: str
    contradictions_detected: List[Contradiction] = field(default_factory=list)
    superseded_objects: List[str] = field(default_factory=list)
    error: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    original_confidence: Optional[float] = None
    adjusted_confidence: Optional[float] = None


@dataclass
class BankSnapshot:
    """Weekly snapshot of bank state for metrics."""
    week: int
    total_objects: int
    by_grade: Dict[str, int]
    by_source_type: Dict[str, int]
    confidence_distribution: Dict[str, int]  # buckets: 0-0.3, 0.3-0.6, 0.6-0.8, 0.8-1.0
    avg_confidence: float
    contradictions_count: int
    superseded_count: int
    objects_read_this_week: int
    objects_acted_on_this_week: int


class ContextBank:
    """
    Central repository for organizational context objects.

    The Context Bank supports:
    - Deposit: Add new context objects with contradiction checking
    - Retrieve: Query objects by various criteria with confidence weighting
    - Update: Modify existing objects, track reads/actions
    - Snapshot: Capture weekly state for metrics
    """

    def __init__(
        self,
        contradiction_detector: Optional[ContradictionDetector] = None,
        similarity_threshold: float = 0.85,
        validators: Optional[Dict[str, ExhaustValidator]] = None,
        enable_validation: bool = True,
    ):
        """
        Initialize the Context Bank.

        Args:
            contradiction_detector: Optional detector for finding contradictions.
                                   If None, a default detector is created.
            similarity_threshold: Threshold for semantic similarity in contradiction detection.
            validators: Dictionary of validators by exhaust type. If None and
                       enable_validation is True, default validators are created.
            enable_validation: Whether to validate objects before deposit.
        """
        self._objects: Dict[str, ContextObject] = {}
        self._contradiction_detector = contradiction_detector or ContradictionDetector(
            similarity_threshold=similarity_threshold
        )
        self._contradictions: List[Contradiction] = []
        self._current_week: int = 0

        # Validation setup
        self._enable_validation = enable_validation
        if enable_validation and validators is None:
            self._validators = create_validator_suite()
        else:
            self._validators = validators or {}

        # Tracking for weekly snapshots
        self._reads_this_week: set = set()
        self._actions_this_week: set = set()

    @property
    def current_week(self) -> int:
        """Get the current simulation week."""
        return self._current_week

    @current_week.setter
    def current_week(self, week: int) -> None:
        """Set the current simulation week and reset weekly tracking."""
        if week != self._current_week:
            self._reads_this_week = set()
            self._actions_this_week = set()
        self._current_week = week

    def deposit(
        self,
        context_object: ContextObject,
        check_contradictions: bool = True,
        skip_validation: bool = False,
    ) -> DepositResult:
        """
        Deposit a context object into the bank.

        Args:
            context_object: The context object to deposit.
            check_contradictions: Whether to check for contradictions with existing objects.
            skip_validation: If True, bypass the validation layer (useful for bulk imports).

        Returns:
            DepositResult with success status, validation result, and any detected contradictions.
        """
        original_confidence = context_object.confidence_at_creation
        validation_result: Optional[ValidationResult] = None

        # Validate object
        if not context_object.id:
            return DepositResult(
                success=False,
                object_id="",
                error="Context object must have an ID"
            )

        # Check for duplicate ID
        if context_object.id in self._objects:
            return DepositResult(
                success=False,
                object_id=context_object.id,
                error=f"Object with ID {context_object.id} already exists"
            )

        # Run validation layer if enabled
        if self._enable_validation and not skip_validation and self._validators:
            validation_result = validate_before_deposit(context_object, self._validators)

            # Check if validation failed completely
            if not validation_result.should_deposit:
                return DepositResult(
                    success=False,
                    object_id=context_object.id,
                    error=f"Validation failed: {validation_result.recommendations[0] if validation_result.recommendations else 'Unknown validation error'}",
                    validation_result=validation_result,
                    original_confidence=original_confidence,
                )

            # Apply confidence adjustment from validation
            if validation_result.adjusted_confidence is not None:
                context_object.confidence_at_creation = validation_result.adjusted_confidence

        # Check for contradictions
        contradictions = []
        if check_contradictions:
            contradictions = self._contradiction_detector.detect(
                context_object,
                list(self._objects.values()),
                self._current_week,
            )
            # Record contradictions
            for c in contradictions:
                self._contradictions.append(c)
                # Update the new object's contradicts list
                context_object.contradicts.append(c.existing_object_id)
                # Update the existing object's contradicts list
                if c.existing_object_id in self._objects:
                    self._objects[c.existing_object_id].contradicts.append(context_object.id)

        # Handle supersession
        superseded = []
        if context_object.supersedes:
            if context_object.supersedes in self._objects:
                self._objects[context_object.supersedes].superseded_by = context_object.id
                superseded.append(context_object.supersedes)

        # Compute current confidence
        context_object.update_confidence(self._current_week)

        # Store the object
        self._objects[context_object.id] = context_object

        return DepositResult(
            success=True,
            object_id=context_object.id,
            contradictions_detected=contradictions,
            superseded_objects=superseded,
            validation_result=validation_result,
            original_confidence=original_confidence,
            adjusted_confidence=context_object.confidence_at_creation if validation_result else None,
        )

    def deposit_many(
        self,
        objects: List[ContextObject],
        check_contradictions: bool = True,
        skip_validation: bool = False,
    ) -> List[DepositResult]:
        """Deposit multiple context objects."""
        return [self.deposit(obj, check_contradictions, skip_validation) for obj in objects]

    def register_source_profile(self, profile: Any) -> None:
        """
        Register a source credibility profile with all validators.

        Args:
            profile: SourceCredibilityProfile to register
        """
        for validator in self._validators.values():
            validator.register_source_profile(profile)

    def register_policy(self, policy: ContextObject) -> None:
        """
        Register a policy for consistency checking across all validators.

        Args:
            policy: Policy ContextObject to register
        """
        for validator in self._validators.values():
            validator.register_policy(policy)

    @property
    def validators(self) -> Dict[str, ExhaustValidator]:
        """Get the validator suite."""
        return self._validators

    def get(self, object_id: str) -> Optional[ContextObject]:
        """
        Retrieve a context object by ID.

        Updates the object's current_confidence based on decay.
        """
        obj = self._objects.get(object_id)
        if obj:
            obj.update_confidence(self._current_week)
        return obj

    def get_all(self) -> List[ContextObject]:
        """Get all context objects, updating confidence scores."""
        objects = list(self._objects.values())
        for obj in objects:
            obj.update_confidence(self._current_week)
        return objects

    def query(
        self,
        workflow_id: Optional[str] = None,
        context_grade: Optional[ContextGrade] = None,
        org_lineage: Optional[OrgLineage] = None,
        source_type: Optional[SourceType] = None,
        min_confidence: float = 0.0,
        exclude_superseded: bool = True,
        exclude_expired: bool = False,
        limit: Optional[int] = None,
    ) -> List[ContextObject]:
        """
        Query context objects with filters.

        Args:
            workflow_id: Filter by workflow.
            context_grade: Filter by grade.
            org_lineage: Filter by lineage.
            source_type: Filter by source type.
            min_confidence: Minimum current confidence score.
            exclude_superseded: Exclude objects that have been superseded.
            exclude_expired: Exclude objects with expired_process grade.
            limit: Maximum number of results.

        Returns:
            List of matching context objects, sorted by confidence descending.
        """
        results = []

        for obj in self._objects.values():
            # Update confidence
            obj.update_confidence(self._current_week)

            # Apply filters
            if workflow_id and obj.workflow_id != workflow_id:
                continue
            if context_grade and obj.context_grade != context_grade:
                continue
            if org_lineage and obj.org_lineage != org_lineage:
                continue
            if source_type and obj.source_type != source_type:
                continue
            if obj.current_confidence < min_confidence:
                continue
            if exclude_superseded and obj.is_superseded():
                continue
            if exclude_expired and obj.context_grade == ContextGrade.expired_process:
                continue

            results.append(obj)

        # Sort by confidence descending
        results.sort(key=lambda x: x.current_confidence or 0, reverse=True)

        if limit:
            results = results[:limit]

        return results

    def search_by_content(
        self,
        keywords: List[str],
        min_confidence: float = 0.0,
        limit: int = 10,
    ) -> List[ContextObject]:
        """
        Search context objects by keywords in payload and structured_data.

        Simple keyword matching for the simulation. In production,
        this would use vector embeddings.
        """
        results = []

        for obj in self._objects.values():
            obj.update_confidence(self._current_week)

            if obj.current_confidence < min_confidence:
                continue

            # Search in payload
            payload_lower = obj.payload.lower()
            match_count = sum(1 for kw in keywords if kw.lower() in payload_lower)

            # Search in structured_data
            if obj.structured_data:
                struct_str = json.dumps(obj.structured_data).lower()
                match_count += sum(1 for kw in keywords if kw.lower() in struct_str)

            if match_count > 0:
                results.append((obj, match_count))

        # Sort by match count, then by confidence
        results.sort(key=lambda x: (x[1], x[0].current_confidence or 0), reverse=True)

        return [obj for obj, _ in results[:limit]]

    def record_read(
        self,
        object_id: str,
        agent_id: str,
        action: str,
        outcome: Optional[str] = None,
    ) -> bool:
        """Record that an agent read a context object."""
        obj = self._objects.get(object_id)
        if not obj:
            return False

        obj.record_read(agent_id, action, outcome)
        self._reads_this_week.add(object_id)
        return True

    def record_action(
        self,
        object_id: str,
        agent_id: str,
        action: str,
        outcome: Optional[str] = None,
    ) -> bool:
        """Record that an agent acted on a context object."""
        obj = self._objects.get(object_id)
        if not obj:
            return False

        obj.record_action(agent_id, action, outcome)
        self._actions_this_week.add(object_id)
        return True

    def record_validation(
        self,
        object_id: str,
        agent_id: str,
        validated: bool,
        notes: Optional[str] = None,
    ) -> bool:
        """Record an agent's validation or invalidation of a context object."""
        obj = self._objects.get(object_id)
        if not obj:
            return False

        obj.record_validation(agent_id, validated, notes)
        return True

    def supersede(
        self,
        old_object_id: str,
        new_object: ContextObject,
    ) -> DepositResult:
        """
        Deposit a new object that supersedes an existing one.

        Args:
            old_object_id: ID of the object being superseded.
            new_object: The new context object.

        Returns:
            DepositResult from the deposit operation.
        """
        new_object.supersedes = old_object_id
        new_object.derivation_chain.append(ProvenanceLink(
            source_id=old_object_id,
            relationship="supersedes"
        ))
        return self.deposit(new_object)

    def get_contradictions(self) -> List[Contradiction]:
        """Get all detected contradictions."""
        return self._contradictions.copy()

    def get_active_objects_count(self) -> int:
        """Get count of non-superseded objects."""
        return sum(1 for obj in self._objects.values() if not obj.is_superseded())

    def snapshot(self) -> BankSnapshot:
        """
        Create a snapshot of current bank state for metrics.

        Returns:
            BankSnapshot with current statistics.
        """
        objects = list(self._objects.values())

        # Count by grade
        by_grade: Dict[str, int] = {}
        for obj in objects:
            grade = obj.context_grade.value if obj.context_grade else "unclassified"
            by_grade[grade] = by_grade.get(grade, 0) + 1

        # Count by source type
        by_source: Dict[str, int] = {}
        for obj in objects:
            source = obj.source_type.value
            by_source[source] = by_source.get(source, 0) + 1

        # Confidence distribution
        confidence_dist = {"0.0-0.3": 0, "0.3-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
        total_confidence = 0.0
        for obj in objects:
            obj.update_confidence(self._current_week)
            conf = obj.current_confidence or 0
            total_confidence += conf
            if conf < 0.3:
                confidence_dist["0.0-0.3"] += 1
            elif conf < 0.6:
                confidence_dist["0.3-0.6"] += 1
            elif conf < 0.8:
                confidence_dist["0.6-0.8"] += 1
            else:
                confidence_dist["0.8-1.0"] += 1

        avg_confidence = total_confidence / len(objects) if objects else 0.0

        # Count superseded
        superseded_count = sum(1 for obj in objects if obj.is_superseded())

        return BankSnapshot(
            week=self._current_week,
            total_objects=len(objects),
            by_grade=by_grade,
            by_source_type=by_source,
            confidence_distribution=confidence_dist,
            avg_confidence=avg_confidence,
            contradictions_count=len(self._contradictions),
            superseded_count=superseded_count,
            objects_read_this_week=len(self._reads_this_week),
            objects_acted_on_this_week=len(self._actions_this_week),
        )

    def reads_this_week(self) -> frozenset:
        """IDs of objects read at least once in the current week."""
        return frozenset(self._reads_this_week)

    def clear(self) -> None:
        """Clear all objects from the bank."""
        self._objects.clear()
        self._contradictions.clear()
        self._reads_this_week.clear()
        self._actions_this_week.clear()
        self._current_week = 0

    def export_to_dict(self) -> Dict[str, Any]:
        """Export bank contents to a dictionary for serialization."""
        return {
            "current_week": self._current_week,
            "objects": [obj.model_dump(mode="json") for obj in self._objects.values()],
            "contradictions": [
                {
                    "new_object_id": c.new_object_id,
                    "existing_object_id": c.existing_object_id,
                    "contradiction_type": c.contradiction_type,
                    "description": c.description,
                    "confidence": c.confidence,
                }
                for c in self._contradictions
            ],
        }

    def __len__(self) -> int:
        """Return number of objects in the bank."""
        return len(self._objects)

    def __contains__(self, object_id: str) -> bool:
        """Check if an object ID exists in the bank."""
        return object_id in self._objects
