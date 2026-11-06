import uuid

from fastapi import APIRouter, Response

from app.api.deps import DbSession
from app.services import device_service

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/containers/{image_id}")
def container_image(image_id: uuid.UUID, db: DbSession):
    """Food photo for a container card. The id is random and changes whenever the photo changes."""
    data, mime = device_service.get_image(db, image_id)
    return Response(content=data, media_type=mime,
                    headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"})
