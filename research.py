"""Constrained strategy research. Signals use only completed bars; fills use next opens."""
import math
import numpy as np
from core import features

FAMILIES = ('momentum', 'mean_reversion', 'breakout')
DEFAULT_STRATEGY = dict(family='momentum', lookback=20, threshold_atr=1.0,
                        stop_atr=2.0, reward_risk=1.5, max_hold_bars=12)


def validate_strategy(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT_STRATEGY):
        raise ValueError('Strategie muss exakt die dokumentierten Parameter enthalten.')
    result = dict(value)
    if result['family'] not in FAMILIES:
        raise ValueError('Unbekannte Strategiefamilie')
    for key, low, high in [('lookback', 5, 100), ('max_hold_bars', 1, 100)]:
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError('Ungültiger ganzzahliger Parameter: '+key)
    for key, low, high in [('threshold_atr', .1, 5), ('stop_atr', .5, 5), ('reward_risk', .5, 4)]:
        if type(result[key]) not in (int, float) or not math.isfinite(result[key]) or not low <= result[key] <= high:
            raise ValueError('Ungültiger Parameter: '+key)
    return result


def signal(strategy, bars, atr):
    strategy = validate_strategy(strategy)
    n = strategy['lookback']
    if len(bars) <= n or atr <= 0:
        return 0
    close = bars[-1]['close']
    previous = bars[-n-1:-1]
    threshold = strategy['threshold_atr']*atr
    if strategy['family'] == 'breakout':
        if close > max(b['high'] for b in previous)+threshold:
            return 1
        if close < min(b['low'] for b in previous)-threshold:
            return -1
        return 0
    delta = close-bars[-n-1]['close']
    direction = 1 if delta > threshold else -1 if delta < -threshold else 0
    return -direction if strategy['family'] == 'mean_reversion' else direction


def backtest(strategy, bars, start, end, spread_fallback=0., slippage=0., commission=0.):
    """Non-compounding R returns with per-bar bid/ask costs. No simultaneous positions.

    Positions are flat at interval boundaries. Same-bar SL+TP ambiguity uses SL first.
    Risk budget, lot discretisation and broker margin are not simulated here.
    """
    validate_strategy(strategy)
    if not 101 <= start < end <= len(bars):
        raise ValueError('Ungültiges Testintervall')
    if any(not math.isfinite(v) or v < 0 for v in (spread_fallback, slippage, commission)):
        raise ValueError('Ungültige Handelskosten')
    _, atrs = features(bars[:end])
    trades, position = [], None
    for i in range(start, end):
        bar = bars[i]
        spread = max(float(bar.get('spread', spread_fallback)), 0.)
        if position is None:
            atr = float(atrs[i-1])
            direction = signal(strategy, bars[max(0, i-102):i], atr)
            if not direction:
                continue
            entry = bar['open']+(spread if direction == 1 else 0)+direction*slippage
            distance = atr*strategy['stop_atr']
            if distance <= 0:
                continue
            position = dict(direction=direction, entry=entry, distance=distance,
                            stop=entry-direction*distance, take=entry+direction*distance*strategy['reward_risk'], opened=i)
        p = position
        direction = p['direction']
        # OHLC are bid prices. Short exits buy at ask.
        offset = spread if direction == -1 else 0.
        op, hi, lo, cl = (bar[k]+offset for k in ('open', 'high', 'low', 'close'))
        stop_gap = op <= p['stop'] if direction == 1 else op >= p['stop']
        take_gap = op >= p['take'] if direction == 1 else op <= p['take']
        stop_hit = lo <= p['stop'] if direction == 1 else hi >= p['stop']
        take_hit = hi >= p['take'] if direction == 1 else lo <= p['take']
        exit_price = None
        if stop_gap:
            exit_price = op
        elif take_gap:
            exit_price = p['take']  # Never assume favourable gap improvement.
        elif stop_hit:
            exit_price = p['stop']
        elif take_hit:
            exit_price = p['take']
        elif i-p['opened']+1 >= strategy['max_hold_bars'] or i == end-1:
            exit_price = cl
        if exit_price is not None:
            exit_price -= direction*slippage
            pnl = (direction*(exit_price-p['entry'])-commission)/p['distance']
            trades.append(dict(opened=p['opened'], closed=i, r=float(pnl)))
            position = None
    returns = [t['r'] for t in trades]
    equity, peak, drawdown = 0., 0., 0.
    for r in returns:
        equity += r
        peak = max(peak, equity)
        drawdown = max(drawdown, peak-equity)
    return dict(trades=len(returns), net_r=float(sum(returns)), max_drawdown_r=float(drawdown),
                mean_r=float(np.mean(returns)) if returns else 0.,
                win_rate=float(np.mean(np.array(returns)>0)) if returns else 0.,
                start_time=bars[start]['time'], end_time=bars[end-1]['time'])


def passes(metrics, minimum=30):
    return (metrics['trades'] >= minimum and metrics['net_r'] > 0
            and metrics['max_drawdown_r'] <= 10 and metrics['mean_r'] >= .05)


def evaluate_candidate(candidate, incumbent, bars, costs, minimum=30):
    """Single proposed candidate, development 60%, validation 20%, untouched final 20%."""
    if len(bars) < 1000:
        raise ValueError('Mindestens 1.000 Kerzen für Strategieforschung erforderlich')
    candidate, incumbent = validate_strategy(candidate), validate_strategy(incumbent)
    split, final = int(len(bars)*.6), int(len(bars)*.8)
    val = backtest(candidate, bars, split, final, **costs)
    reference_val = backtest(incumbent, bars, split, final, **costs)
    test = backtest(candidate, bars, final, len(bars), **costs)
    reference_test = backtest(incumbent, bars, final, len(bars), **costs)
    # Baseline is tested again on exactly the same new observations.
    better = (passes(val, minimum) and passes(test, minimum)
              and val['net_r'] > reference_val['net_r'] and test['net_r'] > reference_test['net_r'])
    keep = passes(reference_val, minimum) and passes(reference_test, minimum)
    selected = candidate if better else incumbent if keep else None
    return dict(candidate=candidate, reference=incumbent, validation=val, final_test=test,
                reference_validation=reference_val, reference_test=reference_test,
                promoted=better, selected=selected,
                selection_reason='Kandidat besteht Prüfungen und übertrifft Referenz' if better else
                    'Referenz bleibt: Kandidat ist nicht nachweislich besser in diesen Tests' if keep else
                    'Keine Strategie besteht die festgelegten Prüfungen',
                tested_until=bars[-1]['time'], development_end=bars[split-1]['time'])


def development_summary(bars):
    # Never send validation/final observations to the strategy proposer.
    dev = bars[:int(len(bars)*.6)]
    prices = np.array([b['close'] for b in dev])
    _, atr = features(dev)
    return dict(samples=len(dev), start=dev[0]['time'], end=dev[-1]['time'],
                change_percent=float((prices[-1]/prices[0]-1)*100),
                mean_atr=float(atr[20:].mean()), last_close=float(prices[-1]),
                recent_candles=dev[-60:])
