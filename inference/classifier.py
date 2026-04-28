"""
Context Object Classifier.

Uses Claude API (or rule-based fallback) to classify context objects
by context_grade and org_lineage.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
import json
import re
import os

from models.context_object import (
    ContextObject, ContextGrade, OrgLineage, ContentType,
)


@dataclass
class ClassificationResult:
    """Result of classifying a context object."""
    object_id: str
    context_grade: ContextGrade
    context_grade_confidence: float
    org_lineage: OrgLineage
    org_lineage_confidence: float
    reasoning: str
    used_api: bool = False


class ContextClassifier:
    """
    Classifies context objects by grade and lineage.

    Uses Claude API for classification when available, with rule-based
    fallback for testing and when API is not configured.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        use_api: bool = True,
    ):
        """
        Initialize classifier.

        Args:
            api_key: Anthropic API key (defaults to env var)
            model: Claude model to use
            use_api: Whether to use the API (False for rule-based only)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.use_api = use_api and bool(self.api_key)

        # Keywords for rule-based classification
        self._grade_keywords = {
            ContextGrade.compliance_scaffolding: [
                "required", "policy", "must", "compliance", "approval required",
                "check required", "do not", "never", "always"
            ],
            ContextGrade.institutional_memory: [
                "learned", "discovered", "root cause", "history", "relationship",
                "remember", "context", "background", "previously", "experience"
            ],
            ContextGrade.expired_process: [
                "was policy until", "no longer", "obsolete", "deprecated",
                "old rule", "used to", "formerly", "previously required"
            ],
            ContextGrade.generative_friction: [
                "intentional", "by design", "review required", "quality gate",
                "checkpoint", "deliberate"
            ],
            ContextGrade.pure_inefficiency: [
                "workaround", "manual", "duplicate", "unnecessary",
                "redundant", "waste"
            ],
        }

        self._lineage_keywords = {
            OrgLineage.failure_recovery: [
                "incident", "failure", "mistake", "error", "caused",
                "learned from", "after", "resulted in", "dispute"
            ],
            OrgLineage.political_settlement: [
                "override", "exception", "relationship", "regardless",
                "agreed", "negotiated", "verbally", "informal"
            ],
            OrgLineage.documented_policy: [
                "policy", "documented", "written", "official", "formal",
                "procedure", "standard", "guideline"
            ],
            OrgLineage.exception_handling: [
                "exception", "edge case", "special case", "unusual",
                "non-standard", "workaround"
            ],
            OrgLineage.direct_observation: [
                "observed", "noticed", "pattern", "tends to", "usually",
                "data shows", "based on", "analysis"
            ],
        }

    def _classify_rule_based(self, obj: ContextObject) -> ClassificationResult:
        """
        Classify using keyword matching.

        Returns classification with confidence based on keyword matches.
        """
        payload_lower = obj.payload.lower()

        # Score each grade
        grade_scores = {}
        for grade, keywords in self._grade_keywords.items():
            score = sum(1 for kw in keywords if kw in payload_lower)
            grade_scores[grade] = score

        # Score each lineage
        lineage_scores = {}
        for lineage, keywords in self._lineage_keywords.items():
            score = sum(1 for kw in keywords if kw in payload_lower)
            lineage_scores[lineage] = score

        # Select best grade
        best_grade = max(grade_scores, key=grade_scores.get)
        grade_score = grade_scores[best_grade]
        grade_confidence = min(0.9, 0.4 + (grade_score * 0.15))

        # Select best lineage
        best_lineage = max(lineage_scores, key=lineage_scores.get)
        lineage_score = lineage_scores[best_lineage]
        lineage_confidence = min(0.9, 0.4 + (lineage_score * 0.15))

        # Use content type as secondary signal
        if obj.content_type == ContentType.policy:
            if grade_scores[ContextGrade.compliance_scaffolding] >= grade_scores[ContextGrade.institutional_memory]:
                best_grade = ContextGrade.compliance_scaffolding
                grade_confidence = max(grade_confidence, 0.6)
        elif obj.content_type == ContentType.tribal_knowledge:
            if grade_scores[ContextGrade.institutional_memory] > 0:
                best_grade = ContextGrade.institutional_memory
                grade_confidence = max(grade_confidence, 0.65)

        return ClassificationResult(
            object_id=obj.id,
            context_grade=best_grade,
            context_grade_confidence=grade_confidence,
            org_lineage=best_lineage,
            org_lineage_confidence=lineage_confidence,
            reasoning=f"Rule-based classification. Grade keywords: {grade_score}, Lineage keywords: {lineage_score}",
            used_api=False,
        )

    def _build_classification_prompt(self, obj: ContextObject) -> str:
        """Build prompt for API classification."""
        return f"""Classify this organizational context object.

