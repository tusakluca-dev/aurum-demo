"""Persist actual training runs and expose model changes without claiming improvement."""
import json

FEATURE_NAMES = ('Momentum 1 Kerze', 'Momentum 5 Kerzen', 'Momentum 20 Kerzen', 'Kerzenspanne')


def init_journal(db):
    db.execute('''CREATE TABLE IF NOT EXISTS training_runs
                  (id INTEGER PRIMARY KEY, symbol TEXT, frame TEXT, trained_at REAL, payload TEXT)''')
    db.commit()


def training_details(model, bars, feedback):
    split = int((len(bars)-3)*0.75)
    cutoff = bars[split-3]['time']
    used = sum(row['closed_at'] < cutoff for row in feedback)
    return dict(score=model['score'], approved=model['approved'], samples=model['samples'],
                validation_samples=model['validation_samples'], trade_examples=used,
                candle_examples=model['samples']-used, data_start=bars[20]['time'],
                data_end=bars[-1]['time'], test_start=bars[split]['time'],
                weights=model['weights'].tolist(), mean=model['mean'].tolist(),
                scale=model['scale'].tolist(), feature_names=list(FEATURE_NAMES))


def record_training(db, symbol, frame, trained_at, details):
    row = db.execute('SELECT id, payload FROM training_runs WHERE symbol=? AND frame=? ORDER BY id DESC LIMIT 1',
                     (symbol, frame)).fetchone()
    previous = json.loads(row[1]) if row else None
    payload = dict(details, symbol=symbol, frame=frame, trained_at=trained_at,
                   version=previous['version']+1 if previous else 1,
                   previous_id=row[0] if row else None,
                   score_change_pp=(details['score']-previous['score'])*100 if previous else None)
    payload['weight_changes'] = [dict(name=name, coefficient=details['weights'][i+1],
        change=details['weights'][i+1]-previous['weights'][i+1] if previous else None)
        for i, name in enumerate(FEATURE_NAMES)]
    cursor = db.execute('INSERT INTO training_runs(symbol, frame, trained_at, payload) VALUES (?, ?, ?, ?)',
                        (symbol, frame, trained_at, json.dumps(payload, ensure_ascii=False)))
    db.commit()
    payload['id'] = cursor.lastrowid
    return payload


def training_history(db, limit=40):
    rows = db.execute('SELECT id, payload FROM training_runs ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return [dict(json.loads(payload), id=identifier) for identifier, payload in rows]


def explain_features(model, vector):
    # Exact additive contributions to the logistic model's log-odds, not causal claims.
    return [dict(name=name, value=float(value), weight=float(weight),
                 contribution=float(weight*(value-mean)/scale))
            for name, value, weight, mean, scale in zip(FEATURE_NAMES, vector,
                 model['weights'][1:], model['mean'], model['scale'])]
