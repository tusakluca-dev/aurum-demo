"""Independent models per MT5 timeframe, with explicit abstention."""
import time
from core import features, train, probability


def feedback_by_frame(rows):
    grouped = {}
    for row in rows:
        # Existing installations stored only M5 vectors. Never assign these to other frames.
        vectors = row['features']
        if isinstance(vectors, list):
            vectors = {'M5': vectors}
        for frame, vector in vectors.items():
            grouped.setdefault(frame, []).append(dict(closed_at=row['closed_at'],
                                                      label=row['label'], features=vector))
    return grouped


class FrameLearner:
    def __init__(self):
        self.models = {}

    def evaluate(self, symbol, frame, bars, feedback):
        key = (symbol, frame)
        cached = self.models.get(key)
        if cached is None or time.time()-cached[0] >= 3600:
            cached = (time.time(), train(bars, feedback))
            self.models[key] = cached
        model = cached[1]
        x, _ = features(bars)
        report = {k: model[k] for k in ('score', 'samples', 'validation_samples', 'approved')}
        report.update(available=True, probability=probability(model, x[-1]),
                      last_closed_bar=bars[-1]['time'], trained_at=cached[0])
        return report, x[-1].tolist()


def consensus(reports, execution, threshold, minimum):
    if not 0.5 < threshold < 1 or not 1 <= minimum <= len(reports):
        raise ValueError('Ungültige Signalgrenze oder Anzahl Bestätigungen')
    base = reports.get(execution, {})
    p = base.get('probability', 0.5)
    if not base.get('available') or not base.get('approved'):
        return p, 'Ausführungsmodell besteht Validierung nicht'
    if max(p, 1-p) < threshold:
        return p, 'Signal der Ausführungszeitebene zu unsicher'
    votes = []
    for report in reports.values():
        if report.get('available') and report.get('approved'):
            q = report['probability']
            if max(q, 1-q) >= threshold:
                votes.append(q > 0.5)
    direction = p > 0.5
    if any(v != direction for v in votes):
        return p, 'Zeitebenen liefern widersprüchliche Signale'
    if sum(v == direction for v in votes) < minimum:
        return p, 'Zu wenige bestätigende Zeitebenen'
    return p, None
