"""
Agent Exhaust Generator.

Deploys specialized agents into Acme's workflows using the Claude API.
Each agent makes decisions and generates context objects from their reasoning.

Supports four experimental conditions:
- SILOED_TYPICAL: Agent only sees their department's context
- SILOED_ADVANCED: Agent sees department + adjacent departments, with basic decay
- GLOBAL_RAG: Agent sees all context, but no sophistication features
- CONTEXT_BANK: Agent sees all context with full sophistication (decay, provenance, etc.)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Tuple, Set
from enum import Enum
import json
import os
import re
import random

from config.simulation_config import (
    SIMULATION_CONFIG, AGENTS, CLIENTS, VENDORS, RunCondition,
    get_visible_context_ids, get_department_for_agent,
)
from config.workflows import get_workflow
from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction,
    ContextGrade, OrgLineage,
)


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class DecisionOutcome(str, Enum):
    """Possible outcomes of an agent decision."""
    CORRECT = "correct"  # Used available context appropriately
    INCORRECT = "incorrect"  # Failed to use available context
    PARTIAL = "partial"  # Partially correct
    ESCALATED = "escalated"  # Correctly escalated to human
    UNKNOWN = "unknown"  # Cannot determine correctness


@dataclass
class AgentDecision:
    """
    A decision made by an agent.

    Captures the agent's reasoning, confidence, and any context deposited.
    """
    decision_id: str
    agent_id: str
    agent_name: str
    workflow_id: str
    week: int
    timestamp: datetime

    # Scenario details
    scenario_type: str  # e.g., "vendor_sow", "staffing", "billing"
    scenario_description: str
    entities_involved: Dict[str, str]  # client, vendor, staff, etc.

    # Decision details
    decision_taken: str
    reasoning: str
    confidence: float  # 0.0 to 1.0

    # Context retrieval (for WITH_BANK condition)
    context_retrieved: List[str] = field(default_factory=list)  # CTX IDs
    context_used: List[str] = field(default_factory=list)  # CTX IDs actually used

    # Outcome (determined by ground truth comparison)
    outcome: DecisionOutcome = DecisionOutcome.UNKNOWN
    outcome_notes: Optional[str] = None

    # Context deposited (learnings from this decision)
    deposited_context: Optional[ContextObject] = None

    # Raw API response
    raw_response: Optional[str] = None
    tokens_used: int = 0


@dataclass
class AgentScenario:
    """A scenario for an agent to process."""
    scenario_id: str
    scenario_type: str
    workflow_id: str
    description: str
    entities: Dict[str, str]
    ground_truth_context_ids: List[str]  # CTX IDs that should be used
    correct_action: str  # What the agent should do
    incorrect_action: str  # What the agent would do without context


class AgentExhaustGenerator:
    """
    Generates agent decisions using Claude API.

    Supports four experimental conditions:
    - SILOED_TYPICAL: Department-only visibility, no sophistication
    - SILOED_ADVANCED: Department + adjacent, basic time decay
    - GLOBAL_RAG: Full visibility, no sophistication
    - CONTEXT_BANK: Full visibility + full sophistication

    Uses performance calibration to introduce realistic accuracy variance
    based on condition, week, chaos state, and cross-domain requirements.
    """

    def __init__(
        self,
        condition: RunCondition = RunCondition.CONTEXT_BANK,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        seed: Optional[int] = None,
        # Legacy parameter for backwards compatibility
        use_context_bank: Optional[bool] = None,
    ):
        """
        Initialize the agent generator.

        Args:
            condition: The experimental condition (SILOED_TYPICAL, SILOED_ADVANCED,
                      GLOBAL_RAG, or CONTEXT_BANK)
            api_key: Anthropic API key (defaults to env var)
            model: Claude model to use
            seed: Random seed for reproducibility
            use_context_bank: DEPRECATED - use condition parameter instead
        """
        # Handle legacy parameter
        if use_context_bank is not None:
            self.condition = RunCondition.CONTEXT_BANK if use_context_bank else RunCondition.SILOED_TYPICAL
        else:
            self.condition = condition

        # Backwards compatibility property
        self.use_context_bank = self.condition in [
            RunCondition.CONTEXT_BANK,
            RunCondition.GLOBAL_RAG,
            RunCondition.SILOED_ADVANCED,
            RunCondition.WITH_BANK,
        ]

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._decision_counter = 0

        # Set up random state for reproducible noise
        self._rng = random.Random(seed or SIMULATION_CONFIG.random_seed)

        # Get calibration configs
        self.performance_calibration = SIMULATION_CONFIG.performance_calibration
        self.retrieval_noise = SIMULATION_CONFIG.retrieval_noise

        # Track API usage
        self.total_tokens = 0
        self.api_calls = 0

    def get_visible_context_for_agent(self, agent_id: str) -> Set[str]:
        """
        Get the context IDs visible to an agent under current condition.

        For SILOED conditions, visibility is limited by department.
        For GLOBAL_RAG and CONTEXT_BANK, all context is visible.
        """
        department = get_department_for_agent(agent_id)
        return get_visible_context_ids(department, self.condition)

    def is_cross_domain_scenario(self, scenario: "AgentScenario", agent_id: str) -> bool:
        """
        Check if a scenario requires cross-domain knowledge.

        A scenario is cross-domain if the required context is outside
        the agent's primary department.
        """
        department = get_department_for_agent(agent_id)
        visible_in_silo = get_visible_context_ids(department, RunCondition.SILOED_TYPICAL)

        # If any ground truth context is NOT in the agent's basic silo, it's cross-domain
        for ctx_id in scenario.ground_truth_context_ids:
            if ctx_id not in visible_in_silo:
                return True
        return False

    def can_agent_see_context(self, agent_id: str, context_id: str) -> bool:
        """Check if an agent can see a specific context object under current condition."""
        visible = self.get_visible_context_for_agent(agent_id)
        return context_id in visible

    def _generate_decision_id(self) -> str:
        """Generate unique decision ID."""
        self._decision_counter += 1
        mode = "WB" if self.use_context_bank else "NB"
        return f"DEC-{mode}-{self._decision_counter:06d}"

    def _build_system_prompt(
        self,
        agent_config: Dict[str, Any],
        week: int,
        retrieved_context: Optional[str] = None,
    ) -> str:
        """Build the system prompt for an agent."""
        template = agent_config["system_prompt_template"]

        context_section = ""
        if retrieved_context and self.use_context_bank:
            context_section = f"\n## Relevant Organizational Context\n{retrieved_context}\n"
        elif self.use_context_bank:
            context_section = "\nNo relevant context retrieved from organizational memory.\n"
        else:
            context_section = ""  # No context bank available

        return template.format(
            week=week,
            context_section=context_section,
        )

    def _build_user_prompt(self, scenario: AgentScenario) -> str:
        """Build the user prompt describing the scenario."""
        entity_lines = []
        for key, value in scenario.entities.items():
            entity_lines.append(f"- {key}: {value}")

        return f"""## Decision Required

