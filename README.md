# EDUSCOPE: Student Learning Analytics and Risk Prediction System

EDUSCOPE is a Flask-based web application for analyzing student learning behavior and estimating academic risk from LMS engagement signals. It combines a clean interactive dashboard with machine learning, clustering, score engineering, and a what-if risk predictor built on a real student engagement dataset.

The system was developed as an FDA Lab project to explore how raw LMS activity can be transformed into interpretable engagement scores, final involvement segments, and intervention-ready risk insights.

## Web Link:
👉 [LIVE DEMO](https://lms-insight-engine.onrender.com/)

## Demo Login Credentials

- Username: `admin`
- Password: `jiit123`

## Key Features

- Session-protected login layer with dummy authentication for demo use.
- Real dataset integration using `student_engagement_dataset.csv`.
- Derived scoring pipeline for:
  - Activity Score
  - Participation Score
  - Performance Score
  - Engagement Score
  - Derived Risk Score
- Dashboard with:
  - cohort size
  - at-risk count
  - average engagement
  - top device usage
  - engagement-level distribution
  - overall risk distribution
  - raw feature importance
  - intervention queue
- Student records view with filtering by engagement level and risk status.
- PCA-based cluster analysis using derived scores.
- Risk predictor page for running custom what-if scenarios.
- Comparison of Random Forest and Logistic Regression risk probabilities.

## Tech Stack

### Backend

- Python
- Flask
- pandas
- NumPy
- scikit-learn
- gunicorn

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript
- Chart.js
- Google Fonts (`Syne`, `Manrope`)

## Dataset

The application uses a real CSV dataset stored at:

`data/student_engagement_dataset.csv`

The dataset includes fields such as:

- `Student_ID`
- `Course_ID`
- `Login_Frequency`
- `Time_Spent_Modules`
- `Participation_Forums`
- `Quiz_Performance_Average`
- `Assignment_Submissions`
- `Resource_Access_Frequency`
- `Session_Duration_Average`
- `Device_Type`
- `Internet_Bandwidth`

The original `Engagement_Level` column from the dataset is not used as the final system label. EDUSCOPE derives its own engagement segmentation and risk logic from engineered scores.

## Scoring Logic

Raw features are first cleaned and normalized using percentile-based scaling after KNN imputation and outlier clipping.

### Activity Score

`0.35 × Login Frequency + 0.35 × Time Spent Modules + 0.30 × Resource Access Frequency`

### Participation Score

`0.60 × Participation Forums + 0.40 × Session Duration Average`

### Performance Score

`0.65 × Quiz Performance Average + 0.35 × Assignment Submissions`

### Engagement Score

`0.35 × Activity Score + 0.20 × Participation Score + 0.45 × Performance Score`

### Final Engagement Levels

- `Inactive` if `Engagement Score <= 45`
- `Sparsely Involved` if `45 < Engagement Score <= 65`
- `Actively Involved` if `Engagement Score > 65`

### Derived Risk Score

Base rule:

`Risk Score = 100 - Engagement Score`

Penalties:

- `+8` if assignment submissions fall below the low threshold
- `+6` if quiz performance falls below the low threshold
- `+4` if resource access frequency falls below the low threshold

### At-Risk Rule

- Student is considered `At Risk` if `Risk Score >= 55`

## Machine Learning Pipeline

The project uses two classifiers trained on the processed dataset:

- `RandomForestClassifier`
- `LogisticRegression`

Both models are trained on raw LMS features plus the engineered score features. The predictor page shows:

- Random Forest risk probability
- Logistic Regression risk probability
- average risk probability across both models

Additional modeling components:

- `KMeans` clustering for student segmentation
- `PCA` for 2D cluster visualization
- `StandardScaler` for preprocessing model inputs
- `KNNImputer` for missing value handling

## Important Note on Risk Labels

This project does not use a historical dropout label from the dataset. The `at_risk` target is derived from the project’s own scoring logic, especially the final risk score cutoff. That means the system is best interpreted as a decision-support and analytics demo rather than a validated institutional dropout predictor.

## Project Structure

```text
.
├── app.py
├── ProcFile
├── requirements.txt
├── README.md
├── data/
│   └── student_engagement_dataset.csv
├── static/
│   ├── script.js
│   └── style.css
└── templates/
    └── index.html
```

## How to Run Locally

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2. Create a virtual environment

On macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the application

```bash
python3 app.py
```

Then open:

[http://localhost:5000](http://localhost:5000)


## Deployment Notes

The repository includes:

- `requirements.txt` for Python dependencies
- `ProcFile` for process-based deployment with gunicorn

## Future Enhancements

- add real institutional outcome labels for stronger validation
- add role-based authentication instead of dummy login
- support downloadable reports


