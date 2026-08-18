import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Literal
import numpy as np

from tcamp.enhance.enhance import AudioEnhancer
from tcamp.diarization.diarize import DiarizationPipeline
from tcamp.diarization.utils import save_diarization_results, parse_rttm, calculate_der, save_rttm
from tcamp.transcription.transcribe import TranscriptionPipeline
from tcamp.analytics.qc_tagger import QCTagger
from tcamp.analytics.behavioral_metrics import BehavioralAnalytics
from tcamp.analytics.dialogue_tagger import OllamaDialogueTagger
from tcamp.analytics.export import export_metrics_to_csv, export_transcript_to_csv

logger = logging.getLogger(__name__)

def compute_rms(audio_array: np.ndarray) -> float:
    """Computes Root Mean Square energy of an audio array."""
    if len(audio_array) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio_array**2)))

class TCAMPPipeline:
    def __init__(self, auth_token: Optional[str] = None):
        self.auth_token = auth_token or os.environ.get("HF_TOKEN")
        self.audio_enhancer = AudioEnhancer()
        self.diarization_pipeline = None
        self.transcription_pipeline = None
        
    def process(
        self,
        input_audio: str | Path,
        output_dir: str | Path,
        enhance_method: Literal["deepfilter", "noisereduce"] = "deepfilter",
        reference_rttm: Optional[str | Path] = None,
        phase: Literal["all", "enhance", "diarize", "transcribe"] = "all",
        num_speakers: Optional[int] = None,
        apply_normalization: bool = False,
        vad_threshold: Optional[float] = None,
        transcription_model: str = "medium.en",
        transcription_device: str = "cpu",
        transcription_compute: str = "int8",
        run_qc: bool = False,
        run_analytics: bool = False
    ) -> Dict[str, Any]:
        """
        Runs the full TCAMP Dual-Path pipeline.
        Executes enhancement, diarization, QC tagging, and transcription.
        """
        input_path = Path(input_audio)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Audio Extraction for Video Files
        if input_path.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov']:
            import subprocess
            logger.info(f"Video file detected ({input_path.suffix}). Extracting audio track to WAV...")
            extracted_wav_path = out_dir / f"{input_path.stem}_extracted.wav"
            
            if not extracted_wav_path.exists():
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", str(input_path), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(extracted_wav_path)],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    logger.info(f"Successfully extracted audio to {extracted_wav_path.name}")
                except Exception as e:
                    logger.error(f"Failed to extract audio from video: {e}")
                    raise
            else:
                logger.info(f"Extracted audio already exists at {extracted_wav_path.name}")
            
            # Point pipeline to the newly extracted WAV file
            input_path = extracted_wav_path
        
        enhanced_audio_path = out_dir / f"enhanced_{enhance_method}_{input_path.name}"
        diarization_json_path = out_dir / f"diarization_{enhance_method}_{input_path.stem}.json"
        diarization_rttm_path = out_dir / f"diarization_{enhance_method}_{input_path.stem}.rttm"
        transcript_path = out_dir / f"transcript_{input_path.stem}.txt"
        
        results = {
            "input_audio": str(input_path),
            "enhanced_audio": str(enhanced_audio_path),
            "enhancement_metrics": {},
            "diarization_results": str(diarization_json_path),
            "diarization_rttm": str(diarization_rttm_path),
            "transcript_file": str(transcript_path),
            "der": None,
            "der_breakdown": None,
            "transcript_segments": []
        }
        
        # 1. Enhancement
        if phase in ["all", "enhance", "transcribe"]:
            if not enhanced_audio_path.exists() or phase == "enhance":
                logger.info(f"enhancing audio via {enhance_method}...")
                metrics = self.audio_enhancer.enhance(
                    input_path=input_path,
                    output_path=enhanced_audio_path,
                    method=enhance_method,
                    target_sr=16000,
                    apply_normalization=apply_normalization
                )
                results["enhancement_metrics"] = metrics
            else:
                logger.info("enhanced audio already exists, skipping generation.")
        
        # 2. Diarization
        if phase in ["all", "diarize", "transcribe"]:
            logger.info("diarizing raw audio...")
            if self.diarization_pipeline is None:
                if not self.auth_token:
                    raise ValueError("HF_TOKEN is missing. Cannot initialize diarization pipeline.")
                self.diarization_pipeline = DiarizationPipeline(auth_token=self.auth_token, vad_threshold=vad_threshold)
                
            segments = self.diarization_pipeline.process(str(input_path), num_speakers=num_speakers)
            save_diarization_results(segments, str(diarization_json_path))
            save_rttm(segments, str(diarization_rttm_path), uri=input_path.stem)
            logger.info(f"Diarization complete. Saved to {diarization_json_path.name}")
            
            # Evaluation
            if reference_rttm is None:
                potential_rttm = input_path.parent / f"{input_path.stem}_ground_truth.rttm"
                if potential_rttm.exists():
                    reference_rttm = str(potential_rttm)
            
            if reference_rttm and Path(reference_rttm).exists():
                logger.info(f"Evaluating DER against {Path(reference_rttm).name}...")
                try:
                    ref_segments = parse_rttm(str(reference_rttm))
                    der_stats = calculate_der(ref_segments, segments)
                    results["der"] = der_stats["der"]
                    results["der_breakdown"] = der_stats
                    logger.info(f"DER: {der_stats['der']:.2%} [Miss: {der_stats['miss']:.2%} | FA: {der_stats['false_alarm']:.2%}]")
                except ImportError:
                    pass

            if run_qc:
                logger.info("Running QC Tagger...")
                qc_tagger = QCTagger()
                qc_flags = qc_tagger.process(segments, str(input_path))
                
                qc_report_path = out_dir / f"qc_flags_{input_path.stem}.json"
                qc_tagger.save_report(qc_flags, str(qc_report_path))
                results["qc_report"] = str(qc_report_path)


        # 3. Transcription
        if phase in ["all", "transcribe"]:
            logger.info("initializing transcriber...")
            if self.transcription_pipeline is None:
                self.transcription_pipeline = TranscriptionPipeline(
                    model_size=transcription_model, 
                    device=transcription_device, 
                    compute_type=transcription_compute
                )
            
            logger.info("executing dual-path transcription...")
            import soundfile as sf
            raw_audio, sr = sf.read(input_path)
            enhanced_audio, _ = sf.read(enhanced_audio_path)
            
            transcript_log = []
            
            for segment in segments:
                start_time = segment["start"]
                end_time = segment["end"]
                speaker = segment["speaker"]
                
                start_sample = int(start_time * sr)
                end_sample = int(end_time * sr)
                
                raw_seg = raw_audio[start_sample:end_sample]
                dfn_seg = enhanced_audio[start_sample:end_sample]
                
                raw_rms = compute_rms(raw_seg)
                dfn_rms = compute_rms(dfn_seg)
                
                # Source Selection Logic
                if raw_rms > 0 and (dfn_rms / raw_rms) < 0.10:
                    selected_seg = raw_seg
                    source = "RAW"
                else:
                    selected_seg = dfn_seg
                    source = "DFN"
                    
                # Minimum duration safeguard
                segment_duration = end_time - start_time
                if segment_duration < 0.5:
                    continue

                # Transcribe numpy array
                try:
                    trans_result = self.transcription_pipeline.transcribe_audio(selected_seg, language="en")
                    segments = trans_result.get("segments", [])
                    text = " ".join([s.get("text", "") for s in segments]).strip()
                except IndexError:
                    # Handle WhisperX VAD empty-chunk IndexError
                    continue
                except Exception as e:
                    logger.warning(f"WhisperX failed to transcribe segment [{start_time}-{end_time}]: {e}")
                    continue
                
                if not text:
                    continue
                    
                log_line = f"[{start_time:05.1f} - {end_time:05.1f}] {speaker} ({source}): {text}"
                logger.info(log_line)
                transcript_log.append(log_line)
                results["transcript_segments"].append({
                    "start": start_time,
                    "end": end_time,
                    "speaker": speaker,
                    "source": source,
                    "text": text
                })
                
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write("\n".join(transcript_log))
            logger.info(f"Transcription complete! Saved to {transcript_path}")
            
        # 4. Behavioral Analytics
        if run_analytics and phase in ["all", "transcribe"]:
            logger.info("running behavioral analytics and NLP tagging...")
            
            # Dialogue Tagging
            tagger = OllamaDialogueTagger()
            tagged_segments = tagger.process(results["transcript_segments"])
            
            tagged_transcript_path = out_dir / f"tagged_transcript_{input_path.stem}.json"
            tagger.save_report(tagged_segments, str(tagged_transcript_path))
            results["tagged_transcript_file"] = str(tagged_transcript_path)
            
            tagged_transcript_csv_path = out_dir / f"tagged_transcript_{input_path.stem}.csv"
            export_transcript_to_csv(tagged_segments, str(tagged_transcript_csv_path))
            results["tagged_transcript_csv_file"] = str(tagged_transcript_csv_path)
            
            # Calculate Metrics
            analytics = BehavioralAnalytics()
            metrics = analytics.process(tagged_segments)
            
            metrics_path = out_dir / f"behavioral_metrics_{input_path.stem}.json"
            analytics.save_report(metrics, str(metrics_path))
            results["behavioral_metrics"] = str(metrics_path)
            
            metrics_csv_path = out_dir / f"behavioral_metrics_{input_path.stem}.csv"
            export_metrics_to_csv(metrics, str(metrics_csv_path))
            results["behavioral_metrics_csv"] = str(metrics_csv_path)
            
            results["transcript_segments"] = tagged_segments
                
        return results
