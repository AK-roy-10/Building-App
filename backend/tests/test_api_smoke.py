"""Smoke test the HTTP API end-to-end."""
def test_signup_login_and_list_strategies(client):
    r = client.post("/api/auth/signup", json={
        "email": "alice@example.com", "password": "supersecret",
        "org_name": "Acme", "accept_risk_disclaimer": True,
    })
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    hdrs = {"Authorization": f"******"}

    me = client.get("/api/me", headers=hdrs).json()
    assert me["user"]["email"] == "alice@example.com"
    assert me["plan"] == "free"

    strategies = client.get("/api/agents/strategies").json()
    assert any(s["code"] == "momentum" for s in strategies)


def test_free_plan_cannot_use_live_automation(client):
    r = client.post("/api/auth/signup", json={
        "email": "b@example.com", "password": "supersecret",
        "org_name": "Bee Org", "accept_risk_disclaimer": True,
    })
    token = r.json()["access_token"]
    hdrs = {"Authorization": f"******"}
    r = client.post("/api/broker-connections", headers=hdrs, json={
        "broker": "paper", "label": "P", "trade_scope": "paper"})
    assert r.status_code == 201

    r = client.post("/api/agents", headers=hdrs, json={
        "name": "X", "strategy_code": "momentum",
        "config": {"symbol": "AAPL", "qty": 1, "threshold_pct": 1},
        "automation": "live_manual", "model_code": "mock",
    })
    assert r.status_code == 402  # entitlement error
