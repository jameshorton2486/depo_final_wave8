"""POST /api/nod/parse — accept a NOD PDF upload, return parsed fields."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.nod_parser import parse as parse_nod

router = APIRouter(prefix="/api/nod", tags=["nod"])

MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB cap on uploads


@router.post("/parse")
async def parse_nod_endpoint(file: UploadFile = File(...)) -> dict:
    """Parse a Notice of Deposition PDF.

    Returns a JSON object with three top-level keys:
      - fields: flat dict matching the frontend's UFM field names
      - metadata: detected document types, jurisdiction, warnings, etc.
      - keyterms: suggested Deepgram keyterms with boost values
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(contents)} bytes; max {MAX_PDF_BYTES}).",
        )

    try:
        result = parse_nod(contents)
    except Exception as exc:
        # Never leak internal exceptions; the parser is best-effort.
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse NOD: {type(exc).__name__}: {exc}",
        ) from exc

    return result.to_frontend_dict()
