"""Risk rules and an experimental, chronologically validated logistic model."""
import math
from datetime import datetime, timezone
import numpy as np


def features(bars):
    c = np.array([b['close'] for b in bars], float)
    h = np.array([b['high'] for b in bars], float)
    l = np.array([b['low'] for b in bars], float)
    tr = np.maximum(h-l, np.maximum(abs(h-np.roll(c, 1)), abs(l-np.roll(c, 1))))
    tr[0] = h[0]-l[0]
    atr = np.convolve(tr, np.ones(14)/14, 'full')[:len(c)]
    atr = np.maximum(atr, 1e-8)
    x = np.zeros((len(c), 4))
    for i in range(20, len(c)):
        x[i] = [(c[i]-c[i-1])/atr[i], (c[i]-c[i-5])/atr[i],
                (c[i]-c[i-20])/atr[i], (h[i]-l[i])/atr[i]]
    return np.clip(x, -10, 10), atr


def sigmoid(x):
    return 1/(1+np.exp(-np.clip(x, -30, 30)))


def train(bars, feedback=()):
    x, atr = features(bars)
    c = np.array([b['close'] for b in bars], float)
    # A three-bar forecast. Purge three bars before the chronological holdout.
    end = len(c)-3
    split = int(end*0.75)
    tx = x[20:split-3]
    ty = (c[23:split] > c[20:split-3]).astype(float)
    cutoff = bars[split-3]['time']
    # Only earlier completed trades enter training; never the validation interval.
    for row in feedback:
        if row['closed_at'] < cutoff:
            tx = np.vstack([tx, row['features']])
            ty = np.append(ty, row['label'])
    mean, scale = tx.mean(axis=0), np.maximum(tx.std(axis=0), 0.1)
    z = np.column_stack([np.ones(len(tx)), (tx-mean)/scale])
    w = np.zeros(5)
    for _ in range(300):
        w -= 0.04*(z.T@(sigmoid(z@w)-ty)/len(ty) + 0.002*np.r_[0, w[1:]])
    vx = np.column_stack([np.ones(end-split), (x[split:end]-mean)/scale])
    predicted = sigmoid(vx@w) >= 0.5
    truth = c[split+3:] > c[split:end]
    recalls = [float((predicted[truth == t] == t).mean()) if (truth == t).any() else 0 for t in (False, True)]
    score = sum(recalls)/2
    return {'weights': w, 'mean': mean, 'scale': scale, 'score': score,
            'samples': len(tx), 'validation_samples': len(truth), 'approved': score >= 0.55}


def probability(model, x):
    return float(sigmoid(np.r_[1, (np.array(x)-model['mean'])/model['scale']] @ model['weights']))


def zone_reason(config, price, spread, atr, now=None):
    now = now or datetime.now(timezone.utc)
    if atr <= 0 or spread/atr > config['max_spread_atr']:
        return 'Spread zu hoch'
    if now.hour in config['blocked_hours_utc']:
        return 'Gesperrte Handelszeit (UTC)'
    for low, high in config['price_zones']:
        if low <= price <= high:
            return 'Gesperrte Preiszone'
    for start, end in config['blocked_windows_utc']:
        if datetime.fromisoformat(start) <= now <= datetime.fromisoformat(end):
            return 'Manuelle Ereignissperre'
    return None


def position_size(budget, loss_per_lot, minimum, maximum, step):
    if budget <= 0 or loss_per_lot <= 0 or step <= 0:
        return 0.0
    size = math.floor(min(budget/loss_per_lot, maximum)/step + 1e-9)*step
    # Never round UP to the broker minimum: that would exceed the risk budget.
    return round(size, 8) if size >= minimum else 0.0