**Scenario Type:** {scenario.scenario_type}

**Description:**
{scenario.description}

**Entities Involved:**
{chr(10).join(entity_lines)}

Please provide:
1. Your recommended action
2. Your reasoning (including any relevant context you considered)
3. Your confidence level (0.0 to 1.0)
4. Any concerns or flags to raise

Format your response as JSON:
```json
{{
  "action": "your recommended action",
  "reasoning": "your reasoning",
  "confidence": 0.X,
  "concerns": ["any concerns"],
  "context_considered": ["list of context IDs if any"]
}}
```"""

    def _parse_agent_response(self, response: str) -> Dict[str, Any]:
        """Parse the agent's JSON response."""
        # Try to extract JSON from response
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try parsing the whole response as JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Fallback: extract key information heuristically
        return {
            "action": response[:200],
            "reasoning": response,
            "confidence": 0.5,
            "concerns": [],
            "context_considered": [],
        }

    def _call_claude_api(
        self,
        system_prompt: str,
        user_prompt: str,
        week: int = 1,
        agent_id: str = "unknown_agent",
        scenario: Optional["AgentScenario"] = None,
        is_chaos: bool = False,
    ) -> Tuple[str, int]:
        """
        Call the Claude API.

        Args:
            system_prompt: System prompt for the agent
            user_prompt: User prompt describing the scenario
            week: Current simulation week (for calibration in simulation mode)
            agent_id: The agent making the decision (for condition-based visibility)
            scenario: The scenario being processed (for cross-domain detection)
            is_chaos: Whether chaos conditions are active

        Returns:
            Tuple of (response text, tokens used)
        """
        if not self.api_key:
            # Simulation mode without API
            return self._simulate_response(
                user_prompt, week, agent_id, scenario, is_chaos
            ), 0

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)

            message = client.messages.create(
                model=self.model,
                max_tokens=SIMULATION_CONFIG.agent_max_tokens,
                temperature=SIMULATION_CONFIG.agent_temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            response_text = message.content[0].text
            tokens = message.usage.input_tokens + message.usage.output_tokens

            self.api_calls += 1
            self.total_tokens += tokens

            return response_text, tokens

        except ImportError:
            # anthropic package not installed, use simulation
            return self._simulate_response(
                user_prompt, week, agent_id, scenario, is_chaos
            ), 0
        except Exception as e:
            # API error, use simulation
            print(f"API error: {e}, using simulated response")
            return self._simulate_response(
                user_prompt, week, agent_id, scenario, is_chaos
            ), 0

    def _should_succeed(
        self,
        week: int,
        is_chaos: bool = False,
        is_cross_domain: bool = False,
    ) -> bool:
        """
        Determine if this decision should succeed based on calibration.

        Uses performance calibration to introduce realistic noise.
        Applies condition-specific accuracy, chaos penalties, and cross-domain penalties.

        Args:
            week: Current simulation week
            is_chaos: Whether chaos conditions are active
            is_cross_domain: Whether this decision requires cross-department knowledge
        """
        # Get base accuracy from calibration (now supports all 4 conditions)
        expected_accuracy = self.performance_calibration.get_accuracy_for_week(
            self.condition,
            week,
            is_chaos=is_chaos,
            is_cross_domain=is_cross_domain,
        )

        # Apply additional chaos modifier (v3.0) if set externally
        accuracy_modifier = getattr(self, '_current_accuracy_modifier', 1.0)
        if accuracy_modifier > 1.0:
            # Convert accuracy to error rate, multiply, convert back
            error_rate = 1.0 - expected_accuracy
            modified_error_rate = min(0.9, error_rate * accuracy_modifier)
            expected_accuracy = 1.0 - modified_error_rate

        return self._rng.random() < expected_accuracy

    def _should_retrieve_succeed(self, agent_id: str, required_context_ids: List[str]) -> bool:
        """
        Determine if context retrieval should succeed.

        For SILOED conditions, checks if required context is visible to the agent.
        For GLOBAL_RAG and CONTEXT_BANK, all context is potentially retrievable.
        Applies chaos context ignore probability (v3.0) if set.

        Args:
            agent_id: The agent making the decision
            required_context_ids: The context IDs needed for correct decision
        """
        # Check if agent can see the required context under current condition
        visible_context = self.get_visible_context_for_agent(agent_id)

        # For siloed conditions, if required context isn't visible, retrieval fails
        if self.condition in [RunCondition.SILOED_TYPICAL, RunCondition.SILOED_ADVANCED]:
            # Check if ANY required context is visible
            visible_required = [ctx for ctx in required_context_ids if ctx in visible_context]
            if not visible_required:
                return False  # Can't retrieve what you can't see

        # Check chaos-based context ignore (v3.0)
        context_ignore_prob = getattr(self, '_current_context_ignore_prob', 0.0)
        if context_ignore_prob > 0 and self._rng.random() < context_ignore_prob:
            return False  # Agent ignores context due to drift

        # Apply retrieval noise
        return self._rng.random() < self.retrieval_noise.retrieval_success_rate

    def _should_interpret_correctly(self) -> bool:
        """
        Determine if agent correctly interprets retrieved context.
        """
        return self._rng.random() < self.retrieval_noise.interpretation_accuracy

    def _simulate_response(
        self,
        user_prompt: str,
        week: int = 1,
        agent_id: str = "unknown_agent",
        scenario: Optional["AgentScenario"] = None,
        is_chaos: bool = False,
    ) -> str:
        """
        Simulate an agent response when API is not available.

        Uses performance calibration to introduce realistic variance
        in decision quality based on condition, week, chaos state, and
        cross-domain requirements.

        Args:
            user_prompt: The scenario prompt
            week: Current simulation week (for calibration)
            agent_id: The agent making the decision
            scenario: The scenario being processed (for cross-domain detection)
            is_chaos: Whether chaos conditions are active
        """
        # Determine if this is a cross-domain scenario
        is_cross_domain = False
        required_context_ids = []
        if scenario:
            is_cross_domain = self.is_cross_domain_scenario(scenario, agent_id)
            required_context_ids = scenario.ground_truth_context_ids

        # Determine if this decision should succeed (uses 4-condition calibration)
        decision_succeeds = self._should_succeed(
            week,
            is_chaos=is_chaos,
            is_cross_domain=is_cross_domain,
        )

        # For conditions that retrieve context, also check retrieval and interpretation
        if self.use_context_bank and required_context_ids:
            retrieval_succeeds = self._should_retrieve_succeed(agent_id, required_context_ids)
            interpretation_correct = self._should_interpret_correctly()
            # All three must succeed for correct decision with context
            decision_succeeds = retrieval_succeeds and interpretation_correct and decision_succeeds

        # Check for key scenario patterns
        # Exclude the cross-domain Brightline staffing scenario, handled further down;
        # otherwise it gets the vendor SOW responses and is scored on the wrong keywords.
        if "brightline" in user_prompt.lower() and "staffing" not in user_prompt.lower():
            if decision_succeeds:
                # Correct decision: route through secondary approval
                return json.dumps({
                    "action": "Route SOW through secondary approval from David Okafor before issuance",
                    "reasoning": "Based on organizational context CTX-001, Brightline Consulting requires secondary approval due to historical pricing disputes. I will route this SOW through David Okafor before proceeding.",
                    "confidence": 0.92,
                    "concerns": ["Historical pricing dispute from 2022"],
                    "context_considered": ["CTX-001"] if self.use_context_bank else []
                })
            else:
                # Incorrect decision: issue directly
                return json.dumps({
                    "action": "Issue SOW to Brightline Consulting as requested",
                    "reasoning": "Standard vendor SOW process. Brightline is on the approved vendor list. Proceeding with SOW issuance.",
                    "confidence": 0.85,
                    "concerns": [],
                    "context_considered": []
                })

        elif "jordan park" in user_prompt.lower() and "nexum" in user_prompt.lower():
            if decision_succeeds:
                # Correct decision: do not assign
                return json.dumps({
                    "action": "Do not assign Jordan Park to Nexum Partners work. Find alternative staffing.",
                    "reasoning": "Context CTX-010 indicates Jordan Park has a documented conflict with Nexum Partners. Must find alternative resource.",
                    "confidence": 0.95,
                    "concerns": ["Staff conflict documented in HR records"],
                    "context_considered": ["CTX-010"] if self.use_context_bank else []
                })
            else:
                # Incorrect decision: assign based on skills
                return json.dumps({
                    "action": "Assign Jordan Park to Nexum Partners engagement based on skills match",
                    "reasoning": "Jordan Park has the required skills and availability. Proceeding with assignment.",
                    "confidence": 0.80,
                    "concerns": [],
                    "context_considered": []
                })

        elif "terralogic" in user_prompt.lower() and ("payment" in user_prompt.lower() or "collection" in user_prompt.lower()):
            if decision_succeeds:
                # Correct decision: do not escalate
                return json.dumps({
                    "action": "Do not escalate until day 65. TerraLogic has 60-day actual payment cycle.",
                    "reasoning": "Context CTX-006 indicates TerraLogic operates on 60-day cycles regardless of contract terms. Premature escalation previously caused account loss.",
                    "confidence": 0.88,
                    "concerns": ["Wait until day 65 before escalation"],
                    "context_considered": ["CTX-006"] if self.use_context_bank else []
                })
            else:
                # Incorrect decision: escalate
                return json.dumps({
                    "action": "Escalate to collections given payment is past 45 days",
                    "reasoning": "Payment exceeds 45-day threshold. Following standard collections escalation process.",
                    "confidence": 0.82,
                    "concerns": [],
                    "context_considered": []
                })

        elif "hartwell" in user_prompt.lower() and "collection" in user_prompt.lower():
            # Cross-domain: Billing agent needs Business Development knowledge
            if decision_succeeds:
                return json.dumps({
                    "action": "Hold escalation and notify Marcus Webb directly. Strategic relationship.",
                    "reasoning": "Context CTX-003 indicates Hartwell Group has a strategic relationship with Marcus Webb. Direct escalation could damage the relationship.",
                    "confidence": 0.88,
                    "concerns": ["Strategic account - coordinate with relationship owner"],
                    "context_considered": ["CTX-003"] if self.use_context_bank else []
                })
            else:
                return json.dumps({
                    "action": "Proceed with standard collection escalation at 45 days",
                    "reasoning": "Following standard collections process for overdue accounts.",
                    "confidence": 0.80,
                    "concerns": [],
                    "context_considered": []
                })

        elif "hartwell" in user_prompt.lower():
            if decision_succeeds:
                # Correct decision: proceed with override
                return json.dumps({
                    "action": "Proceed with go decision. Marcus Webb override applies to Hartwell Group.",
                    "reasoning": "Context CTX-003 indicates Marcus Webb will override go/no-go for any Hartwell opportunity regardless of margin. Historical relationship.",
                    "confidence": 0.85,
                    "concerns": ["Partner override, document rationale"],
                    "context_considered": ["CTX-003"] if self.use_context_bank else []
                })
            else:
                # Incorrect decision: recommend no-go
                return json.dumps({
                    "action": "Recommend no-go due to margin below threshold",
                    "reasoning": "Margin analysis shows below 25% threshold. Standard criteria not met.",
                    "confidence": 0.75,
                    "concerns": ["Margin below threshold"],
                    "context_considered": []
                })

        elif "meridian" in user_prompt.lower() and ("billing" in user_prompt.lower() or "invoice" in user_prompt.lower()):
            # Cross-domain: Billing agent needs Client Engagements knowledge
            if decision_succeeds:
                return json.dumps({
                    "action": "Check scope documentation before escalating. Financial services clients need 24hr docs.",
                    "reasoning": "Context CTX-002 indicates financial services clients frequently expand scope verbally. Must verify documentation exists before escalating billing dispute.",
                    "confidence": 0.87,
                    "concerns": ["Scope documentation may be incomplete", "Financial services scope creep risk"],
                    "context_considered": ["CTX-002"] if self.use_context_bank else []
                })
            else:
                return json.dumps({
                    "action": "Escalate to collections for non-payment",
                    "reasoning": "Invoice is past due and client is disputing. Standard escalation process.",
                    "confidence": 0.78,
                    "concerns": [],
                    "context_considered": []
                })

        elif "brightline" in user_prompt.lower() and "staffing" in user_prompt.lower():
            # Cross-domain: Staffing agent needs Vendor knowledge
            if decision_succeeds:
                return json.dumps({
                    "action": "Flag Brightline relationship for extra oversight due to historical overbilling.",
                    "reasoning": "Context CTX-001 indicates Brightline Consulting has overbilling history. PM assignment should include active cost monitoring.",
                    "confidence": 0.89,
                    "concerns": ["Historical 40% overbilling incident", "Recommend dedicated financial oversight"],
                    "context_considered": ["CTX-001"] if self.use_context_bank else []
                })
            else:
                return json.dumps({
                    "action": "Proceed with standard subcontractor assignment",
                    "reasoning": "Brightline is on approved vendor list. Assigning PM per standard process.",
                    "confidence": 0.82,
                    "concerns": [],
                    "context_considered": []
                })

        # Default response
        return json.dumps({
            "action": "Proceed with standard process",
            "reasoning": "Following standard workflow procedures.",
            "confidence": 0.70,
            "concerns": [],
            "context_considered": []
        })

    def _evaluate_decision(
        self,
        decision: AgentDecision,
        scenario: AgentScenario,
        parsed_response: Dict[str, Any],
    ) -> Tuple[DecisionOutcome, str]:
        """
        Evaluate whether the decision was correct.

        Compares the action taken against the expected correct action.

        For WITH_BANK: Requires both correct action AND context usage.
        For WITHOUT_BANK: Evaluates based on action keywords only
        (represents lucky guesses, general knowledge, or prior experience).
        """
        action = parsed_response.get("action", "").lower()
        context_used = parsed_response.get("context_considered", [])

        # Check if correct context was used (only relevant for WITH_BANK)
        correct_context_ids = set(scenario.ground_truth_context_ids)
        used_context_ids = set(context_used)
        context_match = len(correct_context_ids & used_context_ids) / len(correct_context_ids) if correct_context_ids else 1.0

        # Check if action matches expected
        correct_keywords = scenario.correct_action.lower().split()
        incorrect_keywords = scenario.incorrect_action.lower().split()

        correct_matches = sum(1 for kw in correct_keywords if kw in action)
        incorrect_matches = sum(1 for kw in incorrect_keywords if kw in action)

        # Determine outcome
        if self.use_context_bank:
            # WITH_BANK: Requires both correct action and context usage
            if correct_matches > incorrect_matches and context_match >= 0.5:
                return DecisionOutcome.CORRECT, f"Used correct context ({context_used}) and took appropriate action"
            elif correct_matches > 0 and context_match > 0:
                return DecisionOutcome.PARTIAL, f"Partially correct - some context used but action incomplete"
            elif "escalate" in action or "review" in action:
                return DecisionOutcome.ESCALATED, "Escalated to human review"
            else:
                return DecisionOutcome.INCORRECT, f"Did not use available context. Action taken: {action[:100]}"
        else:
            # WITHOUT_BANK: Evaluate based on action keywords only
            # (represents lucky guesses, general knowledge, or prior experience)
            if correct_matches > incorrect_matches:
                return DecisionOutcome.CORRECT, f"Took appropriate action without context bank"
            elif "escalate" in action or "review" in action:
                return DecisionOutcome.ESCALATED, "Escalated to human review"
            else:
                return DecisionOutcome.INCORRECT, f"Took incorrect action. Action taken: {action[:100]}"

    def _create_deposited_context(
        self,
        decision: AgentDecision,
        parsed_response: Dict[str, Any],
        week: int,
    ) -> Optional[ContextObject]:
        """
        Create a context object from the agent's learning.

        Agents deposit what they learned from the decision.
        """
        # Only deposit if there's meaningful reasoning
        reasoning = parsed_response.get("reasoning", "")
        if len(reasoning) < 50:
            return None

        concerns = parsed_response.get("concerns", [])
        confidence = parsed_response.get("confidence", 0.5)

        # Determine content type based on decision
        if concerns:
            content_type = ContentType.observation
        elif decision.outcome == DecisionOutcome.CORRECT:
            content_type = ContentType.decision
        else:
            content_type = ContentType.inference

        return ContextObject(
            created_by=decision.agent_id,
            source_type=SourceType.agent,
            workflow_id=decision.workflow_id,
            week=week,
            content_type=content_type,
            payload=f"Agent {decision.agent_name} decision on {decision.scenario_type}: {reasoning[:300]}",
            structured_data={
                "scenario_type": decision.scenario_type,
                "decision_id": decision.decision_id,
                "action_taken": parsed_response.get("action", ""),
                "concerns": concerns,
                "entities": decision.entities_involved,
            },
            decay_function=DecayFunction.exponential,
            decay_rate=0.15,
            confidence_at_creation=confidence * 0.8,  # Slightly discount agent confidence
        )

    def generate_decision(
        self,
        agent_id: str,
        scenario: AgentScenario,
        week: int,
        context_bank=None,  # Optional ContextBank
        accuracy_modifier: float = 1.0,  # v3.0: Chaos-based accuracy modifier
        context_ignore_probability: float = 0.0,  # v3.0: Probability of ignoring context
    ) -> AgentDecision:
        """
        Generate an agent decision for a scenario.

        Args:
            agent_id: Which agent (proposal_agent, staffing_agent, etc.)
            scenario: The scenario to process
            week: Current simulation week
            context_bank: Optional context bank for retrieval
            accuracy_modifier: Multiplier on error rate (v3.0 chaos)
            context_ignore_probability: Probability of ignoring retrieved context (v3.0 chaos)

        Returns:
            AgentDecision with the agent's response
        """
        if agent_id not in AGENTS:
            raise ValueError(f"Unknown agent: {agent_id}")

        # Store chaos modifiers for this decision (v3.0)
        self._current_accuracy_modifier = accuracy_modifier
        self._current_context_ignore_prob = context_ignore_probability

        agent_config = AGENTS[agent_id]

        # Retrieve context if bank is available and in WITH_BANK mode
        retrieved_context = None
        context_ids = []

        if self.use_context_bank and context_bank is not None:
            from bank.retrieval import retrieve_relevant_context

            result = retrieve_relevant_context(
                bank=context_bank,
                scenario=scenario.entities,
                workflow_id=scenario.workflow_id,
                min_confidence=SIMULATION_CONFIG.retrieval_min_confidence,
                top_k=SIMULATION_CONFIG.retrieval_top_k,
            )

            if result.objects:
                retrieved_context = result.format_for_prompt()
                context_ids = [obj.id for obj in result.objects]

                # Record the read in the bank
                for obj in result.objects:
                    context_bank.record_read(
                        obj.id, agent_id,
                        f"Retrieved for {scenario.scenario_type} decision"
                    )

        # Build prompts
        system_prompt = self._build_system_prompt(agent_config, week, retrieved_context)
        user_prompt = self._build_user_prompt(scenario)

        # Determine if we're in chaos conditions based on accuracy modifier
        is_chaos = accuracy_modifier > 1.0 or context_ignore_probability > 0.0

        # Call API or simulate (passes condition-aware parameters)
        response_text, tokens = self._call_claude_api(
            system_prompt, user_prompt, week,
            agent_id=agent_id,
            scenario=scenario,
            is_chaos=is_chaos,
        )

        # Parse response
        parsed = self._parse_agent_response(response_text)

        # Create decision record
        decision = AgentDecision(
            decision_id=self._generate_decision_id(),
            agent_id=agent_id,
            agent_name=agent_config["name"],
            workflow_id=scenario.workflow_id,
            week=week,
            timestamp=utc_now(),
            scenario_type=scenario.scenario_type,
            scenario_description=scenario.description,
            entities_involved=scenario.entities,
            decision_taken=parsed.get("action", ""),
            reasoning=parsed.get("reasoning", ""),
            confidence=parsed.get("confidence", 0.5),
            context_retrieved=context_ids,
            context_used=parsed.get("context_considered", []),
            raw_response=response_text,
            tokens_used=tokens,
        )

        # Evaluate the decision
        outcome, notes = self._evaluate_decision(decision, scenario, parsed)
        decision.outcome = outcome
        decision.outcome_notes = notes

        # Create deposited context
        if self.use_context_bank:
            decision.deposited_context = self._create_deposited_context(decision, parsed, week)

        # Record action in bank if context was used
        if self.use_context_bank and context_bank is not None:
            for ctx_id in parsed.get("context_considered", []):
                if ctx_id in context_bank:
                    context_bank.record_action(
                        ctx_id, agent_id,
                        f"Applied to {scenario.scenario_type} decision",
                        outcome=outcome.value
                    )

        return decision


def generate_agent_decision(
    agent_id: str,
    scenario: AgentScenario,
    week: int,
    use_context_bank: bool = True,
    context_bank=None,
) -> AgentDecision:
    """
    Convenience function to generate a single agent decision.

    Args:
        agent_id: Which agent to use
        scenario: The scenario to process
        week: Current simulation week
        use_context_bank: Whether to use the context bank
        context_bank: Optional bank instance

    Returns:
        AgentDecision
    """
    generator = AgentExhaustGenerator(use_context_bank=use_context_bank)
    return generator.generate_decision(agent_id, scenario, week, context_bank)


# Pre-defined test scenarios for the key proof-of-concept cases
BRIGHTLINE_SOW_SCENARIO = AgentScenario(
    scenario_id="SCEN-BRIGHTLINE-001",
    scenario_type="vendor_sow",
    workflow_id="W4",
    description=(
        "A request has been received to issue a Statement of Work (SOW) to "
        "Brightline Consulting for a new financial services engagement. "
        "The engagement manager has submitted the standard SOW request form. "
        "Please determine the appropriate next steps for processing this SOW."
    ),
    entities={
        "vendor": "brightline_consulting",
        "vendor_name": "Brightline Consulting",
        "engagement_type": "financial_services",
        "sow_value": "$150,000",
        "requestor": "engagement_manager",
    },
    ground_truth_context_ids=["CTX-001"],
    correct_action="route through secondary approval from David Okafor",
    incorrect_action="issue SOW directly to vendor",
)

JORDAN_PARK_STAFFING_SCENARIO = AgentScenario(
    scenario_id="SCEN-JORDAN-001",
    scenario_type="staffing_assignment",
    workflow_id="W3",
    description=(
        "A staffing request has been submitted for the Nexum Partners engagement. "
        "Jordan Park has been identified as a skills match with current availability. "
        "Please recommend whether to proceed with this assignment."
    ),
    entities={
        "client": "nexum_partners",
        "client_name": "Nexum Partners",
        "candidate": "jordan_park",
        "candidate_name": "Jordan Park",
        "skills_match": "high",
        "availability": "available",
    },
    ground_truth_context_ids=["CTX-010"],
    correct_action="do not assign Jordan Park, find alternative",
    incorrect_action="assign Jordan Park based on skills match",
)

TERRALOGIC_PAYMENT_SCENARIO = AgentScenario(
    scenario_id="SCEN-TERRALOGIC-001",
    scenario_type="payment_escalation",
    workflow_id="W5",
    description=(
        "TerraLogic invoice #4523 is now 48 days past due. "
        "Standard process indicates escalation to collections at 45 days. "
        "Please recommend next steps for this overdue payment."
    ),
    entities={
        "client": "terralogic",
        "client_name": "TerraLogic",
        "invoice_number": "4523",
        "days_overdue": "48",
        "amount": "$75,000",
    },
    ground_truth_context_ids=["CTX-006"],
    correct_action="do not escalate until day 65",
    incorrect_action="escalate to collections",
)

HARTWELL_PROPOSAL_SCENARIO = AgentScenario(
    scenario_id="SCEN-HARTWELL-001",
    scenario_type="go_no_go",
    workflow_id="W2",
    description=(
        "A new opportunity has been identified with Hartwell Group. "
        "Initial margin analysis shows the engagement at 18% margin, "
        "below the 25% standard threshold. Please provide go/no-go recommendation."
    ),
    entities={
        "client": "hartwell_group",
        "client_name": "Hartwell Group",
        "opportunity_value": "$400,000",
        "calculated_margin": "18%",
        "standard_threshold": "25%",
    },
    ground_truth_context_ids=["CTX-003"],
    correct_action="proceed with go decision due to Marcus Webb override",
    incorrect_action="recommend no-go due to margin below threshold",
)

# =============================================================================
# CROSS-DOMAIN SCENARIOS (require multi-department knowledge)
# =============================================================================
# These scenarios demonstrate where siloed approaches fail most dramatically.
# An agent in one department needs context owned by another department.

MERIDIAN_BILLING_SCENARIO = AgentScenario(
    scenario_id="SCEN-MERIDIAN-CROSS-001",
    scenario_type="billing_escalation",
    workflow_id="W5",
    description=(
        "Meridian Financial invoice #7891 is 35 days past due. "
        "Client claims the invoiced amount exceeds the agreed scope. "
        "Please recommend next steps for resolving this dispute."
    ),
    entities={
        "client": "meridian_financial",
        "client_name": "Meridian Financial",
        "invoice_number": "7891",
        "days_overdue": "35",
        "amount": "$95,000",
        "dispute_reason": "scope_disagreement",
    },
    # Requires CTX-002 (Client Engagements knowledge about scope documentation)
    # But billing_agent is in Finance & Billing, not Client Engagements
    ground_truth_context_ids=["CTX-002"],
    correct_action="check scope documentation before escalating, financial services clients need 24hr docs",
    incorrect_action="escalate to collections for non-payment",
)

BRIGHTLINE_STAFFING_SCENARIO = AgentScenario(
    scenario_id="SCEN-BRIGHTLINE-CROSS-001",
    scenario_type="subcontractor_assignment",
    workflow_id="W3",
    description=(
        "A staffing request has been submitted for a federal compliance engagement. "
        "Brightline Consulting is the proposed subcontractor, and we need to assign "
        "an internal PM to manage the relationship. Please recommend the assignment."
    ),
    entities={
        "client": "federal_client_xyz",
        "client_name": "Federal Client XYZ",
        "subcontractor": "brightline_consulting",
        "subcontractor_name": "Brightline Consulting",
        "role_needed": "Project Manager",
        "engagement_type": "federal_compliance",
    },
    # Requires CTX-001 (Vendor & Procurement knowledge about Brightline issues)
    # But staffing_agent is in Resource Management, not Vendor & Procurement
    ground_truth_context_ids=["CTX-001"],
    correct_action="flag Brightline relationship for extra oversight, historical overbilling",
    incorrect_action="proceed with standard subcontractor assignment",
)

HARTWELL_COLLECTION_SCENARIO = AgentScenario(
    scenario_id="SCEN-HARTWELL-CROSS-001",
    scenario_type="payment_collection",
    workflow_id="W5",
    description=(
        "Hartwell Group has an outstanding balance of $125,000 that is 40 days past due. "
        "Standard collection process calls for escalation at 45 days. "
        "Please recommend next steps."
    ),
    entities={
        "client": "hartwell_group",
        "client_name": "Hartwell Group",
        "outstanding_amount": "$125,000",
        "days_overdue": "40",
        "relationship_tenure": "5 years",
    },
    # Requires CTX-003 (Business Development knowledge about Marcus Webb relationship)
    # But billing_agent is in Finance & Billing, not Business Development
    ground_truth_context_ids=["CTX-003"],
    correct_action="hold escalation and notify Marcus Webb directly, strategic relationship",
    incorrect_action="proceed with standard collection escalation at 45 days",
)
