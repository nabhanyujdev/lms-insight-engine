"""
Student Learning Behavior Analytics & Performance Prediction System
Backend: Flask + Scikit-learn
"""

from flask import Flask, jsonify, request, render_template, session
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import KNNImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "student-analytics-demo-secret")

DUMMY_CREDENTIALS = {
    "username": "admin",
    "password": "jiit123",
}


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.before_request
def require_login_for_api():
    open_api_paths = {"/api/login", "/api/logout", "/api/session"}
    if request.method == "OPTIONS":
        return None
    if request.path.startswith("/api/") and request.path not in open_api_paths:
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized"}), 401
    return None


DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "student_engagement_dataset.csv")

COLUMN_MAP = {
    "Student_ID": "student_id",
    "Course_ID": "course_id",
    "Login_Frequency": "login_frequency",
    "Time_Spent_Modules": "time_spent_modules",
    "Participation_Forums": "participation_forums",
    "Quiz_Performance_Average": "quiz_performance_average",
    "Assignment_Submissions": "assignment_submissions",
    "Resource_Access_Frequency": "resource_access_frequency",
    "Session_Duration_Average": "session_duration_average",
    "Device_Type": "device_type",
    "Internet_Bandwidth": "internet_bandwidth",
    "Engagement_Level": "source_engagement_level",
}

RAW_FEATURES = [
    "login_frequency",
    "time_spent_modules",
    "participation_forums",
    "quiz_performance_average",
    "assignment_submissions",
    "resource_access_frequency",
    "session_duration_average",
]

ACTIVITY_COMPONENTS = {
    "login_frequency": 0.35,
    "time_spent_modules": 0.35,
    "resource_access_frequency": 0.30,
}

PARTICIPATION_COMPONENTS = {
    "participation_forums": 0.60,
    "session_duration_average": 0.40,
}

PERFORMANCE_COMPONENTS = {
    "quiz_performance_average": 0.65,
    "assignment_submissions": 0.35,
}

FEATURES = RAW_FEATURES + [
    "activity_score",
    "participation_score",
    "performance_score",
    "engagement_score",
]
PCA_FEATURES = [
    "activity_score",
    "participation_score",
    "engagement_score",
]
ENGAGEMENT_LEVELS = ["Inactive", "Sparsely Involved", "Actively Involved"]
ENGAGEMENT_THRESHOLDS = {
    "inactive_max": 45,
    "sparse_max": 65,
}


def load_dataset():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    df = pd.read_csv(DATA_PATH).rename(columns=COLUMN_MAP)
    df["student_id"] = df["student_id"].astype(str).str.strip()
    df["course_id"] = df["course_id"].astype(str).str.strip()
    df["device_type"] = df["device_type"].astype(str).str.strip()
    return df


def preprocess(df):
    numeric_cols = RAW_FEATURES + ["internet_bandwidth"]
    imputer = KNNImputer(n_neighbors=5)
    df[numeric_cols] = imputer.fit_transform(df[numeric_cols])

    for col in RAW_FEATURES:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        df[col] = df[col].clip(lower, upper)

    return df


def build_score_bounds(frame):
    bounds = {}
    for col in RAW_FEATURES:
        lower = float(frame[col].quantile(0.10))
        upper = float(frame[col].quantile(0.90))
        bounds[col] = (lower, upper)
    return bounds


def scale_series(series, bounds, column_name):
    lower, upper = bounds[column_name]
    denominator = max(upper - lower, 1e-9)
    return ((series - lower) / denominator).clip(0, 1) * 100


def compute_weighted_score(frame, components, bounds):
    score = np.zeros(len(frame), dtype=float)
    for col, weight in components.items():
        score += scale_series(frame[col], bounds, col) * weight
    return np.round(score, 2)


def enrich_scores(frame, bounds):
    enriched = frame.copy()
    enriched["activity_score"] = compute_weighted_score(
        enriched, ACTIVITY_COMPONENTS, bounds
    )
    enriched["participation_score"] = compute_weighted_score(
        enriched, PARTICIPATION_COMPONENTS, bounds
    )
    enriched["performance_score"] = compute_weighted_score(
        enriched, PERFORMANCE_COMPONENTS, bounds
    )
    enriched["engagement_score"] = np.round(
        0.35 * enriched["activity_score"]
        + 0.20 * enriched["participation_score"]
        + 0.45 * enriched["performance_score"],
        2,
    )
    return enriched


