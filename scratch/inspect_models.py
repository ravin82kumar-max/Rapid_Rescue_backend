import sys
import os
import zipfile
import pickle

print("Python version:", sys.version)

eta_path = "app/ml_models/RapidRescue_ETA_Model.pkl"
severity_path = "app/ml_models/RapidRescue_Severity_Model.pth.zip"

print("\n--- Inspecting ETA Model ---")
if os.path.exists(eta_path):
    import joblib
    model = joblib.load(eta_path)
    print("ETA Model Type:", type(model))
    print("ETA Model Details:", model)
    if hasattr(model, "feature_names_in_"):
        print("ETA Feature Names in model:", model.feature_names_in_)
    if hasattr(model, "n_features_in_"):
        print("ETA N features in model:", model.n_features_in_)

print("\n--- Inspecting Severity Model Zip ---")
if os.path.exists(severity_path):
    with zipfile.ZipFile(severity_path, 'r') as z:
        print("Zip files count:", len(z.namelist()))
        print("Sample files in zip:", z.namelist()[:10])

    import torch
    print("PyTorch version:", torch.__version__)
    try:
        loaded = torch.load(severity_path, map_location="cpu", weights_only=False)
        print("torch.load successful!")
        print("Loaded object type:", type(loaded))
        if isinstance(loaded, dict):
            print("Dict keys:", loaded.keys())
            for k, v in loaded.items():
                print(f"Key '{k}': type {type(v)}")
                if hasattr(v, 'shape'):
                    print(f"  Shape: {v.shape}")
                elif isinstance(v, dict):
                    print(f"  Sub-keys: {list(v.keys())[:10]}")
        elif hasattr(loaded, "eval"):
            print("Loaded model module/class:", loaded.__class__)
            print("Model repr:\n", loaded)
    except Exception as e:
        print("torch.load failed:", e)
        # Try TorchScript load
        try:
            ts_model = torch.jit.load(severity_path, map_location="cpu")
            print("torch.jit.load successful!")
            print("TorchScript model graph:\n", ts_model.code)
        except Exception as e2:
            print("torch.jit.load failed:", e2)
