# ===================================== ENFORCE CACHE DIRECTORY ======================================
import os

os.environ["TORCH_HOME"] = "./model_weights/torch"
os.environ["HF_HOME"] = "./model_weights/huggingface"
os.environ["PYANNOTE_CACHE"] = "./model_weights/torch/pyannote"
# ====================================================================================================

import base64
import io
import warnings

import gradio as gr
import pandas as pd


from loguru import logger
from src.pipeline import process_all_videos_from_path, process_video
from src.plotting import plot_speaker_charts

required_version = (2, 2, 0)
current_version = tuple(map(int, pd.__version__.split(".")[:3]))

if current_version < required_version:
    raise RuntimeError(
        f"Incompatible pandas version detected: {pd.__version__}. "
        f"Please install pandas>=2.2.0 for Python 3.12 compatibility."
    )

warnings.filterwarnings("ignore")



def get_image_base64(path):
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    return f'<img src="data:image/png;base64,{encoded}" width="300" style="display: block; margin: 0 auto;"/>'



def process_multiple_videos(
    folder_path=None,
    video_files=None,
    perform_ner=True,
    perform_sentiment=True,
    perform_tone=True,
):
    """
    Processes videos from a specified folder path or from uploaded files.
    Returns a status message, a pandas DataFrame, and the path to the
    first generated CSV file for download.
    """
    output_dir = "csv_outputs"
    os.makedirs(output_dir, exist_ok=True)
    processed_csvs = []

    logger.debug(
        f"Initializing process_multiple_videos. Folder Path: '{folder_path}', Video Files: {video_files}"
    )
    logger.debug(
        f"Options - NER: {perform_ner}, Sentiment: {perform_sentiment}, Tone: {perform_tone}"
    )

    # Clear any existing CSV files in the output directory
    for f in os.listdir(output_dir):
        if f.endswith(".csv"):
            try:
                os.remove(os.path.join(output_dir, f))
                logger.debug(f"Removed old CSV: {f}")
            except OSError as e:
                logger.error(f"Error removing old CSV file {f}: {e}")

    if folder_path and os.path.isdir(folder_path):
        logger.info(f"Processing videos from folder: {folder_path}")
        # Pass checkbox states to process_all_videos_from_path
        process_all_videos_from_path(
            folder_path,
            output_dir,
            perform_ner,
            perform_sentiment,
            perform_tone,
        )
        processed_csvs = [
            os.path.join(output_dir, f)
            for f in os.listdir(output_dir)
            if f.endswith(".csv")
        ]
        logger.info(
            f"Finished processing videos from folder. Found {len(processed_csvs)} CSVs."
        )

    elif video_files:
        logger.info(f"Processing uploaded video files: {video_files}")
        for idx, video_path in enumerate(video_files):
            logger.debug(
                f"Checking uploaded video_path[{idx}]: '{video_path}' (Exists: {os.path.exists(video_path)})"
            )

            if not os.path.exists(video_path):
                return (
                    f"Error: Uploaded video file does not exist at path: {video_path}. Please try re-uploading.",
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    gr.update(open=False),
                )

            original_filename = os.path.basename(video_path)
            # Ensure proper CSV filename generation from video filename
            output_csv_filename = os.path.splitext(original_filename)[0] + ".csv"
            output_csv_path = os.path.join(output_dir, output_csv_filename)

            logger.info(
                f"Processing uploaded video: {original_filename} to {output_csv_path}"
            )

            try:
                # Call the process_video function from src.pipeline
                # Pass checkbox states to process_video
                process_video(
                    video_path,
                    output_csv_path,
                    perform_ner,
                    perform_sentiment,
                    perform_tone,
                )
                processed_csvs.append(output_csv_path)
                logger.success(
                    f"Successfully processed uploaded video: {original_filename}"
                )
            except Exception as e:
                import traceback

                logger.error(
                    f"Exception while processing {original_filename}: {str(e)}"
                )
                logger.error(traceback.format_exc())
                return (
                    f"Error processing {original_filename}: {str(e)}. Check console for details.",
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    gr.update(open=False),
                )
        logger.info(
            f"Finished processing uploaded videos. Found {len(processed_csvs)} CSVs."
        )

    else:
        logger.warning("No folder path or video files provided.")
        return (
            "Please provide a folder path or upload video files to begin.",
            gr.update(visible=False, value=None),
            gr.update(visible=False, value=None),
            gr.update(visible=False, value=None),
            gr.update(open=False),
        )

    if processed_csvs:
        try:
            # Display the first processed CSV in the DataFrame
            df = pd.read_csv(processed_csvs[0])
            logger.info(f"Displaying data from: {os.path.basename(processed_csvs[0])}")
            # Generate plots and convert to base64 HTML
            plot_img = plot_speaker_charts(df)
            return (
                f"Successfully processed {len(processed_csvs)} video(s). Displaying data from {os.path.basename(processed_csvs[0])}.",
                gr.update(visible=True, value=df),
                gr.update(visible=True, value=processed_csvs[0]),
                plot_img,
                gr.update(open=True),
            )
        except Exception as e:
            import traceback

            logger.error(
                f"Error reading processed CSV {os.path.basename(processed_csvs[0])}: {str(e)}"
            )
            logger.error(traceback.format_exc())
            return (
                f"Error reading processed CSV {os.path.basename(processed_csvs[0])}: {str(e)}. Check console for details.",
                gr.update(visible=False, value=None),
                gr.update(visible=False, value=None),
                "",
                gr.update(open=False),
            )

    logger.warning("No videos were processed or no CSV outputs were generated.")
    return (
        "No videos were processed or no CSV outputs were generated. Please check inputs and console logs.",
        gr.update(visible=False, value=None),
        gr.update(visible=False, value=None),
        "",
        gr.update(open=False),
    )


