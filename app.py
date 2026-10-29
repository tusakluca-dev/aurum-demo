"""Local-only MT5 demo research terminal. No credentials are accepted by this app."""
import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from core import features, zone_reason
from multiframe import FrameLearner, feedback_by_frame, consensus
from learning import init_journal, record_training, training_history
from local_ai import load_settings, ResearchJournal, run_research, research_entry_reason
from automation import Autopilot
from sizing import SizingPreferences, selected_volume

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
AI_LOCK = threading.RLock()
AI_EVENT = threading.Event()
AI_INPUT = None
AI_STATE = {'status': 'Lokale KI noch nicht gestartet', 'busy': False, 'result': None, 'history': []}
LOCK = threading.RLock()
STATE = {'running': False, 'status': 'Warte auf MT5', 'connected': False, 'model': None}
DB = sqlite3.connect(ROOT/'trades.sqlite', check_same_thread=False)
DB.execute('CREATE TABLE IF NOT EXISTS entries (ticket INTEGER PRIMARY KEY, position_id INTEGER, time REAL, direction INTEGER, features TEXT)')
DB.execute('CREATE TABLE IF NOT EXISTS feedback (ticket INTEGER PRIMARY KEY, closed_at REAL, label REAL, features TEXT, pnl REAL)')
DB.execute('CREATE TABLE IF NOT EXISTS daily (day TEXT, account TEXT, equity REAL, PRIMARY KEY(day, account))')
DB.execute('CREATE TABLE IF NOT EXISTS execution_plans (position_id INTEGER PRIMARY KEY, signal_time REAL, hold_bars INTEGER, frame TEXT)')
DB.commit()
init_journal(DB)
AUTOPILOT = Autopilot(DB)
SIZING = SizingPreferences(DB)


def config():
    return json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))


def assert_demo(mt):
    account = mt.account_info()
    if account is None or account.trade_mode != mt.ACCOUNT_TRADE_MODE_DEMO:
        raise RuntimeError('Kein Demokonto verbunden. Handel gesperrt.')
    return account


def sync_feedback(mt, account_key):
    # Join fills by position_id, never infer trade results from individual close fills.
    rows = DB.execute('SELECT ticket, position_id, time, direction, features FROM entries WHERE ticket NOT IN (SELECT ticket FROM feedback)').fetchall()
    positions = mt.positions_get()
    if positions is None:
        raise RuntimeError('Offene Positionen für Trade-Auswertung nicht lesbar')
    active = {p.identifier for p in positions}
    for ticket, pid, opened, direction, fs in rows:
        if not pid or pid in active:
            continue
        deals = mt.history_deals_get(position=pid)
        if deals is None or not any(d.entry in (mt.DEAL_ENTRY_OUT, mt.DEAL_ENTRY_OUT_BY) for d in deals):
            continue
        # Database belongs to a single account; enforced by the worker below.
        pnl = sum(d.profit+d.commission+d.swap+d.fee for d in deals)
        if pnl == 0:
            continue
        label = float((direction == 1) == (pnl > 0))
        DB.execute('INSERT OR IGNORE INTO feedback VALUES (?, ?, ?, ?, ?)',
                   (ticket, max(d.time for d in deals), label, fs, pnl))
    DB.commit()


def research_worker():
    journal = ResearchJournal(ROOT/'research.sqlite')
    next_run = 0
    while True:
        forced = AI_EVENT.wait(5)
        AI_EVENT.clear()
        with AI_LOCK:
            snapshot = AI_INPUT
        if snapshot is None or (not forced and time.time() < next_run):
            continue
        try:
            settings = load_settings(ROOT)
            with AI_LOCK:
                AI_STATE.update(busy=True, status='Lokales Sprachmodell analysiert Quellen und Strategieideen …')
                if AI_STATE['result'] is None:
                    stored = journal.history(snapshot['symbol'], snapshot['frame'])
                    if stored:
                        AI_STATE['result'] = stored[0]
            result = run_research(settings, snapshot, journal)
            with AI_LOCK:
                AI_STATE.update(busy=False, result=result,
                    status=('Neuer Strategietest abgeschlossen' if result['new_strategy_test'] else
                            'Nachrichten aktualisiert; warte auf einen neuen unabhängigen Testzeitraum'),
                    history=journal.history(snapshot['symbol'], snapshot['frame']))
            next_run = time.time()+settings['interval_minutes']*60
        except Exception as exc:
            with AI_LOCK:
                AI_STATE.update(busy=False,status='Lokale KI nicht bereit: '+str(exc))
            next_run = time.time()+60


