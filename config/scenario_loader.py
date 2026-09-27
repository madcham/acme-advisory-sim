"""
Scenario Loader for External YAML Configuration.

Loads agent scenarios from config/scenarios.yaml instead of hardcoded definitions.
This enables:
- Easy scenario modification without code changes
- Version control of scenario configurations
- Validation of scenario structure
- Dynamic scenario injection based on week/chaos conditions
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any
import yaml
import re

from generators.agent_exhaust import AgentScenario


@dataclass
class ScenarioConfig:
    """Complete scenario configuration loaded from YAML."""
    vendor_scenarios: List[AgentScenario] = field(default_factory=list)
    staffing_scenarios: List[AgentScenario] = field(default_factory=list)
    payment_scenarios: List[AgentScenario] = field(default_factory=list)
    proposal_scenarios: List[AgentScenario] = field(default_factory=list)
    cross_domain_scenarios: List[AgentScenario] = field(default_factory=list)
    chaos_scenarios: List[AgentScenario] = field(default_factory=list)
    response_templates: Dict[str, Any] = field(default_factory=dict)

    def all_scenarios(self) -> List[AgentScenario]:
        """Return all scenarios as a flat list."""
        return (
            self.vendor_scenarios +
            self.staffing_scenarios +
            self.payment_scenarios +
            self.proposal_scenarios +
            self.cross_domain_scenarios +
            self.chaos_scenarios
        )

    def get_scenarios_for_week(self, week: int) -> List[AgentScenario]:
        """Get all scenarios scheduled for a specific week."""
        return [
            s for s in self.all_scenarios()
            if hasattr(s, 'injection_weeks') and week in s.injection_weeks
        ]

    def get_cross_domain_scenarios(self) -> List[AgentScenario]:
        """Get only cross-domain scenarios."""
        return self.cross_domain_scenarios

    def get_within_domain_scenarios(self) -> List[AgentScenario]:
        """Get only within-domain scenarios."""
        return (
            self.vendor_scenarios +
            self.staffing_scenarios +
            self.payment_scenarios +
            self.proposal_scenarios
        )


@dataclass
class ExtendedAgentScenario(AgentScenario):
    """Extended scenario with additional metadata from YAML."""
    is_cross_domain: bool = False
    required_from_department: Optional[str] = None
    agent_department: Optional[str] = None
    chaos_type: Optional[str] = None
    injection_weeks: List[int] = field(default_factory=list)


def _parse_scenario(data: Dict[str, Any]) -> ExtendedAgentScenario:
    """Parse a single scenario from YAML data."""
    return ExtendedAgentScenario(
        scenario_id=data["scenario_id"],
        scenario_type=data["scenario_type"],
        workflow_id=data["workflow_id"],
        description=data["description"].strip(),
        entities=data["entities"],
        ground_truth_context_ids=data["ground_truth_context_ids"],
        correct_action=data["correct_action"],
        incorrect_action=data["incorrect_action"],
        is_cross_domain=data.get("is_cross_domain", False),
        required_from_department=data.get("required_from_department"),
        agent_department=data.get("agent_department"),
        chaos_type=data.get("chaos_type"),
        injection_weeks=data.get("injection_weeks", []),
    )


def load_scenarios(
    config_path: Optional[Path] = None,
) -> ScenarioConfig:
    """
    Load scenarios from YAML configuration file.

    Args:
        config_path: Path to scenarios.yaml. Defaults to config/scenarios.yaml

    Returns:
        ScenarioConfig with all loaded scenarios
    """
    if config_path is None:
        # Default to config/scenarios.yaml relative to this file
        config_path = Path(__file__).parent / "scenarios.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Scenarios config not found: {config_path}")

    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    config = ScenarioConfig()

    # Parse each scenario category
    if "vendor_scenarios" in data:
        config.vendor_scenarios = [
            _parse_scenario(s) for s in data["vendor_scenarios"]
        ]

    if "staffing_scenarios" in data:
        config.staffing_scenarios = [
            _parse_scenario(s) for s in data["staffing_scenarios"]
        ]

    if "payment_scenarios" in data:
        config.payment_scenarios = [
            _parse_scenario(s) for s in data["payment_scenarios"]
        ]

    if "proposal_scenarios" in data:
        config.proposal_scenarios = [
            _parse_scenario(s) for s in data["proposal_scenarios"]
        ]

    if "cross_domain_scenarios" in data:
        config.cross_domain_scenarios = [
            _parse_scenario(s) for s in data["cross_domain_scenarios"]
        ]

    if "chaos_scenarios" in data:
        config.chaos_scenarios = [
            _parse_scenario(s) for s in data["chaos_scenarios"]
        ]

    if "response_templates" in data:
        config.response_templates = data["response_templates"]

    return config


def build_injection_schedule(
    config: ScenarioConfig,
) -> Dict[int, List[AgentScenario]]:
    """
    Build a week-by-week injection schedule from scenarios.

    Returns:
        Dict mapping week number to list of scenarios to inject
    """
    schedule: Dict[int, List[AgentScenario]] = {}

    for scenario in config.all_scenarios():
        if hasattr(scenario, 'injection_weeks'):
            for week in scenario.injection_weeks:
                if week not in schedule:
                    schedule[week] = []
                schedule[week].append(scenario)

    return schedule


def get_response_template(
    config: ScenarioConfig,
    scenario_type: str,
    with_context: bool,
) -> Optional[Dict[str, Any]]:
    """
    Get the expected response template for a scenario type.

    Args:
        config: Loaded scenario configuration
        scenario_type: Type of scenario (vendor_sow, staffing, etc.)
        with_context: Whether this is the with-context or without-context template

    Returns:
        Template dict with action_pattern, reasoning_pattern, concerns
    """
    templates = config.response_templates.get(scenario_type, {})

    if with_context:
        return templates.get("correct_with_context")
    else:
        return templates.get("incorrect_without_context")


def validate_scenario_config(config: ScenarioConfig) -> List[str]:
    """
    Validate the loaded scenario configuration.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    for scenario in config.all_scenarios():
        # Check required fields
        if not scenario.scenario_id:
            errors.append(f"Scenario missing ID: {scenario}")

        if not scenario.ground_truth_context_ids:
            errors.append(f"Scenario {scenario.scenario_id} missing ground_truth_context_ids")

        if not scenario.correct_action:
            errors.append(f"Scenario {scenario.scenario_id} missing correct_action")

        if not scenario.incorrect_action:
            errors.append(f"Scenario {scenario.scenario_id} missing incorrect_action")

        # Check workflow ID is valid
        valid_workflows = ["W1", "W2", "W3", "W4", "W5"]
        if scenario.workflow_id not in valid_workflows:
            errors.append(
                f"Scenario {scenario.scenario_id} has invalid workflow_id: {scenario.workflow_id}"
            )

    # Check for duplicate IDs
    ids = [s.scenario_id for s in config.all_scenarios()]
    duplicates = [id for id in ids if ids.count(id) > 1]
    if duplicates:
        errors.append(f"Duplicate scenario IDs: {set(duplicates)}")

    return errors


