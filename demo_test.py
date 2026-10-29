"""Explicit, single-shot demo order connection test. Never a strategy signal."""
import json
import math
import time
from sizing import check_broker_lots


class DemoOrderTest:
    def __init__(self, db):
        self.db=db
        db.execute('CREATE TABLE IF NOT EXISTS demo_order_tests (id INTEGER PRIMARY KEY, created_at REAL, payload TEXT)')
        db.commit()

    def latest(self):
        row=self.db.execute('SELECT id,payload FROM demo_order_tests ORDER BY id DESC LIMIT 1').fetchone()
        return dict(json.loads(row[1]),id=row[0]) if row else None

    def save(self, identifier, report):
        self.db.execute('UPDATE demo_order_tests SET payload=? WHERE id=?',
                        (json.dumps(report,ensure_ascii=False),identifier))
        self.db.commit()

    @staticmethod
    def account(mt, expected):
        account=mt.account_info()
        if account is None or account.trade_mode!=mt.ACCOUNT_TRADE_MODE_DEMO:
            raise ValueError('Kein Demokonto. Der Test sendet keine Echtgeldorders.')
        if f'{account.server}:{account.login}'!=expected:
            raise ValueError('Konto hat sich geändert. Test abgebrochen.')
        return account

    @staticmethod
    def empty_symbol(mt, symbol):
        positions,orders=mt.positions_get(symbol=symbol),mt.orders_get(symbol=symbol)
        if positions is None or orders is None:
            raise ValueError('Positionen oder offene Orders nicht lesbar.')
        if positions or orders:
            raise ValueError('Im Symbol bestehen Positionen oder Orders. Test eröffnet nichts zusätzlich.')

    def reset(self, mt, symbol, expected):
        self.account(mt,expected)
        self.empty_symbol(mt,symbol)
        previous=self.latest()
        if previous:
            previous.update(status='reset',message='Nach manueller MT5-Prüfung zurückgesetzt.')
            self.save(previous['id'],previous)
        return self.latest()

    def run(self, mt, cfg, expected):
        previous=self.latest()
        if previous and previous['status'] in ('running','attention'):
            raise ValueError('Vorheriger Test ist ungeklärt. MT5 prüfen und Teststatus zurücksetzen.')
        if previous and time.time()-previous['created_at']<60:
            raise ValueError('Bitte 60 Sekunden zwischen Testversuchen warten.')
        report=dict(created_at=time.time(),status='running',symbol=cfg['symbol'],steps=[],message='Test läuft')
        cursor=self.db.execute('INSERT INTO demo_order_tests(created_at,payload) VALUES (?,?)',
                              (report['created_at'],json.dumps(report)))
        identifier=cursor.lastrowid
        self.db.commit()
        uncertain=False
        def event(name,detail):
            report['steps'].append(dict(name=name,detail=detail))
            self.save(identifier,report)
        try:
            account=self.account(mt,expected)
            event('Demokonto','Demokonto geprüft.')
            symbol=cfg['symbol']
            if not mt.symbol_select(symbol,True):raise ValueError('Symbol fehlt: '+symbol)
            self.empty_symbol(mt,symbol)
            info,tick=mt.symbol_info(symbol),mt.symbol_info_tick(symbol)
            if info is None or tick is None or time.time()-tick.time>60 or not 0<tick.bid<=tick.ask:
                raise ValueError('Keine aktuellen, gültigen Kurse. Markt oder Verbindung prüfen.')
            volume=check_broker_lots(info.volume_min,dict(min=info.volume_min,max=info.volume_max,step=info.volume_step))
            distance=max(tick.ask*.001,(info.trade_stops_level+10)*info.point,3*(tick.ask-tick.bid))
            if (tick.ask-tick.bid)/distance>.2:raise ValueError('Spread für den Verbindungstest zu hoch.')
            stop,take=round(tick.ask-distance,info.digits),round(tick.ask+distance,info.digits)
            loss=mt.order_calc_profit(mt.ORDER_TYPE_BUY,symbol,volume,tick.ask,stop)
            if loss is None or not math.isfinite(loss) or abs(loss)>account.equity*cfg['risk_percent']/100:
                raise ValueError('Schon das Mindestlot überschreitet das Test-Risikobudget oder Risiko nicht berechenbar.')
            day=time.strftime('%Y-%m-%d',time.gmtime())
            self.db.execute('INSERT OR IGNORE INTO daily VALUES (?,?,?)',(day,expected,account.equity))
            baseline=self.db.execute('SELECT equity FROM daily WHERE day=? AND account=?',(day,expected)).fetchone()[0]
            if baseline<=0 or account.equity<=baseline*(1-cfg['daily_loss_percent']/100):
                raise ValueError('Tagesverlustgrenze erreicht. Kein Testtrade.')
            event('Volumen',f'Test mit Broker-Mindestlot {volume}; geschätztes Stop-Risiko {abs(loss):.2f} Kontowährung.')
            filling=mt.ORDER_FILLING_FOK if info.filling_mode&1 else mt.ORDER_FILLING_IOC
            order=dict(action=mt.TRADE_ACTION_DEAL,symbol=symbol,volume=volume,type=mt.ORDER_TYPE_BUY,
                       price=tick.ask,sl=stop,tp=take,deviation=20,magic=cfg['magic']+1,
                       comment='Aurum connection test',type_time=mt.ORDER_TIME_GTC,type_filling=filling)
            checked=mt.order_check(order)
            if checked is None or checked.retcode!=0:
                raise ValueError('MT5 Orderprüfung: '+str(getattr(checked,'retcode',None))+' '+str(getattr(checked,'comment',mt.last_error())))
            event('Orderprüfung','MT5 hat die Testorder-Prüfung akzeptiert.')
            self.account(mt,expected)
            event('Eröffnen','Ein einzelner Kaufversuch wird gesendet. Keine automatische Wiederholung.')
            uncertain=True
            opened=mt.order_send(order)
            if opened is None:raise ValueError('Keine Antwort auf Testorder. MT5 prüfen.')
            event('MT5-Antwort',f"Eröffnung: Code {opened.retcode}, {getattr(opened,'comment','')}, Order {opened.order}.")
            if opened.retcode not in (mt.TRADE_RETCODE_DONE,mt.TRADE_RETCODE_DONE_PARTIAL):
                uncertain=opened.retcode in (10008,10012,10031)
                raise ValueError('Testorder nicht bestätigt: '+str(opened.retcode)+' '+getattr(opened,'comment',''))
            report['order_ticket']=opened.order
            self.save(identifier,report)
            deals=mt.history_deals_get(ticket=opened.deal)
            pid=deals[0].position_id if deals else None
            position=None
            for attempt in range(5):
                positions=mt.positions_get(symbol=symbol)
                if positions is not None:
                    candidates=[p for p in positions if p.magic==cfg['magic']+1 and
                                ((pid is not None and p.identifier==pid) or p.ticket==opened.order)]
                    if len(candidates)==1:position=candidates[0];break
                if attempt<4:time.sleep(.2)
            if position is None:
                closed=mt.history_deals_get(position=pid) if pid else None
                if closed and any(d.entry in (mt.DEAL_ENTRY_OUT,mt.DEAL_ENTRY_OUT_BY) for d in closed):
                    uncertain=False
                    report.update(status='passed',message='Eröffnung bestätigt; bereits durch Broker/SL/TP geschlossen.')
                    event('Geschlossen',report['message'])
                    return dict(report,id=identifier)
                raise ValueError('Testposition nicht eindeutig zugeordnet. Keine weitere Order. In MT5 prüfen.')
            report['position_ticket']=position.ticket
            event('Position',f'Testposition {position.ticket} mit {position.volume} Lot gefunden.')
            self.account(mt,expected)
            quote=mt.symbol_info_tick(symbol)
            if quote is None or time.time()-quote.time>60:raise ValueError('Keine aktuellen Kurse zum Schließen. Position in MT5 prüfen.')
            close=dict(action=mt.TRADE_ACTION_DEAL,position=position.ticket,symbol=symbol,
                       volume=position.volume,type=mt.ORDER_TYPE_SELL,price=quote.bid,deviation=20,
                       magic=cfg['magic']+1,comment='Aurum test close',type_time=mt.ORDER_TIME_GTC,type_filling=filling)
            result=mt.order_send(close)
            if result is None or result.retcode!=mt.TRADE_RETCODE_DONE:
                raise ValueError('Schließen nicht vollständig bestätigt: '+str(getattr(result,'retcode',None))+' '+str(getattr(result,'comment',''))+'. Position in MT5 prüfen.')
            event('Schließauftrag',f'MT5 bestätigt Schließen, Code {result.retcode}.')
            for attempt in range(5):
                remaining=mt.positions_get(symbol=symbol)
                if remaining is not None and not any(p.ticket==position.ticket for p in remaining):
                    uncertain=False
                    report.update(status='passed',message='Eröffnen und Schließen auf dem Demokonto bestätigt.')
                    event('Ergebnis',report['message'])
                    return dict(report,id=identifier)
                if attempt<4:time.sleep(.2)
            raise ValueError('Schließauftrag bestätigt, aber Position noch nicht als geschlossen verifiziert. MT5 prüfen.')
        except Exception as exc:
            report.update(status='attention' if uncertain else 'failed',message=str(exc))
            event('Ergebnis',str(exc))
            return dict(report,id=identifier)
