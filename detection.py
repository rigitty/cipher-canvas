"""Compatibility proxy for cipher_engine.analysis.detection."""

from cipher_engine.analysis.detection import (
    analyze_image,
    change_locations,
    deviation_from_baseline,
    generate_lsb_plane,
    pov_chisq_per_df,
    pov_profile,
    report,
)

__all__ = [
    "analyze_image",
    "change_locations",
    "deviation_from_baseline",
    "generate_lsb_plane",
    "pov_chisq_per_df",
    "pov_profile",
    "report",
]
