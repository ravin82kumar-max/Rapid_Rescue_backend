import os
import io
import logging
from typing import Optional, Union, Dict, Any
from PIL import Image

logger = logging.getLogger("severity_service")

# Map ML severity output labels to backend emergency priority levels
SEVERITY_TO_PRIORITY_MAP = {
    "CRITICAL": "CRITICAL",
    "MODERATE": "HIGH",
    "LOW": "NORMAL",
}


class SeverityService:
    _model = None
    _class_names: list = ["LOW", "MODERATE", "CRITICAL"]
    _input_size: int = 224
    _transform = None
    _torch = None
    _torchvision = None
    _model_loaded: bool = False
    _model_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "ml_models",
        "RapidRescue_Severity_Model.pth.zip"
    )

    @classmethod
    def load_model(cls) -> bool:
        """
        Load the PyTorch Severity model once upon initialization.
        Returns True if loaded successfully, False otherwise.
        """
        if cls._model_loaded and cls._model is not None:
            return True

        if not os.path.exists(cls._model_path):
            logger.error(f"Severity model file not found at path: {cls._model_path}")
            cls._model_loaded = False
            return False

        try:
            import torch
            import torchvision
            import torchvision.transforms as T

            cls._torch = torch
            cls._torchvision = torchvision

            checkpoint = torch.load(cls._model_path, map_location="cpu", weights_only=False)

            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                cls._class_names = checkpoint.get("class_names", ["LOW", "MODERATE", "CRITICAL"])
                cls._input_size = checkpoint.get("input_size", 224)
                state_dict = checkpoint["model_state_dict"]

                model = torchvision.models.efficientnet_b0(num_classes=len(cls._class_names))
                model.load_state_dict(state_dict)
            elif hasattr(checkpoint, "eval"):
                model = checkpoint
            else:
                raise ValueError(f"Unrecognized checkpoint format in {cls._model_path}")

            model.eval()
            cls._model = model

            # Define standard ImageNet preprocessing transform
            cls._transform = T.Compose([
                T.Resize((cls._input_size, cls._input_size)),
                T.ToTensor(),
                T.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225]
                )
            ])

            cls._model_loaded = True
            logger.info(f"Severity model (EfficientNet-B0) loaded successfully with classes {cls._class_names}.")
            return True

        except Exception as e:
            logger.error(f"Failed to load Severity model from {cls._model_path}: {e}")
            cls._model = None
            cls._model_loaded = False
            return False

    @classmethod
    def is_loaded(cls) -> bool:
        return cls._model_loaded and cls._model is not None

    @classmethod
    def predict_severity(
        cls,
        image_input: Union[str, bytes, Image.Image]
    ) -> Dict[str, Any]:
        """
        Predict emergency image severity.
        Accepts file path (str), raw image bytes (bytes), or PIL Image.
        Returns dict with keys:
        - severity: predicted class name ('LOW', 'MODERATE', 'CRITICAL')
        - confidence: confidence score (float)
        - probabilities: dict of class -> probability
        - suggested_priority: mapped backend priority ('NORMAL', 'HIGH', 'CRITICAL')
        """
        if not cls.is_loaded():
            if not cls.load_model():
                raise RuntimeError("Severity model is not loaded.")

        # Load image into PIL Image
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image file not found: {image_input}")
            img = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, Image.Image):
            img = image_input.convert("RGB")
        else:
            raise TypeError("image_input must be a file path, bytes, or PIL Image instance.")

        torch = cls._torch
        tensor = cls._transform(img).unsqueeze(0)

        with torch.no_grad():
            outputs = cls._model(tensor)
            probabilities_tensor = torch.softmax(outputs, dim=1)[0]
            confidence_idx = torch.argmax(probabilities_tensor).item()

        probs_list = probabilities_tensor.tolist()
        class_probs = {
            cls._class_names[i]: round(float(probs_list[i]), 4)
            for i in range(len(cls._class_names))
        }

        predicted_severity = cls._class_names[confidence_idx]
        confidence_score = round(float(probs_list[confidence_idx]), 4)
        suggested_priority = SEVERITY_TO_PRIORITY_MAP.get(predicted_severity, "CRITICAL")

        return {
            "severity": predicted_severity,
            "confidence": confidence_score,
            "probabilities": class_probs,
            "suggested_priority": suggested_priority,
        }

    @classmethod
    def predict_severity_safe(
        cls,
        image_input: Union[str, bytes, Image.Image]
    ) -> Optional[Dict[str, Any]]:
        """
        Safe prediction wrapper that handles invalid inputs or prediction errors.
        Logs error and returns None without crashing the server.
        """
        try:
            return cls.predict_severity(image_input)
        except Exception as e:
            logger.error(f"Severity safe prediction failed: {e}")
            return None


# Pre-load on import/init
SeverityService.load_model()
