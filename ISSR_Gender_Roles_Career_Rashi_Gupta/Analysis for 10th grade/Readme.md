# 10th Grade Educational Survey Data Analysis

## Overview

This project analyzes educational survey data from 10th grade to understand how students' perceptions and choices impact their future educational and career decisions. The analysis includes data preprocessing, model training, evaluation, and visualization.

## Key Components

### 1. Data Preprocessing

- **SMOTE (Synthetic Minority Over-sampling Technique)**: Used to balance the dataset by generating synthetic samples for minority classes to improve model performance.
- **Cross-Validation**: Applied to assess the model's performance and ensure it generalizes well to unseen data.
- **Grid Search**: Used to find the optimal hyperparameters for the RandomForestClassifier.

### 2. Model Training and Evaluation

- **Models Trained**: RandomForestClassifier
- **Performance Metrics**: Precision, Recall, F1-Score, Accuracy, ROC Curves
- **Data Splits**: Training and Testing sets, with resampling techniques to handle imbalanced classes.

### 3. Visual Representations

#### ROC Curves

The ROC curves illustrate the performance of the model across different classes. The area under the curve (AUC) indicates the model's ability to distinguish between classes.

![ROC Curve - Fall Semester](https://www.example.com/roc_curve_fall.png)
![ROC Curve - Spring Semester](https://www.example.com/roc_curve_spring.png)

#### Confusion Matrices

Confusion matrices provide insights into the number of true positive, true negative, false positive, and false negative predictions.

![Confusion Matrix - Fall Semester](https://www.example.com/confusion_matrix_fall.png)
![Confusion Matrix - Spring Semester](https://www.example.com/confusion_matrix_spring.png)

## Architecture Diagrams

### Overall Architecture

This diagram outlines the overall workflow of the project, from data collection to model evaluation.

![Overall Architecture Diagram](https://www.example.com/overall_architecture.png)

### Model Architecture

This diagram details the model architecture, including feature selection, model training, and evaluation processes.

![Model Architecture Diagram](https://www.example.com/model_architecture.png)

## Usage

To replicate or build upon this analysis, follow these steps:

1. **Data Preparation**: Ensure data is preprocessed, including handling missing values and encoding categorical variables.
2. **Model Training**: Use Grid Search to find the best hyperparameters and train the model with balanced data.
3. **Evaluation**: Assess model performance using metrics like precision, recall, F1-score, and visualize results with ROC curves and confusion matrices.




