"""
Calibration module for realism enhancement (v3.0).

Contains:
- BPI Challenge data loader and calibrator
- Realism configuration
- Chaos engine
"""

from calibration.bpi_loader import BPILoader, BPIDataset, get_default_loader
from calibration.bpi_calibrator import BPICalibrator, get_default_calibrator
from calibration.realism_config import (
    RealismConfig, ChaosConfig, BPICalibrationConfig,
    ChaosEvent, ChaosType,
    DEFAULT_REALISM_CONFIG, CHAOS_ENABLED_CONFIG, FULL_REALISM_CONFIG,
)
from calibration.chaos_engine import ChaosEngine, ChaosImpact

__all__ = [
    "BPILoader",
    "BPIDataset",
    "BPICalibrator",
    "get_default_loader",
    "get_default_calibrator",
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
