"""Code-based pairing: no tokens copied by hand.

Flow
 1. The dispenser (not yet connected) calls POST /devices/pairing/announce every few
    seconds with its hardware id and a random secret it generated. The server answers
    with a 6-digit code, which the dispenser shows on its OLED.
 2. The web app lists dispensers announcing from the user's network ("found nearby").
 3. The user types the code from the OLED. Only someone who can see the physical screen
    knows it, which is what stops a neighbour on the same network from taking it.
 4. The server creates the device (or reconnects the user's existing device with the
    same hardware id, keeping its containers) and stores a fresh token for the session.
 5. On its next announce, the dispenser (proven by its secret) receives the token and
    saves it in flash. The copy on the server is wiped once the device authenticates.
"""
import hashlib
import ipaddress
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.security import generate_device_token, hash_device_token
from app.models.device import Device, PairingSession
from app.models.user import User
from app.schemas.device import DispenseSettings
from app.schemas.pairing import AnnounceIn, AnnounceOut, ClaimIn, ClaimOut, NearbyDeviceOut
from app.services import device_service
from app.utils.time import as_utc, utcnow


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _code_free(db: Session, code: str | None, own_id=None) -> bool:
    if not code:
        return False
    stmt = select(PairingSession.id).where(PairingSession.pairing_code == code, PairingSession.status == "waiting")
    if own_id is not None:
        stmt = stmt.where(PairingSession.id != own_id)
    return db.scalar(stmt) is None


def _new_code(db: Session) -> str:
    for _ in range(20):
        code = f"{secrets.randbelow(1_000_000):06d}"
        taken = db.scalar(select(PairingSession.id).where(PairingSession.pairing_code == code,
                                                          PairingSession.status == "waiting"))
        if taken is None:
            return code
    raise RuntimeError("Could not allocate a pairing code")


def display_name(hardware_id: str, device_name: str | None = None) -> str:
    suffix = hardware_id[-4:].upper()
    return f"{device_name} · {suffix}" if device_name else f"Diet Balancer dispenser {suffix}"


LOCAL_NETWORKS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16",
    "::1/128", "fc00::/7", "fe80::/10")]


def _is_local(ip) -> bool:
    return any(ip in net for net in LOCAL_NETWORKS if net.version == ip.version)


def same_network(a: str | None, b: str | None) -> bool:
    """Same public address (both behind one home router), or both on home-network
    addresses (the server itself runs inside the home network)."""
    if not a or not b:
        return False
    if a == b:
        return True
    try:
        return _is_local(ipaddress.ip_address(a)) and _is_local(ipaddress.ip_address(b))
    except ValueError:
        return False


def announce(db: Session, data: AnnounceIn, client_ip: str | None) -> AnnounceOut:
    settings = get_settings()
    now = utcnow()
    ttl = settings.PAIRING_CODE_TTL_SECONDS
    session = db.scalar(select(PairingSession).where(PairingSession.secret_hash == _hash(data.pairing_secret))
                        .with_for_update())
    info = {"servo_count": data.servo_count, "hx711_ready": data.hx711_ready, "oled_ready": data.oled_ready,
            "calibrated": data.calibrated}

    if session is None:
        code = data.pairing_code if _code_free(db, data.pairing_code) else _new_code(db)
        session = PairingSession(hardware_id=data.hardware_id, secret_hash=_hash(data.pairing_secret),
                                 pairing_code=code, status="waiting", created_at=now,
                                 last_seen_at=now, expires_at=now + timedelta(seconds=ttl))
        db.add(session)
    elif session.hardware_id != data.hardware_id:
        # The secret belongs to a different device id: treat as a bad request, give nothing away.
        return AnnounceOut(status="waiting", pairing_code=None, expires_in=0)

    session.last_seen_at = now
    session.public_ip = client_ip
    session.local_ip = data.local_ip
    session.firmware_version = data.firmware_version
    session.device_name = (data.device_name or "").strip() or None
    session.hardware_info = info

    if session.status == "waiting" and as_utc(session.expires_at) <= now:
        # Renew the code; keep the one on the OLED if it is still free.
        session.pairing_code = (data.pairing_code if _code_free(db, data.pairing_code, session.id)
                                else _new_code(db))
        session.expires_at = now + timedelta(seconds=ttl)

    if session.status in ("claimed",) and session.pending_token and session.device_id:
        device = db.get(Device, session.device_id)
        db.commit()
        return AnnounceOut(status="paired", device_id=session.device_id, device_token=session.pending_token,
                           device_name=device.name if device else None)
    if session.status != "waiting":
        db.commit()
        return AnnounceOut(status="paired", device_id=session.device_id)  # token already delivered

    try:
        db.commit()
    except IntegrityError:  # extremely unlikely code collision between two concurrent announces
        db.rollback()
        return announce(db, data, client_ip)
    return AnnounceOut(status="waiting", pairing_code=session.pairing_code,
                       expires_in=int((as_utc(session.expires_at) - now).total_seconds()), poll_interval=3)


