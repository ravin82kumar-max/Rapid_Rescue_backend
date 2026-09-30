import os
import uuid
from fastapi import UploadFile, HTTPException, status

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/jpg",
    "image/webp",
    "image/heic",
    "image/heif",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_image_file(file: UploadFile, field_name: str) -> None:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field '{field_name}' must contain a valid file name."
        )
    
    ext = os.path.splitext(file.filename)[1].lower()
    if file.content_type and file.content_type.lower() not in ALLOWED_IMAGE_TYPES:
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type for '{field_name}'. Allowed formats: JPG, JPEG, PNG, WEBP, HEIC."
            )

    # Check file size if available
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{field_name}' exceeds maximum allowed size of 10MB."
        )


async def save_upload_file(file: UploadFile, prefix: str = "img") -> tuple[str, str]:
    """
    Saves an uploaded file to uploads/emergencies/ directory.
    Returns a tuple of (local_relative_file_path, web_url_path).
    """
    upload_dir = os.path.join("uploads", "emergencies")
    os.makedirs(upload_dir, exist_ok=True)

    original_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
    if original_ext not in ALLOWED_EXTENSIONS:
        original_ext = ".jpg"

    safe_filename = f"{prefix}_{uuid.uuid4().hex}{original_ext}"
    local_path = os.path.join(upload_dir, safe_filename)

    # Read and write file contents safely
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of 10MB."
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{file.filename}' is empty."
        )

    with open(local_path, "wb") as f:
        f.write(content)

    # Normalize relative path to forward slashes for URLs
    url_path = f"/uploads/emergencies/{safe_filename}"
    db_path = local_path.replace("\\", "/")

    return db_path, url_path
