"""
shared test fixtures
connects tests to the real 3-minute ami headset sample.

"""

import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

ami_sample_path = root_dir / "screening_notebooks" / "sample_input_and_output_files" / "sample_input.wav"
observations_dir = root_dir / "observations"


@pytest.fixture(scope="session", autouse=True)
def setup_observations():
    """creates observations folder to save output files."""
    observations_dir.mkdir(exist_ok=True)
    return observations_dir


@pytest.fixture
def ami_sample():
    """returns path to the real sample audio."""
    if not ami_sample_path.exists():
        pytest.skip(f"sample file not found at {ami_sample_path}")
    return ami_sample_path


@pytest.fixture
def output_path(tmp_path):
    """temporary file path for testing."""
    return tmp_path / "temp_out.wav"


@pytest.fixture
def observations_output():
    """returns path to observations directory to save audio files."""
    return observations_dir
