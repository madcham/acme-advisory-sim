"""
BPI Challenge Data Calibrator.

Extracts timing and frequency distributions from BPI Challenge data
and applies them to calibrate the Acme Advisory simulation.

Maps BPI activities to Acme workflows and calibrates:
- Event timing distributions (hourly, daily)
- Inter-event gaps
- Resource specialization patterns
- Workflow complexity distributions
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random
import math

from calibration.bpi_loader import BPILoader, BPIDataset, get_default_loader


@dataclass
class TimingCalibration:
    """Calibrated timing parameters for simulation."""
    # Probability of event at each hour (0-23)
    hourly_weights: Dict[int, float] = field(default_factory=dict)

    # Probability of event on each weekday (0=Mon, 6=Sun)
    daily_weights: Dict[int, float] = field(default_factory=dict)

    # Percentiles of inter-event gaps in hours
    gap_p25: float = 0.5
    gap_p50: float = 2.0
    gap_p75: float = 8.0
    gap_p95: float = 48.0

    # Events per week (normalized to Acme scale)
    events_per_week: int = 150


@dataclass
class ResourceCalibration:
    """Calibrated resource behavior patterns."""
    # How specialized are resources (0=generalist, 1=specialist)
    avg_specialization: float = 0.4

    # Workload inequality (0=equal, 1=highly unequal)
    workload_gini: float = 0.3

    # Tenure distribution (years of experience)
    tenure_distribution: Dict[str, float] = field(default_factory=lambda: {
        "junior": 0.30,    # 0-2 years
        "mid": 0.40,       # 2-5 years
        "senior": 0.25,    # 5-10 years
        "veteran": 0.05,   # 10+ years
    })


@dataclass
class WorkflowCalibration:
    """Calibrated workflow characteristics."""
    # Mapping of BPI activities to Acme workflows
    activity_workflow_map: Dict[str, str] = field(default_factory=dict)

    # Complexity distribution per workflow
    workflow_complexity: Dict[str, float] = field(default_factory=dict)

    # Average events per case by workflow
    events_per_case: Dict[str, float] = field(default_factory=dict)


class BPICalibrator:
    """
    Calibrates simulation parameters from BPI Challenge data.

    Maps BPI process patterns to Acme Advisory operations:
    - BPI loan application -> Acme client engagement
    - BPI approval stages -> Acme proposal/SOW stages
    - BPI resource patterns -> Acme staff patterns
    """

    # Mapping BPI activities to Acme workflows
    ACTIVITY_WORKFLOW_MAP = {
        # Application activities -> Proposal workflow (W2)
        "A_Create Application": "W2",
        "A_Submitted": "W2",
        "A_SUBMITTED": "W2",
        "A_PARTLYSUBMITTED": "W2",
        "A_PREACCEPTED": "W2",

        # Validation activities -> Vendor workflow (W4)
        "W_Validate application": "W4",
        "W_Valideren aanvraag": "W4",

        # Follow-up activities -> Billing workflow (W5)
        "W_Call after offers": "W5",
        "W_Nabellen offertes": "W5",

        # Completion activities -> Staffing workflow (W3)
        "W_Complete application": "W3",
        "W_Completeren aanvraag": "W3",
        "W_Handle leads": "W3",
    }

    def __init__(self, loader: Optional[BPILoader] = None):
        """
        Initialize calibrator.

        Args:
            loader: BPI data loader (uses default if None)
        """
        self.loader = loader or get_default_loader()
        self._timing_cache: Optional[TimingCalibration] = None
        self._resource_cache: Optional[ResourceCalibration] = None
        self._workflow_cache: Optional[WorkflowCalibration] = None

    def calibrate_timing(
        self,
        dataset_name: str = "BPI2012",
        scale_factor: float = 0.001,
    ) -> TimingCalibration:
        """
        Extract timing calibration from BPI data.

        Args:
            dataset_name: BPI dataset to use
            scale_factor: Scale BPI event counts to Acme size

        Returns:
            TimingCalibration with hourly/daily weights and gap percentiles
        """
        if self._timing_cache:
            return self._timing_cache

        timing_data = self.loader.get_timing_distribution(dataset_name)

        # Calculate gap percentiles
        gaps = sorted(timing_data["inter_event_gaps_hours"])
        if gaps:
            n = len(gaps)
            gap_p25 = gaps[int(n * 0.25)]
            gap_p50 = gaps[int(n * 0.50)]
            gap_p75 = gaps[int(n * 0.75)]
            gap_p95 = gaps[int(n * 0.95)]
        else:
            gap_p25, gap_p50, gap_p75, gap_p95 = 0.5, 2.0, 8.0, 48.0

        # Scale events to Acme size (90 person firm)
        # BPI has ~5000 events/week, Acme targets ~150
        bpi_weekly = timing_data["avg_events_per_week"]
        scaled_weekly = int(bpi_weekly * scale_factor * 30)  # Target ~150

        self._timing_cache = TimingCalibration(
            hourly_weights=timing_data["hourly_weights"],
            daily_weights=timing_data["daily_weights"],
            gap_p25=gap_p25,
            gap_p50=gap_p50,
            gap_p75=gap_p75,
            gap_p95=gap_p95,
            events_per_week=min(scaled_weekly, 200),  # Cap at 200
        )

        return self._timing_cache

    def calibrate_resources(
        self,
        dataset_name: str = "BPI2012",
    ) -> ResourceCalibration:
        """
        Extract resource behavior calibration from BPI data.

        Returns:
            ResourceCalibration with specialization and workload patterns
        """
        if self._resource_cache:
            return self._resource_cache

        resource_data = self.loader.get_resource_patterns(dataset_name)

        self._resource_cache = ResourceCalibration(
            avg_specialization=resource_data["avg_specialization"],
            workload_gini=resource_data["workload_gini"],
        )

        return self._resource_cache

    def calibrate_workflows(
        self,
        dataset_name: str = "BPI2012",
    ) -> WorkflowCalibration:
        """
        Map BPI activities to Acme workflows and extract complexity.

        Returns:
            WorkflowCalibration with activity mappings and complexity
        """
        if self._workflow_cache:
            return self._workflow_cache

        dataset = self.loader.load_dataset(dataset_name)

        # Count activities per workflow
        workflow_counts: Dict[str, int] = {"W2": 0, "W3": 0, "W4": 0, "W5": 0}
        total = 0

        for activity, count in dataset.activity_counts.items():
            workflow = self.ACTIVITY_WORKFLOW_MAP.get(activity, "W3")  # Default to W3
            workflow_counts[workflow] += count
            total += count

        # Calculate relative complexity (based on event frequency)
        workflow_complexity = {}
        for wf, count in workflow_counts.items():
            workflow_complexity[wf] = count / total if total > 0 else 0.25

        # Events per case (derived from BPI statistics)
        events_per_case = {
            "W2": 8.0,   # Proposal workflow - moderate
            "W3": 12.0,  # Staffing workflow - high (matching, scheduling)
            "W4": 6.0,   # Vendor workflow - lower
            "W5": 10.0,  # Billing workflow - moderate-high
        }

        self._workflow_cache = WorkflowCalibration(
            activity_workflow_map=self.ACTIVITY_WORKFLOW_MAP,
            workflow_complexity=workflow_complexity,
            events_per_case=events_per_case,
        )

        return self._workflow_cache

    def get_full_calibration(
        self,
        dataset_name: str = "BPI2012",
    ) -> Dict[str, any]:
        """
        Get complete calibration data for simulation.

        Returns:
            Dict with timing, resource, and workflow calibrations
        """
        return {
            "timing": self.calibrate_timing(dataset_name),
            "resources": self.calibrate_resources(dataset_name),
            "workflows": self.calibrate_workflows(dataset_name),
            "source_dataset": dataset_name,
        }

    def sample_event_hour(self, seed: Optional[int] = None) -> int:
        """
        Sample an event hour based on calibrated distribution.

        Returns:
            Hour (0-23) sampled from BPI hourly distribution
        """
        timing = self.calibrate_timing()
        rng = random.Random(seed)

        hours = list(timing.hourly_weights.keys())
        weights = [timing.hourly_weights.get(h, 0.01) for h in hours]

        return rng.choices(hours, weights=weights, k=1)[0]

    def sample_event_day(self, seed: Optional[int] = None) -> int:
        """
        Sample an event weekday based on calibrated distribution.

        Returns:
            Weekday (0=Mon, 6=Sun) sampled from BPI daily distribution
        """
        timing = self.calibrate_timing()
        rng = random.Random(seed)

        days = list(timing.daily_weights.keys())
        weights = [timing.daily_weights.get(d, 0.1) for d in days]

        return rng.choices(days, weights=weights, k=1)[0]

    def sample_inter_event_gap(self, seed: Optional[int] = None) -> float:
        """
        Sample an inter-event gap based on calibrated distribution.

        Returns:
            Gap in hours, sampled from lognormal fit to BPI data
        """
        timing = self.calibrate_timing()
        rng = random.Random(seed)

        # Use percentiles to fit a lognormal distribution
        # Log of median = mu, spread determines sigma
        mu = math.log(timing.gap_p50)
        sigma = (math.log(timing.gap_p75) - math.log(timing.gap_p25)) / 1.35

        gap = rng.lognormvariate(mu, sigma)

        # Cap at reasonable maximum
        return min(gap, timing.gap_p95 * 2)

    def get_workflow_probability(self, workflow_id: str) -> float:
        """
        Get probability of event belonging to a workflow.

        Returns:
            Probability (0-1) based on BPI activity distribution
        """
        workflows = self.calibrate_workflows()
        return workflows.workflow_complexity.get(workflow_id, 0.25)


def get_default_calibrator() -> BPICalibrator:
    """Get a calibrator with default settings."""
    return BPICalibrator()