def compute_risk_score(frame, low_signal_thresholds):
    risk_score = 100 - frame["engagement_score"]
    risk_score += np.where(
        frame["assignment_submissions"] <= low_signal_thresholds["assignment_submissions"],
        8,
        0,
    )
    risk_score += np.where(
        frame["quiz_performance_average"] <= low_signal_thresholds["quiz_performance_average"],
        6,
        0,
    )
    risk_score += np.where(
        frame["resource_access_frequency"] <= low_signal_thresholds["resource_access_frequency"],
        4,
        0,
    )
    return np.round(np.clip(risk_score, 0, 100), 2)


def assign_engagement_levels(scores):
    labels = []
    for score in scores:
        if score <= ENGAGEMENT_THRESHOLDS["inactive_max"]:
            labels.append("Inactive")
        elif score <= ENGAGEMENT_THRESHOLDS["sparse_max"]:
            labels.append("Sparsely Involved")
        else:
            labels.append("Actively Involved")
    return labels


def derive_at_risk(frame):
    return (frame["risk_score"] >= 55).astype(int)


def extract_risk_factors(row, low_signal_thresholds):
    factors = []
    if row["engagement_level"] == "Inactive":
        factors.append("Very low overall engagement")
    if row["quiz_performance_average"] <= low_signal_thresholds["quiz_performance_average"]:
        factors.append("Quiz performance is below the low-performance threshold")
    if row["assignment_submissions"] <= low_signal_thresholds["assignment_submissions"]:
        factors.append("Assignment submission count is low")
    if row["resource_access_frequency"] <= low_signal_thresholds["resource_access_frequency"]:
        factors.append("Learning resources are accessed infrequently")
    if row["activity_score"] < 45:
        factors.append("Platform activity is below the expected range")
    return factors[:3]


raw_df = load_dataset()
df = preprocess(raw_df.copy())

score_bounds = build_score_bounds(df)
df = enrich_scores(df, score_bounds)

df["engagement_level"] = assign_engagement_levels(df["engagement_score"])

low_signal_thresholds = {
    "quiz_performance_average": float(df["quiz_performance_average"].quantile(0.25)),
    "assignment_submissions": float(df["assignment_submissions"].quantile(0.25)),
    "resource_access_frequency": float(df["resource_access_frequency"].quantile(0.25)),
}
df["risk_score"] = compute_risk_score(df, low_signal_thresholds)
df["at_risk"] = derive_at_risk(df)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(df[FEATURES])

kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
df["cluster"] = kmeans.fit_predict(X_scaled)
cluster_score = df.groupby("cluster")["engagement_score"].mean().sort_values()
segment_map = {
    cluster_score.index[0]: "Inactive",
    cluster_score.index[1]: "Sparsely Involved",
    cluster_score.index[2]: "Actively Involved",
}
df["segment_label"] = df["cluster"].map(segment_map)

pca_scaler = StandardScaler()
X_pca_scaled = pca_scaler.fit_transform(df[PCA_FEATURES])
pca = PCA(n_components=2, random_state=42)
pca_coords = pca.fit_transform(X_pca_scaled)
df["pca_x"] = pca_coords[:, 0]
df["pca_y"] = pca_coords[:, 1]

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled,
    df["at_risk"],
    test_size=0.2,
    random_state=42,
    stratify=df["at_risk"],
)

rf = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    class_weight="balanced",
)
rf.fit(X_train, y_train)

lr = LogisticRegression(random_state=42, class_weight="balanced", max_iter=1000)
lr.fit(X_train, y_train)

rf_acc = round(accuracy_score(y_test, rf.predict(X_test)) * 100, 2)
lr_acc = round(accuracy_score(y_test, lr.predict(X_test)) * 100, 2)

feature_importance = {
    name: round(score, 4)
    for name, score in zip(FEATURES, rf.feature_importances_)
}
raw_importance_total = sum(feature_importance[name] for name in RAW_FEATURES) or 1.0
raw_feature_importance = {}
running_total = 0.0
for index, name in enumerate(RAW_FEATURES):
    if index < len(RAW_FEATURES) - 1:
        value = round((feature_importance[name] / raw_importance_total) * 100, 2)
        running_total += value
    else:
        value = round(100.0 - running_total, 2)
    raw_feature_importance[name] = value

df["risk_probability"] = np.round(rf.predict_proba(X_scaled)[:, 1] * 100, 1)


