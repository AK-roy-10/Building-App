"""Factory: turn a BrokerConnection row into a live BrokerConnector."""
from __future__ import annotations
import json
from sqlalchemy.orm import Session

from .. import models
from ..auth import decrypt_secret
from ..config import get_settings
from .base import BrokerConnector, BrokerError
from .paper import PaperBroker
from .alpaca import AlpacaBroker


def get_broker(db: Session, conn: models.BrokerConnection) -> BrokerConnector:
    if not conn.enabled:
        raise BrokerError("Broker connection is disabled")
    if conn.broker == "paper":
        return PaperBroker(db, conn)
    if conn.broker == "alpaca":
        s = get_settings()
        # Prefer per-connection credentials; fall back to env defaults (e.g., for dev).
        creds = {}
        if conn.encrypted_credentials:
            try:
                creds = json.loads(decrypt_secret(conn.encrypted_credentials))
            except Exception:
                creds = {}
        key = creds.get("api_key") or s.alpaca_api_key
        secret = creds.get("api_secret") or s.alpaca_api_secret
        return AlpacaBroker(key, secret, s.alpaca_base_url)
    raise BrokerError(f"Unknown broker: {conn.broker}")
