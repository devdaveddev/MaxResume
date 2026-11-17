import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("STORAGE", "memory")  # tests never touch a real database
ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "sample_data"


@pytest.fixture(scope="session", autouse=True)
def samples():
    """Generate the synthetic resumes once if they are not present."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    if not (SAMPLES / "resumes" / "aarav_mehta.pdf").exists():
        import generate_samples

        generate_samples.main()
    if not (SAMPLES / "edge_cases" / "two_column.pdf").exists():
        import generate_edge_cases

        generate_edge_cases.main()
    if not (SAMPLES / "heldout" / "nadia_rahman.txt").exists():
        import generate_heldout

        generate_heldout.main()
    return SAMPLES
