"""
tests/test_validation_audit_f4.py - Verification suite for Task F4
Tests:
1. data/known_hotspots.csv template structure and blank coordinates.
2. outputs/validation_audit.md presence and exact sections (a), (b), (c), and (d).
3. Inventory coverage assertions (chainage, zero-scar segments, distance to route).
4. Headline metrics table side-by-side (pooled AUC, block AUC mean, k=6, Spearman rho).
5. Sensitivity table and pairwise rank correlations.
"""
from pathlib import Path
import pandas as pd
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
HOTSPOTS_CSV = ROOT_DIR / "data" / "known_hotspots.csv"
AUDIT_REPORT = ROOT_DIR / "outputs" / "validation_audit.md"

EXPECTED_HOTSPOTS = [
    "Sirobagarh",
    "Kaliasaur",
    "Tangni",
    "Pagal Nala",
    "Lambagad",
    "Chhinka",
    "Helang",
    "Bhanerpani",
]


def test_hotspots_template_exists():
    """Verify data/known_hotspots.csv exists with expected columns and names."""
    assert HOTSPOTS_CSV.exists(), "data/known_hotspots.csv missing"
    df = pd.read_csv(HOTSPOTS_CSV)
    expected_cols = ["name", "lat", "lng", "source_url"]
    assert list(df.columns) == expected_cols

    names = df["name"].tolist()
    for exp in EXPECTED_HOTSPOTS:
        assert exp in names, f"Expected hotspot '{exp}' missing from template"

    # All coordinates must be blank in initial template
    assert df["lat"].isna().all(), "lat should be blank in template"
    assert df["lng"].isna().all(), "lng should be blank in template"


def test_validation_audit_report_sections():
    """Verify outputs/validation_audit.md exists and contains sections (a), (b), (c), and (d)."""
    assert AUDIT_REPORT.exists(), "outputs/validation_audit.md missing"
    content = AUDIT_REPORT.read_text(encoding="utf-8")

    # Check major section headers
    assert "## (a) Inventory Coverage Analysis" in content
    assert "## (b) Headline Model Cross-Validation Metrics" in content
    assert "## (c) Known Hotspot Recall Evaluation" in content
    assert "## (d) Aggregation Method Sensitivity Analysis" in content


def test_inventory_coverage_details():
    """Verify section (a) details: chainage extent, zero scars, max distance."""
    content = AUDIT_REPORT.read_text(encoding="utf-8")

    # 309 scars
    assert "309" in content
    # Chainage extent
    assert "9.07 km to 242.66 km" in content
    # Full coverage verdict
    assert "Does NOT span the full 247.37 km" in content
    # Zero scar segment
    assert "seg_15" in content
    assert "Chamoli to Birahi" in content
    # Max distance
    assert "22.5 m" in content


def test_headline_metrics_table():
    """Verify section (b) side-by-side headline table."""
    content = AUDIT_REPORT.read_text(encoding="utf-8")

    # Table elements
    assert "Pooled Out-of-Fold AUC" in content
    assert "0.767" in content
    assert "Per-Block Mean AUC" in content
    assert "0.664" in content
    assert "Spatial Blocks ($k$)" in content
    assert "6" in content
    assert "Spearman Rank Correlation" in content
    assert "0.653" in content
    assert "p = 0.0033" in content


def test_hotspot_recall_handling():
    """Verify section (c) handles blank template rows with clean messaging."""
    content = AUDIT_REPORT.read_text(encoding="utf-8")

    assert "Template Status" in content
    assert "Sirobagarh" in content
    assert "Skipped (Blank Coordinates in Template)" in content


def test_sensitivity_aggregations():
    """Verify section (d) contains p90, p75, mean, max aggregations and correlations."""
    content = AUDIT_REPORT.read_text(encoding="utf-8")

    # Pairwise correlations
    assert "P90 vs P75" in content
    assert "0.9236" in content
    assert "P90 vs MEAN" in content
    assert "0.8720" in content
    assert "P90 vs MAX" in content
    assert "0.9133" in content
    assert "P75 vs MEAN" in content
    assert "0.9174" in content
    assert "P75 vs MAX" in content
    assert "0.8927" in content
    assert "MEAN vs MAX" in content
    assert "0.8947" in content

    # All 18 segments in ranking table
    for i in range(1, 19):
        assert f"seg_{i:02d}" in content
