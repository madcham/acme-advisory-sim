"""
BPI Challenge Data Loader.

Loads and parses BPI Challenge 2012/2017 datasets for calibration.
These datasets provide real-world process mining data from financial services.

BPI Challenge 2012: Loan application process
BPI Challenge 2017: Loan application process (extended)

Data source: https://data.4tu.nl/
"""

import os
import csv
import gzip
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Iterator
from pathlib import Path
import random


@dataclass
class BPIEvent:
    """A single event from BPI Challenge data."""
    case_id: str
    activity: str
    timestamp: datetime
    resource: Optional[str] = None
    lifecycle: Optional[str] = None  # start, complete, etc.

    # Derived fields
    duration_hours: Optional[float] = None
    day_of_week: Optional[int] = None
    hour_of_day: Optional[int] = None


@dataclass
class BPICase:
    """A complete case (process instance) from BPI data."""
    case_id: str
    events: List[BPIEvent] = field(default_factory=list)

    # Derived metrics
    total_duration_hours: Optional[float] = None
    num_events: int = 0
    num_resources: int = 0

    def compute_metrics(self):
        """Compute derived metrics from events."""
        if not self.events:
            return

        self.num_events = len(self.events)

        # Sort events by timestamp
        sorted_events = sorted(self.events, key=lambda e: e.timestamp)

        # Total duration
        if len(sorted_events) >= 2:
            delta = sorted_events[-1].timestamp - sorted_events[0].timestamp
            self.total_duration_hours = delta.total_seconds() / 3600

        # Unique resources
        resources = set(e.resource for e in self.events if e.resource)
        self.num_resources = len(resources)


@dataclass
class BPIDataset:
    """Loaded BPI Challenge dataset with computed distributions."""
    name: str
    cases: List[BPICase] = field(default_factory=list)

    # Activity distributions
    activity_counts: Dict[str, int] = field(default_factory=dict)
    activity_durations: Dict[str, List[float]] = field(default_factory=dict)

    # Temporal distributions
    hourly_distribution: Dict[int, int] = field(default_factory=dict)
    daily_distribution: Dict[int, int] = field(default_factory=dict)

    # Resource patterns
    resource_activity_map: Dict[str, List[str]] = field(default_factory=dict)
    resource_case_counts: Dict[str, int] = field(default_factory=dict)

    # Inter-event timing
    inter_event_gaps_hours: List[float] = field(default_factory=list)

    def compute_distributions(self):
        """Compute all distributions from loaded cases."""
        for case in self.cases:
            case.compute_metrics()

            prev_event = None
            for event in sorted(case.events, key=lambda e: e.timestamp):
                # Activity counts
                self.activity_counts[event.activity] = \
                    self.activity_counts.get(event.activity, 0) + 1

                # Temporal distributions
                self.hourly_distribution[event.hour_of_day] = \
                    self.hourly_distribution.get(event.hour_of_day, 0) + 1
                self.daily_distribution[event.day_of_week] = \
                    self.daily_distribution.get(event.day_of_week, 0) + 1

                # Resource patterns
                if event.resource:
                    if event.resource not in self.resource_activity_map:
                        self.resource_activity_map[event.resource] = []
                    self.resource_activity_map[event.resource].append(event.activity)

                    self.resource_case_counts[event.resource] = \
                        self.resource_case_counts.get(event.resource, 0) + 1

                # Inter-event gaps
                if prev_event:
                    gap = (event.timestamp - prev_event.timestamp).total_seconds() / 3600
                    if 0 < gap < 720:  # Cap at 30 days
                        self.inter_event_gaps_hours.append(gap)

                prev_event = event


