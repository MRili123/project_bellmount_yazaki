from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import uuid
import threading
from database import get_db
from models import Capture, User, UserRole, Switch
from schemas import CaptureResponse, CaptureUploadRequest
from storage import save_image, read_image, delete_image, ensure_dirs

router = APIRouter(prefix="/captures", tags=["captures"])

# Local mode: make sure the capture folders exist. No-op when using Azure Blob.
ensure_dirs()


def _pick_least_busy_annoteur(db: Session):
    """Return the id of the active annoteur with the fewest captures still
    awaiting verification, or None if there are no active annoteurs.

    Ties (e.g. everyone at zero) are broken by annoteur id so assignment is
    deterministic and rotates evenly as counts grow."""
    annoteurs = db.query(User).filter(
        User.role == UserRole.annoteur,
        User.is_active == True
    ).all()
    if not annoteurs:
        return None

    def pending_count(annoteur):
        return db.query(Capture).filter(
            Capture.annoteur_id == annoteur.id,
            Capture.annoteur_approved == False
        ).count()

    chosen = min(annoteurs, key=lambda a: (pending_count(a), a.id))
    return chosen.id

@router.post("/upload")
def upload_capture(
    machine_id: str = Form(...),
    switch_id: str = Form(...),
    measured_value_mm: float = Form(...),
    p1_x: int = Form(...),
    p1_y: int = Form(...),
    p2_x: int = Form(...),
    p2_y: int = Form(...),
    capture_method: str = Form(...),
    measurement_status: str = Form(...),
    delta_mm: float = Form(...),
    zoom_level: float = Form(None),
    image_original: UploadFile = File(...),
    image_thresholded: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Validate that switch belongs to this machine
        switch = db.query(Switch).filter(Switch.id == switch_id).first()
        if not switch:
            raise HTTPException(status_code=404, detail="Switch not found")
        if switch.machine_id != machine_id:
            raise HTTPException(status_code=400, detail="Switch does not belong to this machine")

        # Generate unique filenames
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        original_filename = f"capture_{timestamp}_{unique_id}_original.png"
        thresholded_filename = f"capture_{timestamp}_{unique_id}_thresholded.png"

        # Save images via the storage layer (Azure Blob in the cloud, local disk
        # otherwise). It returns the key/path to persist on the capture row.
        original_path = save_image("original", original_filename, image_original.file.read())
        thresholded_path = save_image("thresholded", thresholded_filename, image_thresholded.file.read())

        # Fair auto-assignment: give this capture to the active annoteur who
        # currently has the fewest captures still waiting to be verified. This
        # keeps the workload split evenly across all annoteurs.
        assigned_annoteur_id = _pick_least_busy_annoteur(db)

        # Create capture record
        capture = Capture(
            machine_id=machine_id,
            switch_id=switch_id,
            image_original_path=original_path,
            image_thresholded_path=thresholded_path,
            p1_x=p1_x,
            p1_y=p1_y,
            p2_x=p2_x,
            p2_y=p2_y,
            measured_distance_mm=measured_value_mm,
            zoom_level=zoom_level,
            capture_method=capture_method,
            measurement_status=measurement_status,
            delta_mm=delta_mm,
            annoteur_id=assigned_annoteur_id,  # balanced across annoteurs
            annoteur_approved=False,
            in_training_dataset=False
        )

        db.add(capture)
        db.commit()
        db.refresh(capture)

        return {
            "status": "success",
            "capture_id": capture.id,
            "message": "Capture uploaded successfully"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{capture_id}/image")
def get_capture_image(capture_id: str, kind: str = "original", db: Session = Depends(get_db)):
    """Stream a capture's image file over HTTP so clients on other machines can
    see it. `kind` is 'original' or 'thresholded'. The server reads the file
    from its own disk — clients never touch server filesystem paths."""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    key = capture.image_thresholded_path if kind == "thresholded" else capture.image_original_path
    data = read_image(key)
    if data is None:
        raise HTTPException(status_code=404, detail=f"{kind} image file not found on server")

    return Response(content=data, media_type="image/png")

@router.get("/queue", response_model=List[CaptureResponse])
def get_capture_queue(annoteur_id: str, db: Session = Depends(get_db)):
    # Get captures assigned to this annoteur
    captures = db.query(Capture).filter(
        Capture.annoteur_id == annoteur_id,
        Capture.annoteur_approved == False
    ).all()
    return captures

@router.put("/{capture_id}/approve")
def approve_capture(capture_id: str, db: Session = Depends(get_db)):
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    capture.annoteur_approved = True
    db.commit()

    return {"status": "approved", "capture_id": capture_id}

@router.put("/{capture_id}/reject")
def reject_capture(capture_id: str, reason: str = None, db: Session = Depends(get_db)):
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    orig_key, thresh_key = capture.image_original_path, capture.image_thresholded_path
    db.delete(capture)
    db.commit()

    # Clean up the stored images too (best-effort, non-blocking).
    def _cleanup():
        delete_image(orig_key)
        delete_image(thresh_key)
    threading.Thread(target=_cleanup, daemon=True).start()

    return {"status": "rejected", "capture_id": capture_id, "reason": reason}

@router.delete("/{capture_id}")
def delete_capture(capture_id: str, db: Session = Depends(get_db)):
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    # Capture the storage keys before removing the row.
    orig_key = capture.image_original_path
    thresh_key = capture.image_thresholded_path

    # Delete from database immediately
    db.delete(capture)
    db.commit()

    # Delete images (blob or local) in the background so we don't block response.
    def _cleanup():
        delete_image(orig_key)
        delete_image(thresh_key)
    threading.Thread(target=_cleanup, daemon=True).start()

    return {"ok": True, "message": "Capture deleted successfully", "capture_id": capture_id}
