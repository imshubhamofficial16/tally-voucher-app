from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.services.import_service import ImportService
from src.config import config

router = APIRouter(tags=["imports"])

MAX_FILE_SIZE = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert to bytes


@router.post("/imports", status_code=status.HTTP_201_CREATED)
async def create_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Import Tally XML file
    Accepts multipart/form-data with field name 'file'
    Returns 201 for new imports, 200 for duplicates
    """
    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file"
        )

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {config.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Validate it's not empty
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty"
        )

    # Process import
    service = ImportService(db)
    try:
        result = service.process_upload(content, file.filename or "unknown.xml")

        # Return 200 for duplicates, 201 for new imports
        status_code = status.HTTP_200_OK if result["duplicate"] else status.HTTP_201_CREATED

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Log the actual error for debugging
        import traceback
        traceback.print_exc()

        # Don't expose internal errors in production
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the import: {str(e)}"
        )


@router.get("/imports/{import_id}")
async def get_import_details(
    import_id: str,
    db: Session = Depends(get_db)
):
    """Get import details by ID"""
    service = ImportService(db)
    details = service.get_import_details(import_id)

    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import with ID {import_id} not found"
        )

    return details


@router.get("/imports/{import_id}/vouchers")
async def get_import_vouchers(
    import_id: str,
    db: Session = Depends(get_db)
):
    """Get normalized vouchers for an import"""
    service = ImportService(db)

    # Check if import exists first
    details = service.get_import_details(import_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import with ID {import_id} not found"
        )

    vouchers = service.get_normalized_vouchers(import_id)
    return vouchers
