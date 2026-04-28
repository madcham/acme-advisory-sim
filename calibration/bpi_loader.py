"""
BPI Challenge Data Loader.

Loads and parses BPI Challenge 2012/2017 datasets for calibration.
These datasets provide real-world process mining data from financial services.

BPI Challenge 2012: Loan application process
BPI Challenge 2017: Loan application process (extended)

Data source: https://data.4tu.nl/

Features:
- Automatic download from 4TU.ResearchData (optional, non-blocking)
- Local caching in .cache/bpi_data/
- Silent fallback to synthetic calibration if download fails
- Calibration report logging which data source was used
"""

import os
import csv
import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Iterator
from pathlib import Path
import random
import hashlib
import logging

# Set up logging for calibration reporting
logger = logging.getLogger("bpi_loader")


@dataclass
class CalibrationReport:
    """Report on which calibration data source was used."""
    dataset_name: str
    source: str  # "real_data", "synthetic", "cached"
    source_path: Optional[str] = None
    download_attempted: bool = False
    download_succeeded: bool = False
    download_error: Optional[str] = None
    events_loaded: int = 0
    cases_loaded: int = 0
    activities_found: int = 0

    def to_dict(self) -> Dict:
        return {
            "dataset": self.dataset_name,
            "source": self.source,
            "source_path": self.source_path,
            "download_attempted": self.download_attempted,
            "download_succeeded": self.download_succeeded,
            "download_error": self.download_error,
            "events_loaded": self.events_loaded,
            "cases_loaded": self.cases_loaded,
            "activities_found": self.activities_found,
        }

    def __str__(self) -> str:
        lines = [
            f"BPI Calibration Report: {self.dataset_name}",
            f"  Source: {self.source}",
        ]
        if self.source_path:
            lines.append(f"  Path: {self.source_path}")
        if self.download_attempted:
            status = "SUCCESS" if self.download_succeeded else f"FAILED ({self.download_error})"
            lines.append(f"  Download: {status}")
        if self.events_loaded > 0:
            lines.append(f"  Events: {self.events_loaded:,}")
            lines.append(f"  Cases: {self.cases_loaded:,}")
            lines.append(f"  Activities: {self.activities_found}")
        return "\n".join(lines)


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
    source: str = "synthetic"  # "real_data", "synthetic", "cached"
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

    # Calibration report
    calibration_report: Optional[CalibrationReport] = None

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
                if event.hour_of_day is not None:
                    self.hourly_distribution[event.hour_of_day] = \
                        self.hourly_distribution.get(event.hour_of_day, 0) + 1
                if event.day_of_week is not None:
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

    Supports:
    1. Automatic download from 4TU.ResearchData (optional, non-blocking)
    2. Loading from local CSV/XES files
    3. Fallback to synthetic distributions based on published statistics

    Download is attempted once per session and cached locally.
    """

    # Download URLs for BPI Challenge datasets
    # Primary: BPI 2019 CSV (Purchase-to-Pay, 38MB, maps to W4/W5)
    # Note: 4TU URLs change frequently. If downloads fail, data can be manually
    # downloaded from https://data.4tu.nl and placed in .cache/bpi_data/
    #
    # Manual download instructions:
    # 1. Visit https://data.4tu.nl/articles/dataset/BPI_Challenge_2019/12715853
    # 2. Download the CSV version (~38MB)
    # 3. Save as .cache/bpi_data/BPI2019.csv
    DOWNLOAD_URLS = {
        "BPI2019": [
            # 4TU.ResearchData - try multiple URL formats
            ("csv", "https://data.4tu.nl/ndownloader/files/24045793"),  # Direct file ID
            ("csv", "https://data.4tu.nl/file/d06aff4b-79f0-45e6-8ec8-e19730c248f1/BPI_Challenge_2019.csv"),
            ("csv", "https://data.4tu.nl/datasets/d06aff4b-79f0-45e6-8ec8-e19730c248f1/1"),
        ],
        "BPI2017": [
            ("xes", "https://data.4tu.nl/ndownloader/files/24045802"),
        ],
        # Legacy mapping - redirect to BPI2019 which has better coverage
        "BPI2012": "BPI2019",
    }

    # Expected file sizes for validation (approximate, in bytes)
    EXPECTED_SIZES = {
        "BPI2019": 38_000_000,  # ~38MB CSV
        "BPI2017": 100_000_000,  # ~100MB XES compressed
    }

    # Published statistics from BPI Challenge papers
    # BPI 2019: Purchase-to-Pay process (maps well to vendor/billing workflows)
    BPI_2019_STATS = {
        "total_cases": 251734,
        "total_events": 1595923,
        "avg_events_per_case": 6.34,
        "avg_case_duration_days": 45.2,
        "num_activities": 42,
        "num_resources": 627,
        "top_activities": [
            ("Record Invoice Receipt", 0.158),
            ("Record Goods Receipt", 0.158),
            ("Clear Invoice", 0.130),
            ("Record Service Entry Sheet", 0.078),
            ("Vendor creates invoice", 0.065),
            ("Create Purchase Order Item", 0.052),
        ],
        "hourly_peak": 10,  # 10 AM peak activity
        "weekday_weights": [0.19, 0.21, 0.21, 0.20, 0.17, 0.02, 0.00],
    }

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

    def __init__(
        self,
        data_dir: Optional[str] = None,
        cache_dir: Optional[str] = None,
        auto_download: bool = True,
        download_timeout: int = 60,
    ):
        """
        Initialize loader.

        Args:
            data_dir: Directory containing BPI Challenge files (CSV/XES).
                     If None, will try cache_dir or auto-download.
            cache_dir: Directory for caching downloaded files.
                      Defaults to .cache/bpi_data/ in project root.
            auto_download: Whether to attempt downloading if data not found.
            download_timeout: Timeout in seconds for download attempts.
        """
        self.data_dir = Path(data_dir) if data_dir else None
        self.auto_download = auto_download
        self.download_timeout = download_timeout

        # Set up cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Use .cache/bpi_data/ relative to this file's location
            module_dir = Path(__file__).parent.parent
            self.cache_dir = module_dir / ".cache" / "bpi_data"

        self._cached_datasets: Dict[str, BPIDataset] = {}
        self._calibration_reports: Dict[str, CalibrationReport] = {}
        self._download_attempted: Dict[str, bool] = {}

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, name: str, fmt: str = "csv") -> Path:
        """Get the cache file path for a dataset."""
        ext = ".csv" if fmt == "csv" else ".xes.gz"
        return self.cache_dir / f"{name}{ext}"

    def _resolve_dataset_name(self, name: str) -> str:
        """Resolve dataset name aliases (e.g., BPI2012 -> BPI2019)."""
        urls = self.DOWNLOAD_URLS.get(name)
        if isinstance(urls, str):
            # It's an alias, resolve it
            return urls
        return name

    def _download_dataset(self, name: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Attempt to download a BPI Challenge dataset.

        Tries multiple URLs in order until one succeeds.

        Returns:
            Tuple of (success, error_message, format_downloaded)
        """
        # Resolve aliases
        resolved_name = self._resolve_dataset_name(name)

        if resolved_name not in self.DOWNLOAD_URLS:
            return False, f"Unknown dataset: {name}", None

        urls = self.DOWNLOAD_URLS[resolved_name]
        if isinstance(urls, str):
            # Double alias, shouldn't happen
            return False, f"Invalid dataset configuration: {name}", None

        import urllib.request
        import urllib.error
        import socket

        self._ensure_cache_dir()

        last_error = None
        for fmt, url in urls:
            try:
                cache_path = self._get_cache_path(resolved_name, fmt)

                logger.info(f"Downloading {resolved_name} ({fmt}) from {url}...")

                # Create request with timeout
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "AcmeAdvisorySim/1.0 (academic research)",
                        "Accept": "text/csv,application/xml,*/*",
                    }
                )

                # Download with timeout
                with urllib.request.urlopen(request, timeout=self.download_timeout) as response:
                    # Check content length if available
                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        size = int(content_length)
                        logger.info(f"  Downloading {size / 1_000_000:.1f} MB...")

                    # Read and save
                    data = response.read()

                    # Validate we got something reasonable
                    if len(data) < 1000:
                        last_error = f"Downloaded file too small ({len(data)} bytes)"
                        continue

                    # Save to cache
                    with open(cache_path, 'wb') as f:
                        f.write(data)

                    logger.info(f"  Saved to {cache_path} ({len(data) / 1_000_000:.1f} MB)")
                    return True, None, fmt

            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                logger.debug(f"  Failed: {last_error}")
                continue
            except urllib.error.URLError as e:
                last_error = f"URL error: {e.reason}"
                logger.debug(f"  Failed: {last_error}")
                continue
            except socket.timeout:
                last_error = f"Timeout after {self.download_timeout}s"
                logger.debug(f"  Failed: {last_error}")
                continue
            except Exception as e:
                last_error = f"Error: {str(e)}"
                logger.debug(f"  Failed: {last_error}")
                continue

        return False, last_error or "All download attempts failed", None

    def _load_from_xes(self, path: Path, name: str) -> Optional[BPIDataset]:
        """
        Load dataset from XES (XML Event Stream) file.

        XES is the standard format for process mining event logs.
        """
        try:
            dataset = BPIDataset(name=name, source="real_data")
            cases: Dict[str, BPICase] = {}

            # Handle gzipped files
            open_func = gzip.open if str(path).endswith('.gz') else open

            with open_func(path, 'rt', encoding='utf-8') as f:
                # Parse XML incrementally to handle large files
                context = ET.iterparse(f, events=['end'])

                current_case_id = None
                current_events = []

                for event, elem in context:
                    tag = elem.tag.split('}')[-1]  # Remove namespace

                    if tag == 'trace':
                        # Extract case ID from trace attributes
                        case_id = None
                        for attr in elem:
                            attr_tag = attr.tag.split('}')[-1]
                            if attr_tag == 'string' and attr.get('key') == 'concept:name':
                                case_id = attr.get('value')
                                break

                        if case_id and current_events:
                            cases[case_id] = BPICase(
                                case_id=case_id,
                                events=current_events.copy()
                            )
                            current_events = []

                        current_case_id = case_id
                        elem.clear()  # Free memory

                    elif tag == 'event' and current_case_id:
                        # Parse event attributes
                        activity = None
                        timestamp = None
                        resource = None
                        lifecycle = None

                        for attr in elem:
                            attr_tag = attr.tag.split('}')[-1]
                            key = attr.get('key', '')
                            value = attr.get('value', '')

                            if attr_tag == 'string':
                                if key == 'concept:name':
                                    activity = value
                                elif key == 'org:resource':
                                    resource = value
                                elif key == 'lifecycle:transition':
                                    lifecycle = value
                            elif attr_tag == 'date' and key == 'time:timestamp':
                                try:
                                    # Parse ISO timestamp
                                    ts_str = value.replace('Z', '+00:00')
                                    timestamp = datetime.fromisoformat(ts_str)
                                except:
                                    pass

                        if activity and timestamp:
                            bpi_event = BPIEvent(
                                case_id=current_case_id,
                                activity=activity,
                                timestamp=timestamp,
                                resource=resource,
                                lifecycle=lifecycle,
                                day_of_week=timestamp.weekday(),
                                hour_of_day=timestamp.hour,
                            )
                            current_events.append(bpi_event)

                        elem.clear()

            # Add any remaining case
            if current_case_id and current_events:
                cases[current_case_id] = BPICase(
                    case_id=current_case_id,
                    events=current_events
                )

            dataset.cases = list(cases.values())

            if not dataset.cases:
                return None

            dataset.compute_distributions()
            return dataset

        except Exception as e:
            logger.debug(f"Failed to parse XES file {path}: {e}")
            return None

    def _load_from_csv(self, path: Path, name: str) -> Optional[BPIDataset]:
        """
        Load dataset from CSV file.

        Handles multiple CSV formats:
        - BPI 2019: case, eventTime, event, resource, etc.
        - Standard XES export: Case ID, Activity, Complete Timestamp, Resource
        """
        try:
            dataset = BPIDataset(name=name, source="real_data")
            cases: Dict[str, BPICase] = {}

            open_func = gzip.open if str(path).endswith('.gz') else open

            with open_func(path, 'rt', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # Detect column names from first row
                fieldnames = reader.fieldnames or []

                # Map possible column names
                case_cols = ['case', 'Case ID', 'case:concept:name', 'CaseID']
                activity_cols = ['event', 'Activity', 'concept:name', 'activity']
                time_cols = ['eventTime', 'Complete Timestamp', 'time:timestamp', 'timestamp', 'startTime']
                resource_cols = ['resource', 'Resource', 'org:resource', 'user']

                def find_col(candidates):
                    for c in candidates:
                        if c in fieldnames:
                            return c
                    return None

                case_col = find_col(case_cols)
                activity_col = find_col(activity_cols)
                time_col = find_col(time_cols)
                resource_col = find_col(resource_cols)

                if not case_col or not activity_col:
                    logger.debug(f"Could not find required columns in {path}. Found: {fieldnames}")
                    return None

                row_count = 0
                for row in reader:
                    row_count += 1

                    case_id = row.get(case_col, '')
                    activity = row.get(activity_col, '')

                    if not case_id or not activity:
                        continue

                    # Parse timestamp
                    timestamp = None
                    if time_col:
                        ts_str = row.get(time_col, '')
                        if ts_str:
                            try:
                                # Handle various timestamp formats
                                ts_str = ts_str.replace('Z', '+00:00')
                                if 'T' in ts_str:
                                    timestamp = datetime.fromisoformat(ts_str)
                                else:
                                    # Try common formats
                                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%d-%m-%Y %H:%M:%S']:
                                        try:
                                            timestamp = datetime.strptime(ts_str, fmt)
                                            break
                                        except:
                                            pass
                            except:
                                pass

                    # Use a default timestamp if parsing failed
                    if timestamp is None:
                        timestamp = datetime(2019, 1, 1, 10, 0, 0)  # Default for synthetic

                    resource = row.get(resource_col, None) if resource_col else None

                    event = BPIEvent(
                        case_id=case_id,
                        activity=activity,
                        timestamp=timestamp,
                        resource=resource,
                        lifecycle='complete',
                        day_of_week=timestamp.weekday(),
                        hour_of_day=timestamp.hour,
                    )

                    if case_id not in cases:
                        cases[case_id] = BPICase(case_id=case_id)
                    cases[case_id].events.append(event)

                    # Limit for very large files (sample first 500k rows)
                    if row_count >= 500000:
                        logger.info(f"  Sampled {row_count} rows (file truncated for performance)")
                        break

            dataset.cases = list(cases.values())

            if not dataset.cases:
                return None

            logger.info(f"  Loaded {len(dataset.cases)} cases, {row_count} events from CSV")
            dataset.compute_distributions()
            return dataset

        except Exception as e:
            logger.debug(f"Failed to parse CSV file {path}: {e}")
            return None

    def _generate_synthetic(self, name: str) -> BPIDataset:
        """
        Generate synthetic dataset based on published statistics.

        Creates realistic distributions without requiring actual data files.
        """
        # Select appropriate stats based on dataset name
        if name == "BPI2019":
            stats = self.BPI_2019_STATS
        elif name == "BPI2017":
            stats = self.BPI_2017_STATS
        else:
            # Default to BPI2019 (Purchase-to-Pay) for better workflow coverage
            stats = self.BPI_2019_STATS

        dataset = BPIDataset(name=name, source="synthetic")

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

    def load_dataset(self, name: str = "BPI2012") -> BPIDataset:
        """
        Load a BPI Challenge dataset.

        Tries in order:
        1. Return cached dataset if already loaded
        2. Load from data_dir if provided
        3. Load from cache_dir if exists
        4. Download from 4TU.ResearchData if auto_download enabled
        5. Fall back to synthetic generation

        Args:
            name: "BPI2012", "BPI2017", or "BPI2019"

        Returns:
            BPIDataset with distributions computed
        """
        # Resolve aliases (e.g., BPI2012 -> BPI2019)
        resolved_name = self._resolve_dataset_name(name)

        if resolved_name in self._cached_datasets:
            return self._cached_datasets[resolved_name]

        report = CalibrationReport(dataset_name=name, source="synthetic")
        if resolved_name != name:
            report.dataset_name = f"{name} (using {resolved_name})"

        dataset = None

        # Try 1: Load from explicit data_dir
        if self.data_dir:
            for ext in ['.csv', '.csv.gz', '.xes.gz', '.xes']:
                path = self.data_dir / f"{resolved_name}{ext}"
                if path.exists():
                    if '.xes' in ext:
                        dataset = self._load_from_xes(path, resolved_name)
                    else:
                        dataset = self._load_from_csv(path, resolved_name)

                    if dataset:
                        report.source = "real_data"
                        report.source_path = str(path)
                        break

        # Try 2: Load from cache (try CSV first, then XES)
        if not dataset:
            for fmt in ['csv', 'xes']:
                cache_path = self._get_cache_path(resolved_name, fmt)
                if cache_path.exists():
                    if fmt == 'csv':
                        dataset = self._load_from_csv(cache_path, resolved_name)
                    else:
                        dataset = self._load_from_xes(cache_path, resolved_name)

                    if dataset:
                        report.source = "cached"
                        report.source_path = str(cache_path)
                        break

        # Try 3: Download (non-blocking, tries multiple URLs)
        if not dataset and self.auto_download and resolved_name not in self._download_attempted:
            self._download_attempted[resolved_name] = True
            report.download_attempted = True

            success, error, fmt = self._download_dataset(resolved_name)
            report.download_succeeded = success
            report.download_error = error

            if success and fmt:
                cache_path = self._get_cache_path(resolved_name, fmt)
                if fmt == 'csv':
                    dataset = self._load_from_csv(cache_path, resolved_name)
                else:
                    dataset = self._load_from_xes(cache_path, resolved_name)

                if dataset:
                    report.source = "real_data"
                    report.source_path = str(cache_path)

        # Fallback: Synthetic (always succeeds, never blocks)
        if not dataset:
            dataset = self._generate_synthetic(resolved_name)
            report.source = "synthetic"
            report.source_path = None

        # Populate report
        report.events_loaded = sum(dataset.activity_counts.values())
        report.cases_loaded = len(dataset.cases)
        report.activities_found = len(dataset.activity_counts)

        dataset.calibration_report = report
        self._calibration_reports[name] = report
        self._cached_datasets[resolved_name] = dataset

        # Log the calibration path taken
        logger.info(str(report))

        return dataset

    def get_calibration_report(self, name: str = "BPI2012") -> Optional[CalibrationReport]:
        """Get the calibration report for a dataset."""
        if name not in self._calibration_reports:
            self.load_dataset(name)
        return self._calibration_reports.get(name)

    def get_timing_distribution(self, dataset_name: str = "BPI2012") -> Dict[str, any]:
        """
        Get timing distributions for calibration.

        Returns dict with:
        - hourly_weights: Probability of event at each hour
        - daily_weights: Probability of event on each weekday
        - inter_event_gaps: Sample of inter-event gap durations
        - source: Which data source was used
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
            "source": dataset.source,
        }

    def get_resource_patterns(self, dataset_name: str = "BPI2012") -> Dict[str, any]:
        """
        Get resource behavior patterns for calibration.

        Returns dict with:
        - specialization: How focused resources are on specific activities
        - workload_distribution: How evenly work is distributed
        - source: Which data source was used
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
            "source": dataset.source,
        }


def get_default_loader() -> BPILoader:
    """Get a BPI loader with default settings (auto-download enabled)."""
    return BPILoader(auto_download=True)