def create_interface():
    """
    Creates and returns the Gradio interface for the Driving Simulator Communication Analysis Tool.
    """
    custom_css = """
        .red-checkbox input[type='checkbox']:checked {
            accent-color: red !important;
            background-color: red !important;
            border-color: red !important;
        }
        .red-checkbox input[type='checkbox']:checked::before {
            background-color: red !important;
            border-color: red !important;
        }
        /* Make checkboxes and their labels smaller */
        .red-checkbox label span {
            font-size: 0.8em !important; /* Adjust label font size */
            padding-left: 2px !important; /* Adjust spacing between checkbox and label */
        }
        .red-checkbox input[type='checkbox'] {
            transform: scale(0.8); /* Adjust checkbox size */
            margin-right: -5px; /* Adjust spacing if needed after scaling */
        }
        .red-checkbox {
            min-width: auto !important; /* Allow checkbox group to shrink */
            padding: 2px !important; /* Reduce padding around the checkbox itself */
            margin: 0px !important; /* Reduce margin around the checkbox component */
        }
    """

    with gr.Blocks(
        title="Driving Simulator Communication Analysis Tool",
        theme=gr.themes.Monochrome(),
        css=custom_css,  # Added custom CSS
    ) as demo:
        html_img = get_image_base64("assets/trip_lab_logo.png")
        gr.HTML(
            f"""
        <div style="text-align: center;">
            {html_img}  
            <h1>Driving Simulator Communication Analysis Tool</h1>
        </div>
        """
        )

        with gr.Row():
            with gr.Column(scale=1):
                folder_path = gr.Textbox(
                    label="Folder Path (Optional)",
                    placeholder="E.g., C:/Users/YourUser/Videos/SimulatorData",
                    lines=1,
                )
                video_files = gr.File(
                    label="Upload Videos (Optional)",
                    file_count="multiple",
                    type="filepath",  # Ensures a temporary file path is provided
                    file_types=[".mp4", ".mov", ".avi", ".webm"],
                )

                with gr.Group():
                    with gr.Row():  # Make checkboxes inline
                        checkbox_ner = gr.Checkbox(
                            label="NER (Named Entity Recognition)",
                            value=True,
                            elem_classes=["red-checkbox"],
                        )
                        checkbox_sentiment = gr.Checkbox(
                            label="Sentiment Analysis",
                            value=True,
                            elem_classes=["red-checkbox"],
                        )
                        checkbox_tone = gr.Checkbox(
                            label="Tone Intensity",
                            value=True,
                            elem_classes=["red-checkbox"],
                        )

                submit_btn = gr.Button("Start Processing", variant="primary")

            with gr.Column(scale=3):
                status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    placeholder="Waiting for input...",
                )
                with gr.Accordion("Show Table", open=False) as table_accordion:
                    output_table = gr.DataFrame(
                        label="Processed Data (First Video)",
                        visible=False,
                        type="pandas",
                        interactive=True,
                    )
                download_csv = gr.File(
                    label="Download Processed CSV",
                    visible=False,
                    type="filepath",  # This is for download, not upload
                    file_count="single",
                )
                with gr.Accordion("Show Plots", open=True) as plot_accordion:
                    plot_image = gr.Image(label="Speaker Analysis Plots", width=1200)

        submit_btn.click(
            fn=process_multiple_videos,
            inputs=[
                folder_path,
                video_files,
                checkbox_ner,
                checkbox_sentiment,
                checkbox_tone,
            ],
            outputs=[status, output_table, download_csv, plot_image, table_accordion],
        )

    return demo


demo = create_interface()
demo.launch()