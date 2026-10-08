import base64
from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from market_hours import market_is_open
import script
import update_weights
from weights import apply_weights, read_weights


class MarketTests(unittest.TestCase):
    def test_opening_and_closing_dst(self):
        for instant, expected in [('2026-07-06T13:29:59+00:00', False),
                                  ('2026-07-06T13:30:00+00:00', True),
                                  ('2026-07-06T20:00:00+00:00', False),
                                  ('2026-11-02T14:30:00+00:00', True),
                                  ('2026-11-02T21:00:00+00:00', False)]:
            with self.subTest(instant=instant):
                self.assertEqual(market_is_open(datetime.fromisoformat(instant)), expected)

    def test_holiday_weekend_and_early_close(self):
        for instant, expected in [('2026-07-03T15:00:00+00:00', False),
                                  ('2026-07-04T15:00:00+00:00', False),
                                  ('2026-11-27T17:59:59+00:00', True),
                                  ('2026-11-27T18:00:00+00:00', False)]:
            self.assertEqual(market_is_open(datetime.fromisoformat(instant)), expected)

    def test_no_price_requests_after_close(self):
        with patch.object(script, 'SOLO_MERCADO_ABIERTO', True), \
             patch.object(script, 'market_is_open', return_value=False), \
             patch.object(script.yf, 'download') as download:
            with self.assertRaises(script.MercadoCerrado):
                script._descargar_precios_batch(['SPY'])
            download.assert_not_called()

    def test_stale_session_is_not_published_during_market_hours(self):
        history = pd.DataFrame({('SPY', 'Close'): [200., 210.],
                                ('SPY', 'Volume'): [100, 200]},
                               index=pd.to_datetime(['2026-10-06', '2026-10-07']))
        with tempfile.TemporaryDirectory() as temp:
            base, output = Path(temp) / 'base.json', Path(temp) / 'feed.json'
            base.write_text(json.dumps({'componentes': [{'ticker': 'SPY', 'peso_pct': 100}]}))
            with patch.object(script, 'SOLO_MERCADO_ABIERTO', True), \
                 patch.object(script, '_descargar_precios_batch', return_value=history), \
                 patch.object(script, 'datetime') as clock:
                clock.now.return_value.date.return_value = date(2026, 10, 8)
                self.assertFalse(script.actualizar_precios(base, output))
            self.assertFalse(output.exists())

    def test_only_failed_tickers_are_retried(self):
        index = pd.to_datetime(['2026-10-06', '2026-10-07'])
        first = pd.DataFrame({('AAPL', 'Close'): [100., 110.],
                              ('SPY', 'Close'): [None, None]}, index=index)
        second = pd.DataFrame({('SPY', 'Close'): [200., 210.]}, index=index)
        with patch.object(script.yf, 'download', side_effect=[first, second]) as download, \
             patch.object(script.time, 'sleep'):
            result = script._descargar_precios_batch(['AAPL', 'SPY'])
        self.assertEqual(download.call_args_list[1].kwargs['tickers'], ['SPY'])
        self.assertEqual(download.call_args_list[0].kwargs['threads'], 8)
        self.assertEqual(result[('AAPL', 'Close')].iloc[-1], 110.)

    def test_history_references_are_cached_by_session(self):
        history = pd.Series([100., 200.], index=pd.to_datetime(['2025-10-06', '2026-09-04']))
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(script, '_descargar_historico_largo', return_value=history) as download:
            cache = Path(temp) / 'refs.json'
            first = script._referencias_periodos(date(2026, 10, 7), cache)
            self.assertEqual(first['mes'], 200.)
            self.assertEqual(first['anio'], 100.)
            self.assertEqual(script._referencias_periodos(date(2026, 10, 7), cache), first)
            self.assertEqual(download.call_count, 1)
            script._referencias_periodos(date(2026, 10, 8), cache)
            self.assertEqual(download.call_count, 2)

    def test_inadequate_coverage_does_not_replace_feed(self):
        history = pd.DataFrame({('SPY', 'Close'): [200., 210.],
                                ('SPY', 'Volume'): [100, 200],
                                ('AAPL', 'Close'): [100., 110.],
                                ('AAPL', 'Volume'): [100, 200]},
                               index=pd.to_datetime(['2026-10-06', '2026-10-07']))
        with tempfile.TemporaryDirectory() as temp:
            base, output = Path(temp) / 'base.json', Path(temp) / 'feed.json'
            base.write_text(json.dumps({'componentes': [{'ticker': 'AAPL', 'peso_pct': 1},
                                                        {'ticker': 'MISSING', 'peso_pct': 99}]}))
            output.write_text('original')
            with patch.object(script, '_descargar_precios_batch', return_value=history), \
                 patch.object(script, '_descargar_historico_largo') as download:
                self.assertFalse(script.actualizar_precios(base, output))
            self.assertEqual(output.read_text(), 'original')
            download.assert_not_called()

    def test_same_prices_keep_timestamp_and_use_consistent_period_price(self):
        history = pd.DataFrame({('SPY', 'Close'): [200., 210.],
                                ('SPY', 'Volume'): [100, 200],
                                ('AAPL', 'Close'): [100., 110.],
                                ('AAPL', 'Volume'): [100, 200]},
                               index=pd.to_datetime(['2026-10-06', '2026-10-07']))
        with tempfile.TemporaryDirectory() as temp:
            base, output = Path(temp) / 'base.json', Path(temp) / 'feed.json'
            base.write_text(json.dumps({'componentes': [{'ticker': 'AAPL', 'peso_pct': 100}]}))
            with patch.object(script, '_descargar_precios_batch', return_value=history), \
                 patch.object(script, '_referencias_periodos', return_value={'mes': 100, 'anio': 50}):
                self.assertTrue(script.actualizar_precios(base, output))
                data = json.loads(output.read_text())
                self.assertEqual(data['variacion_mensual_SPY'], 110.)
                self.assertEqual(data['variacion_anual_SPY'], 320.)
                data['fecha_actualizacion'] = 'timestamp-original'
                output.write_text(json.dumps(data))
                original = output.read_bytes()
                self.assertTrue(script.actualizar_precios(base, output))
                self.assertEqual(output.read_bytes(), original)


