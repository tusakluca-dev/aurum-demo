"""Persistent user-selected lot size, with exact broker-step validation."""
from decimal import Decimal, InvalidOperation
from core import position_size


def parse_lots(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('Bitte eine gültige Lotgröße eingeben.')
    try:
        lots = Decimal(str(value).strip().replace(',', '.'))
    except InvalidOperation:
        raise ValueError('Bitte eine gültige Lotgröße eingeben.') from None
    if not lots.is_finite() or lots <= 0 or lots > 1000000 or lots.as_tuple().exponent < -8:
        raise ValueError('Lotgröße muss positiv sein und höchstens 8 Nachkommastellen haben.')
    return lots


def check_broker_lots(value, limits):
    lots = parse_lots(value)
    minimum, maximum, step = (Decimal(str(limits[k])) for k in ('min', 'max', 'step'))
    if not all(v.is_finite() and v > 0 for v in (minimum, maximum, step)) or maximum < minimum:
        raise ValueError('Ungültige Lotgrenzen vom Broker.')
    if not minimum <= lots <= maximum:
        raise ValueError(f'Broker erlaubt {minimum} bis {maximum} Lot.')
    if lots % step != 0:
        raise ValueError(f'Lotgröße muss ein Vielfaches von {step} sein.')
    return float(lots)


class SizingPreferences:
    def __init__(self, db):
        self.db = db
        db.execute('CREATE TABLE IF NOT EXISTS lot_settings (id INTEGER PRIMARY KEY CHECK(id=1), mode TEXT, fixed_lot TEXT)')
        db.execute("INSERT OR IGNORE INTO lot_settings VALUES (1, 'auto', '0.1')")
        db.commit()

    def get(self):
        mode, lots = self.db.execute('SELECT mode,fixed_lot FROM lot_settings WHERE id=1').fetchone()
        return dict(mode=mode, fixed_lot=float(lots))

    def save(self, mode, value, limits=None):
        if mode not in ('auto', 'fixed'):
            raise ValueError('Modus muss automatisch oder feste Lotgröße sein.')
        lots = parse_lots(value)
        if mode == 'fixed' and limits is not None:
            check_broker_lots(lots_to_text(lots), limits)
        self.db.execute('UPDATE lot_settings SET mode=?,fixed_lot=? WHERE id=1', (mode,lots_to_text(lots)))
        self.db.commit()
        return self.get()


def lots_to_text(value):
    return format(value, 'f')


def selected_volume(preferences, budget, loss_per_lot, limits):
    if preferences['mode'] == 'fixed':
        return check_broker_lots(preferences['fixed_lot'], limits)
    if preferences['mode'] != 'auto':
        raise ValueError('Unbekannter Lotmodus')
    return position_size(budget, loss_per_lot, limits['min'], limits['max'], limits['step'])
