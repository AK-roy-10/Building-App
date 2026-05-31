"""Smoke tests for Phase 1 expansion: markets, LLM catalog, broker capabilities."""
from datetime import datetime, timedelta


def _signup(client):
    r = client.post("/api/auth/signup", json={
        "email": "p1@example.com", "password": "password123",
        "org_name": "P1Org", "accept_risk_disclaimer": True})
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_market_metadata_endpoints(client):
    _signup(client)
    r = client.get("/api/asset-classes")
    assert r.status_code == 200, r.text
    codes = [a["code"] for a in r.json()]
    assert "equity" in codes and "crypto" in codes and "forex" in codes

    r = client.get("/api/timeframes")
    assert r.status_code == 200
    tfs = [t["code"] for t in r.json()]
    assert "1m" in tfs and "1d" in tfs and "1M" in tfs

    r = client.get("/api/data-providers")
    assert r.status_code == 200
    codes = [p["code"] for p in r.json()]
    assert "synthetic" in codes


def test_llm_catalog_endpoints(client):
    _signup(client)
    r = client.get("/api/llm/providers")
    assert r.status_code == 200, r.text
    codes = [p["code"] for p in r.json()]
    assert {"mock", "openai", "anthropic", "gemini", "ollama", "hugging_face"} <= set(codes)

    r = client.get("/api/llm/models?tag=finance")
    assert r.status_code == 200
    models = r.json()
    assert len(models) > 0
    finance_ids = {m["id"] for m in models}
    # at least one open finance-tuned model present
    assert any("fin" in mid.lower() or "finance" in mid.lower() for mid in finance_ids)


def test_broker_catalog_lists_stub_adapters(client):
    _signup(client)
    r = client.get("/api/broker-connections/catalog")
    assert r.status_code == 200, r.text
    codes = {b["code"] for b in r.json()}
    assert {"paper", "alpaca", "ccxt", "binance", "coinbase", "kraken",
            "oanda", "ib", "tradier"} <= codes


def test_paper_broker_verify(client):
    _signup(client)
    r = client.post("/api/broker-connections", json={
        "broker": "paper", "label": "p", "trade_scope": "paper"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = client.post(f"/api/broker-connections/{cid}/verify")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_agent_create_accepts_new_fields_then_backtest(client):
    _signup(client)
    r = client.post("/api/broker-connections", json={
        "broker": "paper", "label": "p", "trade_scope": "paper"})
    bid = r.json()["id"]
    r = client.post("/api/agents", json={
        "name": "A1", "strategy_code": "momentum",
        "config": {"symbol": "AAPL", "qty": 1, "threshold_pct": 1.0},
        "automation": "suggest", "model_code": "mock",
        "asset_class": "equity", "timeframe": "1d",
        "data_provider": "synthetic", "llm_provider": "mock",
        "broker_connection_id": bid, "allowed_symbols": ["AAPL"]})
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert r.json()["asset_class"] == "equity"
    assert r.json()["timeframe"] == "1d"

    # Backtest
    r = client.post(f"/api/agents/{aid}/backtest", json={
        "starting_cash_cents": 100_000_00})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["agent_id"] == aid
    assert body["n_bars"] > 0
    assert "pnl" in body["result"]
