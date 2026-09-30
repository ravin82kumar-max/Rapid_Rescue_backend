import torch

severity_path = "app/ml_models/RapidRescue_Severity_Model.pth.zip"
loaded = torch.load(severity_path, map_location="cpu", weights_only=False)

print("Architecture:", loaded.get("architecture"))
print("Input size:", loaded.get("input_size"))
print("Class names:", loaded.get("class_names"))
print("Validation macro f1:", loaded.get("validation_macro_f1"))

print("\n--- Model State Dict Keys & Shapes ---")
for k, v in loaded["model_state_dict"].items():
    print(f"{k}: {v.shape}")
