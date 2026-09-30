# 🤖 RapidRescue — Machine Learning Integration Documentation

This document outlines the machine learning architecture, integrated models, input specifications, API integration flows, fallback mechanisms, and deployment guidelines for the **RapidRescue** emergency dispatch system.

---

## 1. Integrated Models Overview

| Model Name | Model Type / Architecture | Source File Location | Primary Function |
|---|---|---|---|
| **ETA Model** | `RandomForestRegressor` (scikit-learn) | [`app/ml_models/RapidRescue_ETA_Model.pkl`](file:///c:/Users/Nature/Desktop/backend/app/ml_models/RapidRescue_ETA_Model.pkl) | Predicts ambulance arrival time in minutes based on distance, traffic, speed, and temporal features. |
| **Severity Model** | `EfficientNet-B0` (PyTorch / torchvision) | [`app/ml_models/RapidRescue_Severity_Model.pth.zip`](file:///c:/Users/Nature/Desktop/backend/app/ml_models/RapidRescue_Severity_Model.pth.zip) | Classifies incident photo severity from uploaded vehicle/patient emergency images. |

---

## 2. Model 1 — ETA Prediction Model

### 2.1 Specification & Features
- **Model File:** `app/ml_models/RapidRescue_ETA_Model.pkl`
- **Service Class:** [`ETAService`](file:///c:/Users/Nature/Desktop/backend/app/services/eta_service.py)
- **Model Type:** Scikit-learn `RandomForestRegressor(n_estimators=200, max_depth=15)`
- **Input Features (Exact Order & Format):**
  1. `distance_km` (float): Distance in kilometers between responder and pickup location.
  2. `traffic_level` (int): Categorical traffic congestion level (`1` = Low, `2` = Medium, `3` = High).
  3. `avg_speed_kmh` (float): Expected or average ambulance speed in km/h.
  4. `hour` (int): Hour of day (`0` to `23`).
  5. `day_of_week` (int): Day of week (`0` = Monday, `1` = Tuesday, ..., `6` = Sunday).

### 2.2 Output & Sample Verification
- **Output:** Predicted ETA in minutes (float rounded to 2 decimal places).
- **Verified Benchmark Sample:**
  ```python
  ETAService.predict_eta(
      distance_km=5.2,
      traffic_level=2,
      avg_speed_kmh=28,
      hour=18,
      day_of_week=2
  )
  # Result: 14.18 minutes
  ```

### 2.3 API Integration & Fallback Behavior
- Loaded **once** on application startup.
- Integrated into [`DispatchService.dispatch_to_next_candidate`](file:///c:/Users/Nature/Desktop/backend/app/services/dispatch_service.py#L80) and `EMERGENCY_DISPATCH` WebSocket payload.
- **Fallback Rule:** If real traffic level or speed data is not supplied, `ETAService.predict_eta_safe` returns `None` without fabricating fake traffic data. Standard emergency creation and dispatch continues seamlessly.

---

## 3. Model 2 — Incident Severity Classification Model

### 3.1 Specification & Preprocessing
- **Model File:** `app/ml_models/RapidRescue_Severity_Model.pth.zip`
- **Service Class:** [`SeverityService`](file:///c:/Users/Nature/Desktop/backend/app/services/severity_service.py)
- **Model Architecture:** PyTorch `torchvision.models.efficientnet_b0(num_classes=3)`
- **Input Feature:** Image (`JPEG`/`PNG`/`WEBP` photo, bytes, or file path).
- **Preprocessing Pipeline:**
  1. Convert to `RGB` image.
  2. Resize image tensor to `224x224`.
  3. Convert to PyTorch Tensor.
  4. Normalize using standard ImageNet mean & std:
     - `mean = [0.485, 0.456, 0.406]`
     - `std  = [0.229, 0.224, 0.225]`

### 3.2 Label & Priority Mapping
- **Model Output Classes:** `['LOW', 'MODERATE', 'CRITICAL']`
- **Mapping to Backend Dispatch Priorities:**
  | ML Severity Label | Backend Priority Value | Description |
  |---|---|---|
  | `CRITICAL` | `CRITICAL` | Highest priority (20s response deadline) |
  | `MODERATE` | `HIGH` | Elevated priority (40s response deadline) |
  | `LOW` | `NORMAL` | Standard priority (60s response deadline) |

### 3.3 Output Format
```json
{
  "severity": "LOW",
  "confidence": 0.427,
  "probabilities": {
    "LOW": 0.427,
    "MODERATE": 0.4034,
    "CRITICAL": 0.1696
  },
  "suggested_priority": "NORMAL"
}
```

### 3.4 API Integration & Fallback Behavior
- Loaded **once** on application startup.
- Executed during `POST /api/v1/emergencies` on uploaded front vehicle/incident photo (`front_photo`).
- **Fallback Rule:** If photo processing or ML prediction encounters any error or missing model file, `SeverityService.predict_severity_safe` catches the error, logs server-side diagnostic info, and returns `None`. Emergency creation defaults safely to standard priority (`CRITICAL`).

---

## 4. Model Storage & Directory Structure

Model artifacts are stored in `app/ml_models/`:

```
backend/
├── app/
│   ├── ml_models/
│   │   ├── RapidRescue_ETA_Model.pkl
│   │   └── RapidRescue_Severity_Model.pth.zip
│   │
│   └── services/
│       ├── eta_service.py
│       └── severity_service.py
│
├── predict_eta.py
├── requirements.txt
└── ML_INTEGRATION.md
```

> [!IMPORTANT]
> Model files are not served under any public or static web endpoint to prevent unauthorized downloads.

---

## 5. Dependency & Environment Requirements

Required packages in `requirements.txt`:

```text
joblib==1.6.0
pandas==3.0.6
scikit-learn==1.9.1
torch==2.14.0+cpu
torchvision==0.29.0+cpu
pillow==12.3.0
```

---

## 6. Known Limitations & Recommendations

1. **Traffic & Speed Input Requirement:** Real-time traffic level and speed values must be supplied to obtain ETA model predictions. The service layer strictly avoids generating fake traffic metrics.
2. **PyTorch CPU Execution:** The default configuration runs PyTorch on CPU for universal cross-platform deployment. If deployed on GPU-enabled infrastructure, `map_location` can be updated to `cuda`.
