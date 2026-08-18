"""
tests for speaker diarization module
evaluates the Pyannote pipeline and DER tracking skeleton.
"""

import os
import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from tcamp.diarization.diarize import DiarizationPipeline
from tcamp.diarization.utils import save_diarization_results, parse_rttm, calculate_der


class TestDiarizationPipeline:
    """tests execution of the pyannote pipeline."""

    def test_pipeline_execution(self, ami_sample, tmp_path):
        """tests if the model can load and process audio. requires HF_TOKEN."""
        token = os.environ.get("HF_TOKEN")
        if not token:
            pytest.skip("HF_TOKEN missing from environment variables. Skipping heavy Pyannote inference test.")
            
        pipeline = DiarizationPipeline(auth_token=token)
        segments = pipeline.process(str(ami_sample))
        
        assert isinstance(segments, list)
        if len(segments) > 0:
            assert "start" in segments[0]
            assert "end" in segments[0]
            assert "speaker" in segments[0]
            
        out_json = tmp_path / "test_diarization_output.json"
        save_diarization_results(segments, str(out_json))
        assert out_json.exists()


class TestDiarizationMetrics:
    """tests evaluation metrics."""

    def test_der_perfect_match(self):
        """tests DER calculation mathematically on a mock 0% error case."""
        mock_reference = [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.5, "end": 4.0, "speaker": "SPEAKER_01"}
        ]
        mock_hypothesis = [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.5, "end": 4.0, "speaker": "SPEAKER_01"}
        ]
        
        der_stats = calculate_der(mock_reference, mock_hypothesis)
        assert der_stats["der"] == 0.0
        assert der_stats["miss"] == 0.0
        assert der_stats["false_alarm"] == 0.0

    def test_rttm_parser(self, tmp_path):
        """tests if the RTTM parsing skeleton works correctly."""
        mock_rttm_content = (
            "SPEAKER test_file 1 0.00 4.50 <NA> <NA> SPEAKER_00 <NA> <NA>\n"
            "SPEAKER test_file 1 5.00 1.00 <NA> <NA> SPEAKER_01 <NA> <NA>\n"
        )
        rttm_path = tmp_path / "test.rttm"
        rttm_path.write_text(mock_rttm_content)
        
        segments = parse_rttm(str(rttm_path))
        
        assert len(segments) == 2
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 4.50
        assert segments[0]["speaker"] == "SPEAKER_00"
        
        assert segments[1]["start"] == 5.0
        assert segments[1]["end"] == 6.0
        assert segments[1]["speaker"] == "SPEAKER_01"
