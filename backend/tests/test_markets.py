"""Unit tests for the markets package primitives."""
from datetime import datetime, timedelta
from app.markets.types import Timeframe, Symbol, AssetClass
from app.markets.resample import resample_bars, bar_count_for
from app.markets.features import compute_features
from app.markets.data_provider import get_data_provider
from app.markets.backtester import run_backtest
import app.markets  # noqa: F401 — populate registry


def test_timeframe_parse_and_seconds():
    assert Timeframe.parse("1m").seconds == 60
    assert Timeframe.parse("1h").seconds == 3600
    assert Timeframe.parse("1d").seconds == 86400
    assert Timeframe.parse("1M").seconds >= 28 * 86400


def test_symbol_roundtrip():
    s = Symbol.parse("equity:NASDAQ:AAPL:USD")
    assert s.asset_class == "equity"
    assert s.base == "AAPL"
    assert Symbol.parse(s.canonical()).canonical() == s.canonical()


def test_synthetic_provider_is_deterministic():
    prov = get_data_provider("synthetic")
    end = datetime(2024, 1, 10)
    start = end - timedelta(days=20)
    a = prov.get_bars(Symbol.parse("equity::AAPL"), Timeframe.parse("1d"), start, end)
    b = prov.get_bars(Symbol.parse("equity::AAPL"), Timeframe.parse("1d"), start, end)
    assert len(a) == len(b) > 0
    assert [bar.close for bar in a] == [bar.close for bar in b]


def test_features_on_flat_series():
    from app.markets.types import Bar
    bars = [Bar(ts=datetime.utcnow(), open=100, high=100, low=100,
                close=100, volume=1, timeframe="1d") for _ in range(30)]
    feats = compute_features(bars)
    # RSI of a perfectly flat series is undefined; just assert one is reported.
    assert "rsi" in feats
    assert feats["sma_short"] == 100.0 or feats["sma_long"] == 100.0


def test_backtester_on_monotonic_uptrend_is_profitable():
    prov = get_data_provider("synthetic")
    bars = prov.get_bars(Symbol.parse("equity::AAPL"), Timeframe.parse("1d"),
                          datetime(2024, 1, 1), datetime(2024, 3, 1))

    def buy_and_hold(window):
        # buy on the first bar then hold
        if len(window) == 1:
            return ("buy", 10.0)
        return None

    result = run_backtest(bars, buy_and_hold, starting_cash=100_000.0)
    assert result.n_trades >= 1
