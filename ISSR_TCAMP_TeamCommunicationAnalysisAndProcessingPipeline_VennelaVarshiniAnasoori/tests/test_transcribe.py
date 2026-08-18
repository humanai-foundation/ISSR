import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Skip actual loading if whisperx is not installed in the test environment
try:
    from tcamp.transcription.transcribe import TranscriptionPipeline
    HAS_WHISPERX = True
except ImportError:
    HAS_WHISPERX = False

@pytest.fixture
def mock_whisperx():
    with patch('tcamp.transcription.transcribe.whisperx') as mock_wx:
        # Mock load_model
        mock_model = MagicMock()
        mock_wx.load_model.return_value = mock_model
        
        # Mock transcribe result
        mock_model.transcribe.return_value = {
            "segments": [{"text": " hello world"}],
            "language": "en"
        }
        
        # Mock load_audio
        mock_wx.load_audio.return_value = "dummy_audio_array"
        
        yield mock_wx, mock_model

@pytest.mark.skipif(not HAS_WHISPERX, reason="whisperx is required for transcription tests")
def test_transcription_pipeline_initialization(mock_whisperx):
    mock_wx, mock_model = mock_whisperx
    
    pipeline = TranscriptionPipeline(model_size="tiny", device="cpu")
    
    mock_wx.load_model.assert_called_once_with("tiny", "cpu", compute_type="int8")
    assert pipeline.device == "cpu"

@pytest.mark.skipif(not HAS_WHISPERX, reason="whisperx is required for transcription tests")
def test_transcription_pipeline_transcribe(mock_whisperx, tmp_path):
    mock_wx, mock_model = mock_whisperx
    
    # Create a dummy audio file
    dummy_audio = tmp_path / "dummy.wav"
    dummy_audio.touch()
    
    pipeline = TranscriptionPipeline(model_size="tiny", device="cpu")
    result = pipeline.transcribe_audio(dummy_audio)
    
    mock_wx.load_audio.assert_called_once_with(str(dummy_audio))
    mock_model.transcribe.assert_called_once_with("dummy_audio_array", batch_size=16)
    
    assert "segments" in result
    assert result["segments"][0]["text"] == " hello world"

@pytest.mark.skipif(not HAS_WHISPERX, reason="whisperx is required for transcription tests")
def test_transcription_pipeline_file_not_found(mock_whisperx):
    pipeline = TranscriptionPipeline(model_size="tiny", device="cpu")
    
    with pytest.raises(FileNotFoundError):
        pipeline.transcribe_audio("nonexistent_file.wav")