class BPILoader:
    """
    Loader for BPI Challenge datasets.

    Supports loading from CSV/XES files or generating synthetic
    distributions based on published statistics when data unavailable.
    """

    # Published statistics from BPI Challenge papers
    BPI_2012_STATS = {
        "total_cases": 13087,
        "total_events": 262200,
        "avg_events_per_case": 20.04,
        "avg_case_duration_days": 8.62,
        "num_activities": 24,
        "num_resources": 69,
        "top_activities": [
            ("A_SUBMITTED", 0.05),
            ("A_PARTLYSUBMITTED", 0.05),
            ("A_PREACCEPTED", 0.05),
            ("W_Completeren aanvraag", 0.15),
            ("W_Nabellen offertes", 0.12),
            ("W_Valideren aanvraag", 0.08),
        ],
        "hourly_peak": 10,  # 10 AM peak activity
        "weekday_weights": [0.18, 0.20, 0.20, 0.20, 0.18, 0.03, 0.01],
    }

    BPI_2017_STATS = {
        "total_cases": 31509,
        "total_events": 1202267,
        "avg_events_per_case": 38.15,
        "avg_case_duration_days": 22.27,
        "num_activities": 26,
        "num_resources": 145,
        "top_activities": [
            ("A_Create Application", 0.026),
            ("A_Submitted", 0.026),
            ("W_Handle leads", 0.089),
            ("W_Complete application", 0.132),
            ("W_Call after offers", 0.156),
            ("W_Validate application", 0.048),
        ],
        "hourly_peak": 11,  # 11 AM peak activity
        "weekday_weights": [0.17, 0.19, 0.20, 0.20, 0.19, 0.04, 0.01],
    }

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize loader.

        Args:
            data_dir: Directory containing BPI Challenge CSV files.
                     If None, uses synthetic distributions.
        """
        self.data_dir = Path(data_dir) if data_dir else None
        self._cached_datasets: Dict[str, BPIDataset] = {}

    def load_dataset(self, name: str = "BPI2012") -> BPIDataset:
        """
        Load a BPI Challenge dataset.

        Args:
            name: "BPI2012" or "BPI2017"

        Returns:
            BPIDataset with distributions computed
        """
        if name in self._cached_datasets:
            return self._cached_datasets[name]

        # Try to load from file
        if self.data_dir:
            csv_path = self.data_dir / f"{name}.csv"
            if csv_path.exists():
                dataset = self._load_from_csv(csv_path, name)
                self._cached_datasets[name] = dataset
                return dataset

        # Fall back to synthetic generation
        dataset = self._generate_synthetic(name)
        self._cached_datasets[name] = dataset
        return dataset

    def _load_from_csv(self, path: Path, name: str) -> BPIDataset:
        """Load dataset from CSV file."""
        dataset = BPIDataset(name=name)
        cases: Dict[str, BPICase] = {}

        open_func = gzip.open if str(path).endswith('.gz') else open

        with open_func(path, 'rt', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                case_id = row.get('Case ID', row.get('case:concept:name', ''))
                activity = row.get('Activity', row.get('concept:name', ''))

                # Parse timestamp
                ts_str = row.get('Complete Timestamp', row.get('time:timestamp', ''))
                try:
                    timestamp = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                except:
                    continue

                resource = row.get('Resource', row.get('org:resource', None))
                lifecycle = row.get('lifecycle:transition', 'complete')

                event = BPIEvent(
                    case_id=case_id,
                    activity=activity,
                    timestamp=timestamp,
                    resource=resource,
                    lifecycle=lifecycle,
                    day_of_week=timestamp.weekday(),
                    hour_of_day=timestamp.hour,
                )

                if case_id not in cases:
                    cases[case_id] = BPICase(case_id=case_id)
                cases[case_id].events.append(event)

        dataset.cases = list(cases.values())
        dataset.compute_distributions()

        return dataset

    def _generate_synthetic(self, name: str) -> BPIDataset:
        """
        Generate synthetic dataset based on published statistics.

        Creates realistic distributions without requiring actual data files.
        """
        stats = self.BPI_2012_STATS if name == "BPI2012" else self.BPI_2017_STATS
        dataset = BPIDataset(name=name)

        # Generate activity counts
        for activity, freq in stats["top_activities"]:
            dataset.activity_counts[activity] = int(stats["total_events"] * freq)

        # Distribute remaining events across generic activities
        remaining = stats["total_events"] - sum(dataset.activity_counts.values())
        other_activities = stats["num_activities"] - len(stats["top_activities"])
        per_other = remaining // max(1, other_activities)

        for i in range(other_activities):
            dataset.activity_counts[f"Activity_{i+1}"] = per_other

        # Generate hourly distribution (bell curve around peak)
        peak = stats["hourly_peak"]
        for hour in range(24):
            # Gaussian-ish distribution
            diff = abs(hour - peak)
            if hour < 6 or hour > 20:
                weight = 0.01
            else:
                weight = max(0.01, 1.0 - (diff / 12) ** 2)
            dataset.hourly_distribution[hour] = int(stats["total_events"] * weight / 24)

        # Generate daily distribution
        for day, weight in enumerate(stats["weekday_weights"]):
            dataset.daily_distribution[day] = int(stats["total_events"] * weight)

        # Generate inter-event gaps (lognormal-ish)
        # Most events happen within hours, some take days
        random.seed(42)
        for _ in range(min(10000, stats["total_events"] // 10)):
            # Mix of quick (minutes) and slow (hours/days) gaps
            if random.random() < 0.6:
                gap = random.expovariate(1/0.5)  # Mean 30 min
            elif random.random() < 0.8:
                gap = random.expovariate(1/4)  # Mean 4 hours
            else:
                gap = random.expovariate(1/24)  # Mean 1 day
            dataset.inter_event_gaps_hours.append(min(gap, 720))

        # Generate resource patterns
        for i in range(stats["num_resources"]):
            resource = f"Resource_{i+1}"
            # Each resource handles 2-5 activity types
            num_activities = random.randint(2, 5)
            activities = random.sample(list(dataset.activity_counts.keys()),
                                       min(num_activities, len(dataset.activity_counts)))
            dataset.resource_activity_map[resource] = activities
            dataset.resource_case_counts[resource] = \
                stats["total_cases"] // stats["num_resources"]

        return dataset

    def get_timing_distribution(self, dataset_name: str = "BPI2012") -> Dict[str, any]:
        """
        Get timing distributions for calibration.

        Returns dict with:
        - hourly_weights: Probability of event at each hour
        - daily_weights: Probability of event on each weekday
        - inter_event_gaps: Sample of inter-event gap durations
        """
        dataset = self.load_dataset(dataset_name)

        # Normalize hourly distribution
        total_hourly = sum(dataset.hourly_distribution.values()) or 1
        hourly_weights = {h: c/total_hourly
                         for h, c in dataset.hourly_distribution.items()}

        # Normalize daily distribution
        total_daily = sum(dataset.daily_distribution.values()) or 1
        daily_weights = {d: c/total_daily
                        for d, c in dataset.daily_distribution.items()}

        return {
            "hourly_weights": hourly_weights,
            "daily_weights": daily_weights,
            "inter_event_gaps_hours": dataset.inter_event_gaps_hours,
            "avg_events_per_week": sum(dataset.activity_counts.values()) / 52,
        }

    def get_resource_patterns(self, dataset_name: str = "BPI2012") -> Dict[str, any]:
        """
        Get resource behavior patterns for calibration.

        Returns dict with:
        - specialization: How focused resources are on specific activities
        - workload_distribution: How evenly work is distributed
        """
        dataset = self.load_dataset(dataset_name)

        # Calculate specialization (entropy of activity distribution per resource)
        specializations = []
        for resource, activities in dataset.resource_activity_map.items():
            # Lower entropy = more specialized
            unique = len(set(activities))
            total = len(activities) or 1
            specializations.append(unique / total)

        # Calculate workload distribution (Gini coefficient approximation)
        counts = list(dataset.resource_case_counts.values())
        if counts:
            counts.sort()
            n = len(counts)
            total = sum(counts) or 1
            gini = sum((2*i - n - 1) * c for i, c in enumerate(counts, 1)) / (n * total)
        else:
            gini = 0

        return {
            "avg_specialization": sum(specializations) / len(specializations) if specializations else 0.5,
            "workload_gini": abs(gini),
            "num_resources": len(dataset.resource_activity_map),
            "resource_activity_map": dataset.resource_activity_map,
        }


def get_default_loader() -> BPILoader:
    """Get a BPI loader with default settings."""
    return BPILoader()