## Context Object
**ID:** {obj.id}
**Content Type:** {obj.content_type.value}
**Payload:** {obj.payload}
**Structured Data:** {json.dumps(obj.structured_data) if obj.structured_data else "None"}

## Classification Tasks

1. **Context Grade** - Classify the type of organizational friction:
   - compliance_scaffolding: Required process that prevents harm or ensures legal compliance
   - institutional_memory: Learned wisdom from past organizational experience
   - expired_process: Once-valid process that no longer applies but people still follow
   - generative_friction: Intentional friction designed to improve quality or outcomes
   - pure_inefficiency: Unnecessary process that should be eliminated

2. **Organizational Lineage** - How did this knowledge come to exist:
   - failure_recovery: Learned from a past failure, incident, or mistake
   - political_settlement: Result of organizational negotiation or relationship dynamics
   - documented_policy: Formal written policy or procedure
   - exception_handling: Pattern developed from handling edge cases
   - direct_observation: Observed behavior pattern from data or experience

Respond in JSON format:
```json
{{
  "context_grade": "grade_value",
  "context_grade_confidence": 0.XX,
  "org_lineage": "lineage_value",
  "org_lineage_confidence": 0.XX,
  "reasoning": "Brief explanation of classification"
}}
```"""

    def _call_api(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call Claude API for classification."""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)

            message = client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.3,  # Lower temperature for classification
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text

            # Parse JSON from response
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            return json.loads(response_text)

        except Exception as e:
            print(f"API classification error: {e}")
            return None

    def classify(self, obj: ContextObject) -> ClassificationResult:
        """
        Classify a context object.

        Uses API if available, falls back to rule-based.
        """
        # Try API first if configured
        if self.use_api:
            prompt = self._build_classification_prompt(obj)
            api_result = self._call_api(prompt)

            if api_result:
                try:
                    return ClassificationResult(
                        object_id=obj.id,
                        context_grade=ContextGrade(api_result["context_grade"]),
                        context_grade_confidence=float(api_result["context_grade_confidence"]),
                        org_lineage=OrgLineage(api_result["org_lineage"]),
                        org_lineage_confidence=float(api_result["org_lineage_confidence"]),
                        reasoning=api_result.get("reasoning", "API classification"),
                        used_api=True,
                    )
                except (KeyError, ValueError):
                    pass  # Fall through to rule-based

        # Rule-based fallback
        return self._classify_rule_based(obj)

    def classify_and_update(self, obj: ContextObject) -> ClassificationResult:
        """
        Classify and update the context object in place.

        Returns the classification result.
        """
        result = self.classify(obj)

        obj.context_grade = result.context_grade
        obj.context_grade_confidence = result.context_grade_confidence
        obj.org_lineage = result.org_lineage
        obj.org_lineage_confidence = result.org_lineage_confidence

        return result


def classify_context_object(
    obj: ContextObject,
    use_api: bool = False,
) -> ClassificationResult:
    """
    Convenience function to classify a single context object.

    Args:
        obj: The context object to classify
        use_api: Whether to use the Claude API

    Returns:
        ClassificationResult
    """
    classifier = ContextClassifier(use_api=use_api)
    return classifier.classify(obj)


def classify_batch(
    objects: List[ContextObject],
    use_api: bool = False,
    update_objects: bool = True,
) -> List[ClassificationResult]:
    """
    Classify a batch of context objects.

    Args:
        objects: List of context objects to classify
        use_api: Whether to use the Claude API
        update_objects: Whether to update objects in place

    Returns:
        List of ClassificationResult
    """
    classifier = ContextClassifier(use_api=use_api)
    results = []

    for obj in objects:
        if update_objects:
            result = classifier.classify_and_update(obj)
        else:
            result = classifier.classify(obj)
        results.append(result)

    return results


def evaluate_classification_accuracy(
    results: List[ClassificationResult],
    ground_truth: Dict[str, Tuple[ContextGrade, OrgLineage]],
) -> Dict[str, float]:
    """
    Evaluate classification accuracy against ground truth.

    Args:
        results: Classification results
        ground_truth: Dict mapping object_id to (grade, lineage) tuples

    Returns:
        Dict with accuracy metrics
    """
    grade_correct = 0
    lineage_correct = 0
    total = 0

    for result in results:
        if result.object_id in ground_truth:
            true_grade, true_lineage = ground_truth[result.object_id]
            total += 1

            if result.context_grade == true_grade:
                grade_correct += 1
            if result.org_lineage == true_lineage:
                lineage_correct += 1

    if total == 0:
        return {"grade_accuracy": 0.0, "lineage_accuracy": 0.0, "total_evaluated": 0}

    return {
        "grade_accuracy": grade_correct / total,
        "lineage_accuracy": lineage_correct / total,
        "total_evaluated": total,
    }