def nearby(db: Session, user: User, client_ip: str | None) -> list[NearbyDeviceOut]:
    window = timedelta(seconds=get_settings().PAIRING_NEARBY_WINDOW_SECONDS)
    now = utcnow()
    sessions = db.scalars(select(PairingSession).where(
        PairingSession.status == "waiting", PairingSession.last_seen_at >= now - window,
        PairingSession.expires_at > now).order_by(PairingSession.last_seen_at.desc()))
    owned = set(db.scalars(select(Device.hardware_id).where(Device.owner_user_id == user.id,
                                                            Device.hardware_id.is_not(None))))
    out, seen = [], set()
    for s in sessions:
        if not same_network(client_ip, s.public_ip) or s.hardware_id in seen:
            continue
        seen.add(s.hardware_id)
        out.append(NearbyDeviceOut(session_id=s.id, hardware_id=s.hardware_id, display_name=display_name(s.hardware_id, s.device_name),
                                   suggested_name=s.device_name or "Kitchen dispenser",
                                   firmware_version=s.firmware_version, local_ip=s.local_ip,
                                   hardware_info=s.hardware_info or {}, last_seen_at=s.last_seen_at,
                                   already_yours=s.hardware_id in owned))
    return out


def claim(db: Session, user: User, data: ClaimIn) -> ClaimOut:
    now = utcnow()
    session = db.scalar(select(PairingSession).where(
        PairingSession.pairing_code == data.pairing_code, PairingSession.status == "waiting",
        PairingSession.expires_at > now).with_for_update())
    if session is None:
        raise NotFoundError("No dispenser is showing that code. Check the code on its screen and try again.",
                            code="pairing_code_not_found")

    token = generate_device_token()
    device = db.scalar(select(Device).where(Device.owner_user_id == user.id,
                                            Device.hardware_id == session.hardware_id))
    reconnected = device is not None
    if device is None:
        device = Device(owner_user_id=user.id, name=data.name.strip(), hardware_id=session.hardware_id,
                        token_hash=hash_device_token(token), token_hint=token[-4:],
                        dispense_settings=DispenseSettings().model_dump())
        db.add(device)
        db.flush()
        device_service.add_event(db, device, "paired", f"Connected by pairing code ({session.hardware_id}).")
    else:
        device.token_hash = hash_device_token(token)  # the old token stops working
        device.token_hint = token[-4:]
        device_service.add_event(db, device, "re_paired", "Reconnected by pairing code; previous token revoked.",
                                 "warning")
    device.hardware_info = session.hardware_info or device.hardware_info
    device.firmware_version = session.firmware_version

    session.status = "claimed"
    session.claimed_by_user_id = user.id
    session.device_id = device.id
    session.pending_token = token
    db.commit()
    db.refresh(device)
    return ClaimOut(device=device_service.device_out(db, device), reconnected=reconnected,
                    message="Connected. The dispenser will finish setting up in a few seconds.")


def mark_delivered(db: Session, device: Device) -> None:
    """Called when a device authenticates with its token: wipe server-side token copies."""
    db.execute(update(PairingSession).where(PairingSession.device_id == device.id,
                                            PairingSession.status == "claimed")
               .values(status="delivered", pending_token=None))


def cleanup(db: Session) -> None:
    """Remove stale sessions (called opportunistically)."""
    cutoff = utcnow() - timedelta(days=1)
    db.query(PairingSession).filter(PairingSession.last_seen_at < cutoff).delete(synchronize_session=False)
