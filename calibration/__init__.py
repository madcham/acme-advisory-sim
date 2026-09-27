"""
Calibration module for realism enhancement (v3.1).

Contains:
- BPI Challenge data loader and calibrator (structured exhaust timing)
- Enron email corpus loader and calibrator (behavioral exhaust patterns)
- Realism configuration
- Chaos engine

The dual-calibration approach:
1. BPI Challenge: Calibrates workflow timing and event sequencing
2. Enron Corpus: Calibrates behavioral communication patterns

This gives the simulation realistic "texture" based on:
- Real process mining data (BPI Challenge 2012)
- Real organizational communication (Enron 1998-2002)
"""

from calibration.bpi_loader import BPILoader, BPIDataset, get_default_loader
from calibration.bpi_calibrator import BPICalibrator, get_default_calibrator
from calibration.realism_config import (
    RealismConfig, ChaosConfig, BPICalibrationConfig,
    ChaosEvent, ChaosType,
    DEFAULT_REALISM_CONFIG, CHAOS_ENABLED_CONFIG, FULL_REALISM_CONFIG,
)
from calibration.chaos_engine import ChaosEngine, ChaosImpact
from calibration.enron_loader import EnronLoader, EnronEmail, KnowledgeTransferPattern
from calibration.enron_calibrator import (
    EnronCalibrator, BehavioralExhaustParameters, EnronCalibrationResult,
    calibrate_from_enron,
)

__all__ = [
    # BPI Challenge calibration
    "BPILoader",
    "BPIDataset",
    "BPICalibrator",
    "get_default_loader",
    "get_default_calibrator",
    # Enron calibration
    "EnronLoader",
    "EnronEmail",
    "KnowledgeTransferPattern",
    "EnronCalibrator",
    "BehavioralExhaustParameters",
    "EnronCalibrationResult",
    "calibrate_from_enron",
    # Realism configuration
    "RealismConfig",
    "ChaosConfig",
    "BPICalibrationConfig",
    "ChaosEvent",
    "ChaosType",
    "ChaosEngine",
    "ChaosImpact",
    "DEFAULT_REALISM_CONFIG",
    "CHAOS_ENABLED_CONFIG",
    "FULL_REALISM_CONFIG",
]