def build_feature_frame(payload):
    frame = pd.DataFrame(
        [
            {
                "login_frequency": float(payload["login_frequency"]),
                "time_spent_modules": float(payload["time_spent_modules"]),
                "participation_forums": float(payload["participation_forums"]),
                "quiz_performance_average": float(payload["quiz_performance_average"]),
                "assignment_submissions": float(payload["assignment_submissions"]),
                "resource_access_frequency": float(payload["resource_access_frequency"]),
                "session_duration_average": float(payload["session_duration_average"]),
            }
        ]
    )
    frame = enrich_scores(frame, score_bounds)
    frame["engagement_level"] = assign_engagement_levels(frame["engagement_score"])
    frame["risk_score"] = compute_risk_score(frame, low_signal_thresholds)
    frame["at_risk"] = derive_at_risk(frame)
    return frame


def get_recommendation(risk_prob, engagement_level, risk_factors):
    factor_note = ""
    if risk_factors:
        factor_note = f" Main concerns: {', '.join(risk_factors[:2]).lower()}."
    if risk_prob >= 0.70:
        return (
            "High risk: schedule an academic intervention, review missed assignments, "
            "and monitor this student weekly." + factor_note
        )
    if risk_prob >= 0.50:
        return (
            "Moderate risk: send engagement nudges, offer tutoring support, and track "
            "module access over the next two weeks." + factor_note
        )
    if engagement_level == "Sparsely Involved":
        return (
            "Low immediate risk, but participation is inconsistent. Encourage more forum "
            "activity and regular resource access." + factor_note
        )
    return (
        "On track: keep reinforcing the current study pattern and maintain regular "
        "module activity." + factor_note
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/session")
def session_status():
    return jsonify(
        {
            "authenticated": bool(session.get("authenticated")),
            "username": session.get("username", ""),
        }
    )


@app.route("/api/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()

    if (
        username == DUMMY_CREDENTIALS["username"]
        and password == DUMMY_CREDENTIALS["password"]
    ):
        session["authenticated"] = True
        session["username"] = username
        return jsonify({"success": True, "username": username})

    return jsonify({"success": False, "error": "Invalid dummy ID or password"}), 401


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/dashboard")
def dashboard():
    total_students = len(df)
    at_risk_count = int(df["at_risk"].sum())
    avg_engagement = round(df["engagement_score"].mean(), 1)
    avg_activity = round(df["activity_score"].mean(), 1)
    avg_participation = round(df["participation_score"].mean(), 1)
    avg_performance = round(df["performance_score"].mean(), 1)
    avg_bandwidth = round(df["internet_bandwidth"].mean(), 1)
    top_device = df["device_type"].mode().iat[0]

    level_dist = (
        df["engagement_level"]
        .value_counts()
        .reindex(ENGAGEMENT_LEVELS, fill_value=0)
        .to_dict()
    )
    segment_dist = (
        df["segment_label"]
        .value_counts()
        .reindex(ENGAGEMENT_LEVELS, fill_value=0)
        .to_dict()
    )
    risk_by_level = {}
    for level in ENGAGEMENT_LEVELS:
        level_df = df[df["engagement_level"] == level]
        at_risk_level = int(level_df["at_risk"].sum())
        safe_level = int(len(level_df) - at_risk_level)
        risk_by_level[level] = {
            "at_risk": at_risk_level,
            "safe": safe_level,
        }

    return jsonify(
        {
            "total_students": total_students,
            "at_risk": at_risk_count,
            "avg_engagement": avg_engagement,
            "avg_activity": avg_activity,
            "avg_participation": avg_participation,
            "avg_performance": avg_performance,
            "avg_bandwidth": avg_bandwidth,
            "top_device": top_device,
            "rf_accuracy": rf_acc,
            "lr_accuracy": lr_acc,
            "engagement_level_dist": level_dist,
            "segment_dist": segment_dist,
            "risk_by_level": risk_by_level,
            "raw_feature_importance": raw_feature_importance,
        }
    )


@app.route("/api/students")
def students():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 15))
    search = request.args.get("search", "").strip().lower()
    risk_filter = request.args.get("risk", "all")
    level_filter = request.args.get("level", "all")

    subset = df.copy()
    if search:
        subset = subset[
            subset["student_id"].str.lower().str.contains(search)
            | subset["course_id"].str.lower().str.contains(search)
        ]

    if risk_filter == "at_risk":
        subset = subset[subset["at_risk"] == 1]
    elif risk_filter == "safe":
        subset = subset[subset["at_risk"] == 0]

    level_map = {
        "inactive": "Inactive",
        "sparse": "Sparsely Involved",
        "active": "Actively Involved",
    }
    if level_filter in level_map:
        subset = subset[subset["engagement_level"] == level_map[level_filter]]

    total_filtered = len(subset)
    subset = subset.iloc[(page - 1) * per_page : page * per_page]

    records = []
    for _, row in subset.iterrows():
        records.append(
            {
                "student_id": row["student_id"],
                "course_id": row["course_id"],
                "login_frequency": int(round(row["login_frequency"])),
                "time_spent_modules": round(row["time_spent_modules"], 1),
                "participation_forums": int(round(row["participation_forums"])),
                "quiz_performance_average": round(row["quiz_performance_average"], 1),
                "activity_score": round(row["activity_score"], 1),
                "participation_score": round(row["participation_score"], 1),
                "performance_score": round(row["performance_score"], 1),
                "engagement_score": round(row["engagement_score"], 1),
                "final_segment": row["engagement_level"],
                "at_risk": int(row["at_risk"]),
                "risk_score": round(float(row["risk_score"]), 1),
                "risk_probability": round(float(row["risk_probability"]), 1),
                "risk_factors": extract_risk_factors(row, low_signal_thresholds),
            }
        )

    return jsonify(
        {
            "students": records,
            "total": total_filtered,
            "page": page,
            "per_page": per_page,
        }
    )