def manage_research_exits(mt, cfg, expected_account):
    positions = mt.positions_get(symbol=cfg['symbol'])
    if positions is None:
        raise RuntimeError('Positionen für Zeitausstiege nicht lesbar')
    for position in positions:
        if position.magic != cfg['magic']:
            continue
        plan = DB.execute('SELECT signal_time, hold_bars, frame FROM execution_plans WHERE position_id=?',
                          (position.identifier,)).fetchone()
        if not plan:
            continue
        rates = mt.copy_rates_from_pos(cfg['symbol'], getattr(mt, 'TIMEFRAME_'+plan[2]), 1, plan[1]+2)
        if rates is None:
            raise RuntimeError('Kerzen für Zeitausstieg nicht lesbar')
        if sum(float(b['time']) > plan[0] for b in rates) < plan[1]:
            continue
        assert_demo(mt)
        tick = mt.symbol_info_tick(cfg['symbol'])
        info = mt.symbol_info(cfg['symbol'])
        if tick is None or time.time()-tick.time > 60:
            raise RuntimeError('Keine aktuellen Kurse für Zeitausstieg')
        buy = position.type == mt.POSITION_TYPE_BUY
        current = assert_demo(mt)
        if f'{current.server}:{current.login}' != expected_account:
            raise RuntimeError('Kontowechsel vor Zeitausstieg erkannt')
        result = mt.order_send(dict(action=mt.TRADE_ACTION_DEAL, position=position.ticket,
            symbol=cfg['symbol'], volume=position.volume,
            type=mt.ORDER_TYPE_SELL if buy else mt.ORDER_TYPE_BUY,
            price=tick.bid if buy else tick.ask, deviation=20, magic=cfg['magic'],
            comment='Aurum research time exit', type_time=mt.ORDER_TIME_GTC,
            type_filling=mt.ORDER_FILLING_FOK if info.filling_mode & 1 else mt.ORDER_FILLING_IOC))
        if result is None or result.retcode != mt.TRADE_RETCODE_DONE:
            raise RuntimeError('Zeitausstieg nicht vollständig bestätigt. Position in MT5 prüfen.')


