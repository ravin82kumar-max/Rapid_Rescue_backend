
import os
import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "app", "ml_models", "RapidRescue_ETA_Model.pkl")
if not os.path.exists(MODEL_PATH):
    MODEL_PATH = os.path.join(BASE_DIR, "RapidRescue_ETA_Model.pkl")

eta_model = None
if os.path.exists(MODEL_PATH):
    eta_model = joblib.load(MODEL_PATH)


def predict_eta(
    distance_km,
    traffic_level,
    avg_speed_kmh,
    hour,
    day_of_week
):
    """
    Predict ambulance ETA in minutes.

    traffic_level:
        1 = Low
        2 = Medium
        3 = High

    day_of_week:
        0 = Monday
        1 = Tuesday
        2 = Wednesday
        3 = Thursday
        4 = Friday
        5 = Saturday
        6 = Sunday
    """
    if eta_model is None:
        raise FileNotFoundError(f"ETA model not found at {MODEL_PATH}")

    input_data = pd.DataFrame([{
        "distance_km": distance_km,
        "traffic_level": traffic_level,
        "avg_speed_kmh": avg_speed_kmh,
        "hour": hour,
        "day_of_week": day_of_week
    }])

    prediction = eta_model.predict(input_data)[0]

    return round(float(prediction), 2)


if __name__ == "__main__":

    eta = predict_eta(
        distance_km=5.2,
        traffic_level=2,
        avg_speed_kmh=28,
        hour=18,
        day_of_week=2
    )

    print(f"Predicted ETA: {eta} minutes")

