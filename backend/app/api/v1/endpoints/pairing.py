from fastapi import APIRouter, Depends, Request

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limit
from app.schemas.pairing import AnnounceIn, AnnounceOut, ClaimIn, ClaimOut, NearbyDeviceOut
from app.services import pairing_service

router = APIRouter(prefix="/devices/pairing", tags=["pairing"])


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/announce", response_model=AnnounceOut, tags=["device-api"],
             dependencies=[Depends(rate_limit("pairing_announce", 60, 60))])
def announce(data: AnnounceIn, request: Request, db: DbSession):
    """Called by an unpaired dispenser. No credentials: the 6-digit code shown on its
    screen is what the owner must enter, and the token is only returned to the caller
    that holds the pairing secret."""
    return pairing_service.announce(db, data, client_ip(request))


@router.get("/nearby", response_model=list[NearbyDeviceOut])
def nearby(request: Request, user: CurrentUser, db: DbSession):
    return pairing_service.nearby(db, user, client_ip(request))


@router.post("/claim", response_model=ClaimOut, dependencies=[Depends(rate_limit("pairing_claim", 10, 300))])
def claim(data: ClaimIn, user: CurrentUser, db: DbSession):
    return pairing_service.claim(db, user, data)
