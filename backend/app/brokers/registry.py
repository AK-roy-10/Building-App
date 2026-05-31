"""Factory: turn a BrokerConnection row into a live BrokerConnector + capability registry."""
from __future__ import annotations
import json
from sqlalchemy.orm import Session

from .. import models
from ..auth import decrypt_secret
from ..config import get_settings
from .base import BrokerConnector, BrokerError, BrokerCapabilities
from .paper import PaperBroker
from .alpaca import AlpacaBroker
from .stubs import STUB_BROKERS


# All known broker codes with their capability cards (used by the UI + entitlements).
def list_broker_catalog() -> list[dict]:
    cards: list[BrokerCapabilities] = [PaperBroker.capabilities, AlpacaBroker.capabilities]
    cards += [cls.capabilities for cls in STUB_BROKERS.values()]
    return [c.to_dict() for c in cards]


def get_broker_capabilities(code: str) -> BrokerCapabilities:
    for c in [PaperBroker.capabilities, AlpacaBroker.capabilities,
              *[cls.capabilities for cls in STUB_BROKERS.values()]]:
        if c.code == code:
            return c
    raise BrokerError(f"Unknown broker: {code}")


def get_broker(db: Session, conn: models.BrokerConnection) -> BrokerConnector:
    if not conn.enabled:
        raise BrokerError("Broker connection is disabled")
    if conn.broker == "paper":
        return PaperBroker(db, conn)
    if conn.broker == "alpaca":
        s = get_settings()
        creds = {}
        if conn.encrypted_credentials:
            try:
                creds = json.loads(decrypt_secret(conn.encrypted_credentials))
            except Exception:
                creds = {}
        key = creds.get("api_key") or s.alpaca_api_key
        secret = creds.get("api_secret") or s.alpaca_api_secret
        return AlpacaBroker(key, secret, s.alpaca_base_url)
    if conn.broker in STUB_BROKERS:
        creds = {}
        if conn.encrypted_credentials:
            try:
                creds = json.loads(decrypt_secret(conn.encrypted_credentials))
            except Exception:
                creds = {}
        return STUB_BROKERS[conn.broker](**creds)
    raise BrokerError(f"Unknown broker: {conn.broker}")


# All recognized broker codes (for validation in the API).
def known_broker_codes() -> list[str]:
    return ["paper", "alpaca", *STUB_BROKERS.keys()]

