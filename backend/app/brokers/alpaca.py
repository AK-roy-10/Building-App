"""Alpaca broker stub. Uses HTTPS REST. Only runs if credentials are set; otherwise raises.

NOTE: This is a minimal real integration suitable for the paper-trading endpoint of Alpaca.
For production, add retries, websockets for streaming, and proper reconciliation.
"""
from __future__ import annotations
import httpx
from .base import BrokerConnector, BrokerOrder, BrokerAccount, BrokerError


class AlpacaBroker(BrokerConnector):
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        if not (api_key and api_secret and base_url):
            raise BrokerError("Alpaca credentials not configured")
        self.base = base_url.rstrip("/")
        self.headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}

    def _get(self, path: str) -> dict:
        r = httpx.get(self.base + path, headers=self.headers, timeout=15.0)
        if r.status_code >= 400:
            raise BrokerError(f"Alpaca GET {path} {r.status_code}: {r.text}")
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = httpx.post(self.base + path, headers=self.headers, json=body, timeout=15.0)
        if r.status_code >= 400:
            raise BrokerError(f"Alpaca POST {path} {r.status_code}: {r.text}")
        return r.json()

    def get_account(self) -> BrokerAccount:
        acct = self._get("/v2/account")
        positions_raw = self._get("/v2/positions")
        positions = {p["symbol"]: {"qty": float(p["qty"]), "avg_price": float(p["avg_entry_price"])}
                     for p in positions_raw}
        cash_cents = int(round(float(acct.get("cash", 0)) * 100))
        return BrokerAccount(cash_cents=cash_cents, positions=positions)

    def get_last_price(self, symbol: str) -> float:
        # Alpaca data API is on a separate host; for the stub we use latest trade snapshot.
        try:
            data = httpx.get(
                f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
                headers=self.headers, timeout=10.0,
            ).json()
            return float(data.get("trade", {}).get("p", 0.0)) or 0.0
        except Exception:
            return 0.0

    def place_order(self, *, symbol: str, side: str, qty: float,
                    order_type: str = "market", limit_price: float | None = None,
                    idempotency_key: str) -> BrokerOrder:
        body = {
            "symbol": symbol, "qty": qty, "side": side, "type": order_type,
            "time_in_force": "day", "client_order_id": idempotency_key,
        }
        if order_type == "limit" and limit_price is not None:
            body["limit_price"] = limit_price
        resp = self._post("/v2/orders", body)
        return BrokerOrder(
            broker_order_id=resp.get("id", ""),
            status=resp.get("status", "new"),
            filled_qty=float(resp.get("filled_qty", 0) or 0),
            avg_fill_price=float(resp.get("filled_avg_price") or 0),
            raw=resp,
        )

    def cancel_order(self, broker_order_id: str) -> None:
        r = httpx.delete(self.base + f"/v2/orders/{broker_order_id}", headers=self.headers, timeout=15.0)
        if r.status_code >= 400 and r.status_code != 404:
            raise BrokerError(f"Cancel failed {r.status_code}: {r.text}")
