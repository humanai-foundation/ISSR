# Drowsiness and Distraction detection for drivers
## Project Overview
Distracted and drowsy driving are major threats on the road, contributing significantly to global road accidents. This project specifically addresses drowsy driving, targeting professions like surgical residents and truck drivers who often face gruelling schedules. Here a camera is used to detect signs of drowsiness or distraction  in the driver. By analysing these factors, the system can warn drivers who are too tired or distracted to continue driving safely.
## Dataset
The datset used in this github repo can be found [here](https://github.com/Vicomtech/DMD-Driver-Monitoring-Dataset)
## Directories
Directories move and yawn contain code to seperate frames with instances for yawn and drowsy driver and make a YOLOv8 dataset for the images
Run clip zero_clip_video.py to get the zero shot results for running CLIP ViT-L/14 model on the DMD dataset.

## Implementation Guidance
1. Install the required packages <br>
```
pip install -r requirements.txt
```
2. Install the required packages from the [SPIGA](https://github.com/andresprados/SPIGA) and [CLIP](https://github.com/openai/CLIP) github repositories.
## Results
Final Results will be released by the final evaluation period. You can find out more about the project on my [blog](https://medium.com/@aditya.arvind97/fatigue-detection-and-driver-state-monitoring-48c75eb0eeff).
