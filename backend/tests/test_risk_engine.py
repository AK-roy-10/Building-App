"""Risk engine tests — the safety-critical core."""
from app.risk_engine import Proposal, AccountState, RiskPolicy, evaluate


def _policy(**kw):
    base = dict(automation="paper", trade_scope="paper",
                max_position_notional_cents=10_000_00,
                max_orders_per_run=3,
                allowed_symbols=[],
                org_daily_loss_limit_cents=10_000_00,
                org_kill_switch=False,
                risk_ack_accepted=True,
                price_hint=100.0)
    base.update(kw)
    return RiskPolicy(**base)


def _acct(cash=100_000_00, positions=None, pnl=0):
    return AccountState(cash_cents=cash, positions=positions or {}, realised_pnl_today_cents=pnl)


def test_suggest_mode_blocks_orders():
    v = evaluate(Proposal("AAPL", "buy", 1), _acct(), _policy(automation="suggest"))
    assert v.verdict == "rejected"
    assert any("suggest" in r for r in v.reasons)


def test_kill_switch_blocks_orders():
    v = evaluate(Proposal("AAPL", "buy", 1), _acct(), _policy(org_kill_switch=True))
    assert v.verdict == "rejected"


def test_risk_ack_required():
    v = evaluate(Proposal("AAPL", "buy", 1), _acct(), _policy(risk_ack_accepted=False))
    assert v.verdict == "rejected"


def test_symbol_allowlist():
    v = evaluate(Proposal("TSLA", "buy", 1), _acct(),
                 _policy(allowed_symbols=["AAPL", "MSFT"]))
    assert v.verdict == "rejected"
    assert any("allowlist" in r for r in v.reasons)


def test_notional_cap_hard_rejects():
    # price 100 * qty 200 = $20,000 > $10,000 cap
    v = evaluate(Proposal("AAPL", "buy", 200), _acct(), _policy())
    assert v.verdict == "rejected"


def test_insufficient_cash():
    v = evaluate(Proposal("AAPL", "buy", 50),
                 _acct(cash=100_00), _policy(max_position_notional_cents=999_999_99))
    assert v.verdict == "rejected"


def test_insufficient_position_for_sell():
    v = evaluate(Proposal("AAPL", "sell", 5), _acct(),
                 _policy(max_position_notional_cents=999_999_99))
    assert v.verdict == "rejected"


def test_daily_loss_limit():
    v = evaluate(Proposal("AAPL", "buy", 1),
                 _acct(pnl=-10_000_00), _policy())
    assert v.verdict == "rejected"


def test_live_requires_live_scope():
    v = evaluate(Proposal("AAPL", "buy", 1), _acct(),
                 _policy(automation="live_manual", trade_scope="paper"))
    assert v.verdict == "rejected"


def test_live_manual_requires_approval():
    v = evaluate(Proposal("AAPL", "buy", 1), _acct(),
                 _policy(automation="live_manual", trade_scope="live"))
    assert v.verdict == "requires_user_approval"


def test_large_relative_notional_requires_approval_in_live_auto():
    # 100 * 100 = $10,000 vs $20,000 cash → 50% > 25% threshold
    v = evaluate(Proposal("AAPL", "buy", 100),
                 _acct(cash=20_000_00),
                 _policy(automation="live_auto", trade_scope="live",
                         max_position_notional_cents=999_999_99))
    assert v.verdict == "requires_user_approval"


def test_orders_per_run_cap():
    v = evaluate(Proposal("AAPL", "buy", 1), _acct(),
                 _policy(max_orders_per_run=2), orders_already_this_run=2)
    assert v.verdict == "rejected"


def test_happy_path_paper_auto_approves():
    v = evaluate(Proposal("AAPL", "buy", 1), _acct(), _policy())
    assert v.verdict == "approved"
    assert v.checks["max_position_notional"] is True
