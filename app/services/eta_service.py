import os
import logging
from typing import Optional
import joblib
import pandas as pd

logger = logging.getLogger("eta_service")


class ETAService:
    _model = None
    _model_loaded: bool = False
    _model_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "ml_models",
        "RapidRescue_ETA_Model.pkl"
    )

    @classmethod
    def load_model(cls) -> bool:
        """
        Load the ETA model once when initialized.
        Returns True if loaded successfully, False otherwise.
        """
        if cls._model_loaded and cls._model is not None:
            return True

        if not os.path.exists(cls._model_path):
            logger.error(f"ETA model file not found at path: {cls._model_path}")
            cls._model_loaded = False
            return False

        try:
            cls._model = joblib.load(cls._model_path)
            cls._model_loaded = True
            logger.info("ETA model loaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to load ETA model from {cls._model_path}: {e}")
            cls._model = None
            cls._model_loaded = False
            return False

    @classmethod
    def is_loaded(cls) -> bool:
        return cls._model_loaded and cls._model is not None

    @classmethod
    def predict_eta(
        cls,
        distance_km: float,
        traffic_level: int,
        avg_speed_kmh: float,
        hour: int,
        day_of_week: int,
    ) -> float:
        """
        Predict ambulance ETA in minutes using exact model features:
        - distance_km (float)
        - traffic_level (int: 1=Low, 2=Medium, 3=High)
        - avg_speed_kmh (float)
        - hour (int: 0..23)
        - day_of_week (int: 0=Monday..6=Sunday)
        """
        if not cls.is_loaded():
            if not cls.load_model():
                raise RuntimeError("ETA model is not loaded.")

        # Input validation
        if distance_km < 0:
            raise ValueError("distance_km cannot be negative.")
        if traffic_level not in (1, 2, 3):
            raise ValueError("traffic_level must be 1 (Low), 2 (Medium), or 3 (High).")
        if avg_speed_kmh <= 0:
            raise ValueError("avg_speed_kmh must be greater than zero.")
        if not (0 <= hour <= 23):
            raise ValueError("hour must be between 0 and 23.")
        if not (0 <= day_of_week <= 6):
            raise ValueError("day_of_week must be between 0 (Monday) and 6 (Sunday).")

        input_df = pd.DataFrame([{
            "distance_km": float(distance_km),
            "traffic_level": int(traffic_level),
            "avg_speed_kmh": float(avg_speed_kmh),
            "hour": int(hour),
            "day_of_week": int(day_of_week)
        }])

        prediction = cls._model.predict(input_df)[0]
        return round(float(prediction), 2)

    @classmethod
    def predict_eta_safe(
        cls,
        distance_km: float,
        traffic_level: Optional[int] = None,
        avg_speed_kmh: Optional[float] = None,
        hour: Optional[int] = None,
        day_of_week: Optional[int] = None,
    ) -> Optional[float]:
        """
        Safe prediction wrapper that handles missing inputs or model errors gracefully.
        Will NOT fabricate traffic/speed data if not provided.
        Returns ETA float in minutes if successful, or None if inputs/prediction unavailable.
        """
        if traffic_level is None or avg_speed_kmh is None:
            # Missing real traffic/speed data; return None to avoid fake data
            return None

        if hour is None or day_of_week is None:
            # Can infer hour and day_of_week from current UTC time if timestamp not provided
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if hour is None:
                hour = now.hour
            if day_of_week is None:
                day_of_week = now.weekday()

        try:
            return cls.predict_eta(
                distance_km=distance_km,
                traffic_level=traffic_level,
                avg_speed_kmh=avg_speed_kmh,
                hour=hour,
                day_of_week=day_of_week,
            )
        except Exception as e:
            logger.error(f"ETA safe prediction failed: {e}")
            return None


# Pre-load on import/init
ETAService.load_model()