class WeightsTests(unittest.TestCase):
    def test_existing_user_csv(self):
        items = read_weights(Path(script.DIRECTORIO_SCRIPT / 'spy500.csv').read_text())
        self.assertGreater(len(items), 400)
        self.assertTrue(all(i['peso_pct'] > 0 and not i['ticker'].endswith('=F') for i in items))

    def test_invalid_csv_rejected(self):
        for text in ['Ticker,Weight\nAAPL,NaN\n', 'Ticker,Weight\nAAPL,-1\n',
                     'Ticker,Weight\nAAPL,5\nAAPL,5\n', 'Ticker,Weight\nAAPL,5\n']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_weights(text)

    def test_reweight_does_not_change_price_or_market_date(self):
        feed = {'fecha_datos_mercado': '2026-10-07', 'componentes': [
            {'ticker': 'AAPL', 'precio_actual': 110, 'variacion_pct': 10, 'peso_pct': 7}]}
        result = apply_weights(feed, [{'ticker': 'AAPL', 'nombre': 'Apple', 'peso_pct': 8},
                                      {'ticker': 'NEW', 'nombre': 'New', 'peso_pct': 1}])
        self.assertEqual(result['componentes'][0]['impacto_indice_pct'], .8)
        self.assertEqual(result['componentes'][0]['precio_actual'], 110)
        self.assertEqual(result['fecha_datos_mercado'], feed['fecha_datos_mercado'])
        self.assertEqual(result['errores'][0]['ticker'], 'NEW')
        self.assertEqual(feed['componentes'][0]['peso_pct'], 7)

    def test_publish_is_single_commit_without_forced_update(self):
        feed = {'componentes': [{'ticker': 'AAPL', 'variacion_pct': 10}]}
        def content(data):
            return {'content': base64.b64encode(json.dumps(data).encode()).decode()}
        responses = [{'object': {'sha': 'old'}}, {'tree': {'sha': 'base-tree'}},
                     content(feed), content({'componentes': []}),
                     {'sha': 'blob1'}, {'sha': 'blob2'}, {'sha': 'blob3'},
                     {'sha': 'tree'}, {'sha': 'new'}, {}]
        with patch.object(update_weights, 'api', side_effect=responses) as api:
            url = update_weights.publish('csv', [{'ticker': 'AAPL', 'peso_pct': 7}], 'test', 'owner/repo')
        self.assertTrue(url.endswith('/new'))
        self.assertEqual(api.call_args.args[-1], {'sha': 'new', 'force': False})
        self.assertEqual(api.call_args_list[8].args[-1]['parents'], ['old'])

    def test_unchanged_weights_do_not_create_commit(self):
        items = [{'ticker': 'AAPL', 'peso_pct': 7}]
        def content(data):
            return {'content': base64.b64encode(json.dumps(data).encode()).decode()}
        with patch.object(update_weights, 'api', side_effect=[
            {'object': {'sha': 'old'}}, {'tree': {'sha': 'base-tree'}},
            content({'componentes': []}), content({'componentes': items})]) as api:
            self.assertIsNone(update_weights.publish('csv', items, 'test', 'owner/repo'))
        self.assertEqual(api.call_count, 4)
