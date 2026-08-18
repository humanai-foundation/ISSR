"""
tests for audio enhancement module
runs checks on the real 3-minute sample file.

"""

import math
import sys
from pathlib import Path
import pytest

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from tcamp.enhance.enhance import enhance_audio
from tcamp.enhance.metrics import evaluate, _si_sdr, _stoi


class TestInputHandling:
    """tests error handling for bad inputs."""

    def test_missing_file(self, output_path):
        with pytest.raises(FileNotFoundError, match="input file not found"):
            enhance_audio("nonexistent.wav", output_path)

    def test_bad_method(self, ami_sample, output_path):
        with pytest.raises(ValueError, match="unknown method"):
            enhance_audio(ami_sample, output_path, method="badmethod")  # type: ignore


class TestEnhancementOnSample:
    """tests running enhancement on real audio sample."""

    def test_noisereduce(self, ami_sample, observations_output):
        out_file = observations_output / "enhanced_noisereduce_ami.wav"
        res = enhance_audio(ami_sample, out_file, method="noisereduce", target_sr=16000)

        assert out_file.exists()
        assert res["method"] == "noisereduce"

        import soundfile as sf
        _, sr = sf.read(str(out_file))
        assert sr == 16000

        print("\n--- noisereduce results ---")
        print(f"stoi:   {res['stoi']}")
        print(f"si-sdr: {res['si_sdr']} dB")
        print(f"dnsmos: {res['dnsmos']}")
        print(f"saved:  {out_file}")

    def test_deepfilter(self, ami_sample, observations_output):
        out_file = observations_output / "enhanced_deepfilter_ami.wav"
        try:
            res = enhance_audio(ami_sample, out_file, method="deepfilter", target_sr=16000)
            assert out_file.exists()
            assert res["method"] == "deepfilter"

            import soundfile as sf
            _, sr = sf.read(str(out_file))
            assert sr == 16000

            print("\n--- deepfilter results ---")
            print(f"stoi:   {res['stoi']} (aligned 16khz scale)")
            print(f"si-sdr: {res['si_sdr']} dB")
            print(f"dnsmos: {res['dnsmos']}")
            print(f"saved:  {out_file}")
        except ImportError as e:
            assert "deepfilternet" in str(e) or "torchaudio" in str(e)
            print("\n--- deepfilter model not installed in this env ---")

    def test_auto_mkdir(self, ami_sample, tmp_path):
        deep_file = tmp_path / "newdir" / "out.wav"
        enhance_audio(ami_sample, deep_file, method="noisereduce")
        assert deep_file.exists()


class TestMetricsCalculation:
    """tests quality scores calculations."""

    def test_stoi_range(self, ami_sample, tmp_path):
        out_file = tmp_path / "test.wav"
        enhance_audio(ami_sample, out_file, method="noisereduce")

        score = _stoi(ami_sample, out_file)
        if not math.isnan(score):
            assert 0.0 <= score <= 1.0

    def test_sisdr_valid(self, ami_sample, tmp_path):
        out_file = tmp_path / "test.wav"
        enhance_audio(ami_sample, out_file, method="noisereduce")

        score = _si_sdr(ami_sample, out_file)
        assert math.isfinite(score)

    def test_keys_exist(self, ami_sample, tmp_path):
        out_file = tmp_path / "test.wav"
        enhance_audio(ami_sample, out_file, method="noisereduce")

        res = evaluate(ami_sample, out_file)
        assert all(k in res for k in ("stoi", "dnsmos", "si_sdr"))

    def test_dnsmos_valid(self, ami_sample):
        res = evaluate(ami_sample, ami_sample)
        score = res["dnsmos"]
        if not math.isnan(score):
            assert score > 1.0