@app.route("/api/clusters")
def clusters():
    sample_size = min(200, len(df))
    sample = df.sample(sample_size, random_state=42)
    points = []
    for _, row in sample.iterrows():
        points.append(
            {
                "x": round(row["pca_x"], 3),
                "y": round(row["pca_y"], 3),
                "segment_label": row["segment_label"],
                "engagement_level": row["engagement_level"],
                "engagement_score": round(row["engagement_score"], 1),
                "student_id": row["student_id"],
                "course_id": row["course_id"],
            }
        )

    return jsonify(
        {
            "points": points,
            "variance_explained": [
                round(value * 100, 1) for value in pca.explained_variance_ratio_
            ],
        }
    )


@app.route("/api/predict", methods=["POST"])
def predict():
    payload = request.get_json(silent=True) or {}
    required_fields = list(RAW_FEATURES)

    missing = [field for field in required_fields if field not in payload]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        frame = build_feature_frame(payload)
        scaled = scaler.transform(frame[FEATURES])
        rf_prob = float(rf.predict_proba(scaled)[0][1])
        lr_prob = float(lr.predict_proba(scaled)[0][1])
        avg_prob = (rf_prob + lr_prob) / 2
        cluster = int(kmeans.predict(scaled)[0])
        segment_label = segment_map.get(cluster, "Unknown")
        engagement_level = frame["engagement_level"].iat[0]
        risk_factors = extract_risk_factors(frame.iloc[0], low_signal_thresholds)

        return jsonify(
            {
                "rf_risk_probability": round(rf_prob * 100, 1),
                "lr_risk_probability": round(lr_prob * 100, 1),
                "avg_risk_probability": round(avg_prob * 100, 1),
                "at_risk": avg_prob >= 0.5,
                "activity_score": round(float(frame["activity_score"].iat[0]), 1),
                "participation_score": round(float(frame["participation_score"].iat[0]), 1),
                "performance_score": round(float(frame["performance_score"].iat[0]), 1),
                "engagement_score": round(float(frame["engagement_score"].iat[0]), 1),
                "risk_score": round(float(frame["risk_score"].iat[0]), 1),
                "engagement_level": engagement_level,
                "segment_label": segment_label,
                "risk_factors": risk_factors,
                "recommendation": get_recommendation(avg_prob, engagement_level, risk_factors),
            }
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/top_at_risk")
def top_at_risk():
    risky = df.sort_values("risk_probability", ascending=False).head(10)
    return jsonify(
        [
            {
                "student_id": row["student_id"],
                "course_id": row["course_id"],
                "engagement_level": row["engagement_level"],
                "engagement_score": round(row["engagement_score"], 1),
                "risk_score": round(float(row["risk_score"]), 1),
                "risk_probability": round(float(row["risk_probability"]), 1),
            }
            for _, row in risky.iterrows()
        ]
    )


if __name__ == "__main__":
    print("=" * 55)
    print("  Student Learning Analytics System")
    print("  Running at: http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