# =============================================================================
# CACHED LOADER
# =============================================================================

_cached_config: Optional[ScenarioConfig] = None


def get_scenario_config(force_reload: bool = False) -> ScenarioConfig:
    """
    Get scenario configuration with caching.

    Args:
        force_reload: If True, reload from disk even if cached

    Returns:
        ScenarioConfig
    """
    global _cached_config

    if _cached_config is None or force_reload:
        _cached_config = load_scenarios()

        # Validate on load
        errors = validate_scenario_config(_cached_config)
        if errors:
            import logging
            logger = logging.getLogger(__name__)
            for error in errors:
                logger.warning(f"Scenario config validation: {error}")

    return _cached_config


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

def get_legacy_scenarios() -> Dict[str, AgentScenario]:
    """
    Get scenarios in the legacy format (for backwards compatibility).

    Returns:
        Dict mapping scenario names to AgentScenario objects
    """
    config = get_scenario_config()

    legacy = {}
    for scenario in config.all_scenarios():
        # Convert scenario_id to legacy name format
        # e.g., "SCEN-BRIGHTLINE-001" -> "BRIGHTLINE_SOW_SCENARIO"
        name_parts = scenario.scenario_id.replace("SCEN-", "").replace("-", "_")
        legacy_name = f"{name_parts}_SCENARIO"
        legacy[legacy_name] = scenario

    return legacy