def worker():
    global AI_INPUT
    try:
        import MetaTrader5 as mt
    except ImportError:
        with LOCK:
            STATE['status'] = 'Windows + MetaTrader5-Paket erforderlich. Siehe README.'
        return
    learner = FrameLearner(lambda symbol, frame, at, details:
                           record_training(DB, symbol, frame, at, details))
    last_bar, bound_account = None, None
    while True:
        try:
            with LOCK:
                intent = AUTOPILOT.state()
                STATE.update(trading_requested=intent['requested'], halt_reason=intent['halt_reason'])
                cfg = config()
                if not mt.initialize():
                    raise RuntimeError('MT5 nicht erreichbar. Terminal öffnen und Demokonto anmelden.')
                account = assert_demo(mt)
                key = f'{account.server}:{account.login}'
                saved = ROOT/'account.json'
                if saved.exists() and json.loads(saved.read_text(encoding='utf-8-sig'))['account'] != key:
                    raise RuntimeError('Anderes Konto erkannt. Eigene Installation pro Demokonto verwenden.')
                if not saved.exists():
                    saved.write_text(json.dumps({'account': key}), encoding='utf-8')
                if bound_account and key != bound_account:
                    STATE['running'] = False
                    raise RuntimeError('Konto gewechselt. Anwendung neu starten.')
                bound_account = key
                if not mt.symbol_select(cfg['symbol'], True):
                    raise RuntimeError('Symbol fehlt. config.json: symbol auf GOLD oder Broker-Symbol ändern.')
                info = mt.symbol_info(cfg['symbol'])
                tick = mt.symbol_info_tick(cfg['symbol'])
                if not tick or time.time()-tick.time > 60:
                    raise RuntimeError('Keine aktuellen Kurse. Markt möglicherweise geschlossen.')
                sync_feedback(mt, key)
                feedback = feedback_by_frame([
                    {'closed_at': t, 'label': y, 'features': json.loads(f)}
                    for t, y, f in DB.execute('SELECT closed_at, label, features FROM feedback')])
                frames = cfg['timeframes']
                execution = cfg['execution_timeframe']
                if execution not in frames or len(set(frames)) != len(frames):
                    raise RuntimeError('Ausführungszeitebene muss eindeutig in timeframes enthalten sein.')
                snapshots, reports, series = {}, {}, {}
                for frame in frames:
                    constant = getattr(mt, 'TIMEFRAME_'+frame, None)
                    if constant is None:
                        raise RuntimeError('Unbekannte MT5-Zeitebene: '+frame)
                    rates = mt.copy_rates_from_pos(cfg['symbol'], constant, 1, 4000)
                    if rates is None or len(rates) < 800:
                        reports[frame] = {'available': False, 'reason': 'Mindestens 800 geschlossene Kerzen nötig'}
                        continue
                    fb = [dict({k: float(r[k]) for k in ('time', 'open', 'high', 'low', 'close')}, spread=float(r['spread'])*info.point) for r in rates]
                    report, vector = learner.evaluate(cfg['symbol'], frame, fb, feedback.get(frame, []))
                    reports[frame] = report
                    snapshots[frame] = vector
                    series[frame] = fb
                if execution not in series:
                    raise RuntimeError('Keine ausreichenden Daten für Ausführungszeitebene '+execution)
                bars = series[execution]
                x, atrs = features(bars)
                atr = float(atrs[-1])
                p, signal_reason = consensus(reports, execution, cfg['min_probability'], cfg['min_confirmations'])
                model = reports[execution]
                ai_settings = load_settings(ROOT)
                unit_value = mt.order_calc_profit(mt.ORDER_TYPE_BUY, cfg['symbol'], 1., tick.ask, tick.ask+1.)
                if unit_value is None or unit_value <= 0:
                    raise RuntimeError('Kostenumrechnung für Strategietests fehlgeschlagen')
                snapshot = dict(symbol=cfg['symbol'], frame=execution, bars=bars,
                    direction=1 if p > .5 else -1,
                    costs=dict(spread_fallback=tick.ask-tick.bid,
                               slippage=ai_settings['slippage_points']*info.point,
                               commission=ai_settings['commission_per_lot_round_trip']/unit_value),
                    cost_assumptions=dict(slippage_points=ai_settings['slippage_points'],
                        commission_per_lot_round_trip=ai_settings['commission_per_lot_round_trip'],
                        note='Kommission ist eine Nutzervorgabe, keine automatisch ermittelte Brokergebühr.'))
                with AI_LOCK:
                    AI_INPUT = snapshot
                    research_result = AI_STATE['result']
                ai_reason = research_entry_reason(ai_settings, research_result, snapshot)
                selected_strategy = (research_result['evaluation']['selected']
                    if ai_settings['require_research_for_entries'] and research_result else None)
                manage_research_exits(mt, cfg, key)
                preferences = SIZING.get()
                limits = dict(min=info.volume_min, max=info.volume_max, step=info.volume_step)
                direction = 1 if p > 0.5 else -1
                kind = mt.ORDER_TYPE_BUY if direction == 1 else mt.ORDER_TYPE_SELL
                price = tick.ask if direction == 1 else tick.bid
                distance = max(atr*(selected_strategy['stop_atr'] if selected_strategy else cfg['stop_atr']), (info.trade_stops_level+2)*info.point)
                stop = round(price-direction*distance, info.digits)
                take = round(price+direction*distance*(selected_strategy['reward_risk'] if selected_strategy else cfg['reward_risk']), info.digits)
                loss = mt.order_calc_profit(kind, cfg['symbol'], 1.0, price, stop)
                if loss is None:
                    raise RuntimeError('Risikoberechnung fehlgeschlagen.')
                sizing_reason = None
                try:
                    volume = selected_volume(preferences, account.equity*cfg['risk_percent']/100, abs(loss), limits)
                    if volume <= 0:
                        sizing_reason = 'Mindestlot überschreitet Risikobudget'
                except ValueError as exc:
                    volume = 0.
                    sizing_reason = str(exc)
                STATE.update(volume_limits=limits, sizing=preferences, sizing_preview=dict(
                    volume=volume, estimated_stop_loss=volume*abs(loss),
                    estimated_risk_percent=volume*abs(loss)/account.equity*100 if account.equity > 0 else None,
                    auto_risk_percent=cfg['risk_percent'], error=sizing_reason,
                    note='Schätzung für den aktuellen Stop, ohne Gebühren, Slippage und Kurslücken.'))
                day = datetime.now(timezone.utc).date().isoformat()
                DB.execute('INSERT OR IGNORE INTO daily VALUES (?, ?, ?)', (day, key, account.equity))
                baseline = DB.execute('SELECT equity FROM daily WHERE day=? AND account=?', (day, key)).fetchone()[0]
                DB.commit()
                positions = mt.positions_get(symbol=cfg['symbol'])
                if positions is None:
                    raise RuntimeError('Positionen konnten nicht gelesen werden.')
                reason = zone_reason(cfg, tick.ask, tick.ask-tick.bid, atr)
                if baseline <= 0 or account.equity <= baseline*(1-cfg['daily_loss_percent']/100):
                    reason = 'Tagesverlustgrenze erreicht'
                reason = reason or signal_reason or ai_reason or sizing_reason
                if positions:
                    reason = 'Position im Symbol bereits offen'
                STATE['running'] = intent['armed']
                if intent['halt_reason']:
                    reason = intent['halt_reason']
                STATE.update(connected=True, symbol=cfg['symbol'], balance=account.balance,
                             equity=account.equity, bid=tick.bid, ask=tick.ask,
                             probability=p, atr=atr, positions=len(positions),
                             timeframes=reports, execution_timeframe=execution,
                             status=reason or ('Bereit' if STATE['running'] else 'Pausiert'),
                             model={k: model[k] for k in ('score', 'samples', 'validation_samples', 'approved')},
                             candles=[{'time':b['time'], 'close':b['close']} for b in bars[-100:]],
                             trades=[{'ticket':t, 'closed_at':d, 'pnl':v} for t,d,v in DB.execute('SELECT ticket, closed_at, pnl FROM feedback ORDER BY closed_at DESC LIMIT 30')],
                             zones=cfg['price_zones'], blocked_hours=cfg['blocked_hours_utc'])
                bar_time = bars[-1]['time']
                if STATE['running'] and not reason and bar_time != last_bar:
                    # Consume the bar before sending: never retry an ambiguous order outcome.
                    last_bar = bar_time
                    if not AUTOPILOT.claim_bar(cfg['symbol'], execution, bar_time):
                        STATE['status'] = 'Orderversuch für diese Kerze bereits gespeichert'
                        continue
                    if not volume:
                        STATE['status'] = 'Mindestlot überschreitet Risikobudget'
                    else:
                        assert_demo(mt)
                        fill = mt.ORDER_FILLING_FOK if info.filling_mode & 1 else mt.ORDER_FILLING_IOC
                        request = dict(action=mt.TRADE_ACTION_DEAL, symbol=cfg['symbol'], volume=volume,
                                       type=kind, price=price, sl=stop, tp=take, deviation=20,
                                       magic=cfg['magic'], comment='Aurum demo research',
                                       type_time=mt.ORDER_TIME_GTC, type_filling=fill)
                        check = mt.order_check(request)
                        if check is None or check.retcode != 0:
                            raise RuntimeError('Orderprüfung abgelehnt: '+str(getattr(check, 'comment', mt.last_error())))
                        # Account, quotes and daily loss are checked again before a send.
                        fresh = assert_demo(mt)
                        if f'{fresh.server}:{fresh.login}' != key:
                            raise RuntimeError('Kontowechsel vor Order erkannt.')
                        if fresh.equity <= baseline*(1-cfg['daily_loss_percent']/100):
                            raise RuntimeError('Tagesverlustgrenze vor Order erreicht.')
                        try:
                            result = mt.order_send(request)
                        except Exception:
                            AUTOPILOT.halt('Unklarer Orderstatus: MT5 prüfen, dann Demohandel ausdrücklich neu starten.')
                            raise
                        if result is None or result.retcode not in (mt.TRADE_RETCODE_DONE, mt.TRADE_RETCODE_DONE_PARTIAL):
                            if result is None or result.retcode in (10008, 10012, 10031):
                                AUTOPILOT.halt('Unklarer Orderstatus: MT5 prüfen, dann Demohandel ausdrücklich neu starten.')
                            raise RuntimeError('Order nicht ausgeführt/bestätigt: '+str(getattr(result, 'comment', mt.last_error())))
                        fills = mt.history_deals_get(ticket=result.deal)
                        pid = fills[0].position_id if fills else result.order
                        DB.execute('INSERT OR IGNORE INTO entries VALUES (?, ?, ?, ?, ?)',
                                   (result.order, pid, time.time(), direction, json.dumps(snapshots)))
                        if selected_strategy:
                            DB.execute('INSERT OR REPLACE INTO execution_plans VALUES (?, ?, ?, ?)',
                                       (pid, bar_time, selected_strategy['max_hold_bars'], execution))
                        DB.commit()
                        STATE['status'] = 'Demo-Order ausgeführt'
        except Exception as exc:
            with LOCK:
                intent = AUTOPILOT.state()
                STATE.update(connected=False, running=False, trading_requested=intent['requested'],
                             halt_reason=intent['halt_reason'], status=str(exc))
        time.sleep(5)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, code, data, mime='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        return self.headers.get('Host') in ('127.0.0.1:8765', 'localhost:8765')

    def do_GET(self):
        if not self.valid_host():
            return self.send(403, b'{}')
        path = urlparse(self.path).path
        if path == '/api/sizing':
            with LOCK:
                return self.send(200, json.dumps(dict(preferences=SIZING.get(), broker=STATE.get('volume_limits'),
                    preview=STATE.get('sizing_preview')), ensure_ascii=False).encode('utf-8'))
        if path == '/api/research':
            with AI_LOCK:
                return self.send(200, json.dumps(AI_STATE, ensure_ascii=False).encode('utf-8'))
        if path == '/api/learning':
            with LOCK:
                return self.send(200, json.dumps(training_history(DB), ensure_ascii=False).encode('utf-8'))
        if path == '/api/status':
            with LOCK:
                return self.send(200, json.dumps(STATE, ensure_ascii=False).encode('utf-8'))
        if path == '/':
            html = (ROOT/'static/index.html').read_text(encoding='utf-8').replace('__TOKEN__', TOKEN)
            return self.send(200, html.encode('utf-8'), 'text/html; charset=utf-8')
        self.send(404, b'{}')

    def do_POST(self):
        if not self.valid_host() or not secrets.compare_digest(self.headers.get('X-Token', ''), TOKEN):
            return self.send(403, b'{}')
        if self.path == '/api/sizing':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('Ungültige Größe der Anfrage.')
                data = json.loads(self.rfile.read(length).decode('utf-8'))
                if not isinstance(data, dict):
                    raise ValueError('Ungültige Einstellungen.')
                with LOCK:
                    saved = SIZING.save(data.get('mode'), data.get('fixed_lot'), STATE.get('volume_limits'))
                    STATE['sizing'] = saved
                    STATE.pop('sizing_preview', None)
                return self.send(200, json.dumps(dict(preferences=saved), ensure_ascii=False).encode('utf-8'))
            except (ValueError, TypeError) as exc:
                return self.send(400, json.dumps(dict(error=str(exc)), ensure_ascii=False).encode('utf-8'))
        if self.path == '/api/research':
            AI_EVENT.set()
            return self.send(202, b'{"queued":true}')
        with LOCK:
            if self.path == '/api/start':
                AUTOPILOT.request(True)
                STATE.update(trading_requested=True, halt_reason=None, running=bool(STATE['connected']))
            elif self.path == '/api/stop':
                AUTOPILOT.request(False)
                STATE.update(trading_requested=False, halt_reason=None, running=False)
            else:
                return self.send(409, b'{"error":"MT5-Verbindung fehlt"}')
            self.send(200, json.dumps({'running': STATE['running']}).encode('utf-8'))


if __name__ == '__main__':
    # Bind before starting any workers: a second instance must never start trading.
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=research_worker, daemon=True).start()
    print('Aurum Demo: http://127.0.0.1:8765 — Strg+C beendet den Dienst.')
    server.serve_forever()
