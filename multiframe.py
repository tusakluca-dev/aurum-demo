"""Independent models per MT5 timeframe, with explicit abstention."""
import time
from core import features, train, probability
from learning import training_details, explain_features


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
    def __init__(self, recorder=None):
        self.models = {}
        self.recorder = recorder
        self.audits = {}

    def evaluate(self, symbol, frame, bars, feedback):
        key = (symbol, frame)
        cached = self.models.get(key)
        if cached is None or time.time()-cached[0] >= 3600:
            cached = (time.time(), train(bars, feedback))
            details = training_details(cached[1], bars, feedback)
            if self.recorder:
                details = self.recorder(symbol, frame, cached[0], details)
            self.audits[key] = details
            self.models[key] = cached
        model = cached[1]
        x, _ = features(bars)
        report = {k: model[k] for k in ('score', 'samples', 'validation_samples', 'approved')}
        report.update(available=True, probability=probability(model, x[-1]),
                      last_closed_bar=bars[-1]['time'], trained_at=cached[0],
                      learning=self.audits[key], influences=explain_features(model, x[-1]))
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
