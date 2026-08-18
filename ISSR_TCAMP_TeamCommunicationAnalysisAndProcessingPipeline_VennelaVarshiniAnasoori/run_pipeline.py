import argparse
import logging
import json
from tcamp.pipeline import TCAMPPipeline

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main():
    parser = argparse.ArgumentParser(description="TCAMP Telemetry Pipeline")
    parser.add_argument("--input", "-i", type=str, required=True, help="Path to input audio file")
    parser.add_argument("--output-dir", "-o", type=str, default="observations/outputs", help="Directory to save output files")
    parser.add_argument("--enhance-method", "-m", type=str, choices=["deepfilter", "noisereduce"], default="deepfilter", help="Enhancement method")
    parser.add_argument("--evaluate", "-e", type=str, help="Path to reference RTTM file for DER evaluation")
    parser.add_argument("--phase", type=str, choices=["all", "enhance", "diarize", "transcribe"], default="all", help="Which pipeline phase to run")
    parser.add_argument("--num-speakers", "-s", type=int, help="Force a specific number of speakers (optional)")
    parser.add_argument("--vad-threshold", type=float, help="Override Pyannote VAD segmentation threshold (e.g., 0.30)")
    parser.add_argument("--apply-normalization", action="store_true", help="Apply DRC speech normalization after enhancement")
    parser.add_argument("--token", "-t", type=str, help="Hugging Face token (defaults to HF_TOKEN env var)")
    
    # Transcription Arguments
    parser.add_argument("--transcription-model", type=str, default="medium.en", help="WhisperX model size (e.g., medium.en, large-v2, base)")
    parser.add_argument("--transcription-device", type=str, default="cpu", help="Device for WhisperX (cpu or cuda)")
    parser.add_argument("--transcription-compute", type=str, default="int8", help="Compute precision for WhisperX (int8 or float16)")
    parser.add_argument("--run-qc", action="store_true", help="Run the Multi-Condition QC Tagger on diarization output")
    parser.add_argument("--run-analytics", action="store_true", help="Run Behavioral Analytics and NLP Tagging")
    
    args = parser.parse_args()
    setup_logger()
    logger = logging.getLogger("run_pipeline")
    
    logger.info("initializing tcamp pipeline...")
    try:
        pipeline = TCAMPPipeline(auth_token=args.token)
        results = pipeline.process(
            input_audio=args.input,
            output_dir=args.output_dir,
            enhance_method=args.enhance_method,
            reference_rttm=args.evaluate,
            phase=args.phase,
            num_speakers=args.num_speakers,
            apply_normalization=args.apply_normalization,
            vad_threshold=args.vad_threshold,
            transcription_model=args.transcription_model,
            transcription_device=args.transcription_device,
            transcription_compute=args.transcription_compute,
            run_qc=args.run_qc,
            run_analytics=args.run_analytics
        )
        
        logger.info("\npipeline execution summary:\n" + json.dumps(results, indent=2))
        
    except ValueError as ve:
        logger.error(f"config error: {str(ve)}")
    except Exception as ex:
        logger.error(f"pipeline crashed: {str(ex)}")

if __name__ == "__main__":
    main()
