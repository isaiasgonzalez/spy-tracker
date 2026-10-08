import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import script


class PipelineTests(unittest.TestCase):
    def history(self):
        return pd.DataFrame(
            {('AAPL', 'Close'): [100., 110.], ('AAPL', 'Volume'): [100, 200],
             ('SPY', 'Close'): [200., 210.], ('SPY', 'Volume'): [100, 200]},
            index=pd.to_datetime(['2026-10-06', '2026-10-07']))

    def test_price_change_and_invalid_prices(self):
        history = self.history()
        result = script._procesar_componente('AAPL', history, date(2026, 10, 7))
        self.assertEqual(result['variacion_pct'], 10)
        self.assertIsNone(script._procesar_componente('MISSING', history, date(2026, 10, 7)))
        self.assertIsNone(script._procesar_componente('AAPL', history, date(2026, 10, 8)))
        history[('AAPL', 'Volume')] = 0
        self.assertIsNone(script._procesar_componente('AAPL', history, date(2026, 10, 7)))
        history[('AAPL', 'Volume')] = 200
        history[('AAPL', 'Close')] = [0, 110]
        self.assertIsNone(script._procesar_componente('AAPL', history, date(2026, 10, 7)))

    def test_session_consensus(self):
        self.assertEqual(script._fecha_sesion_mercado(self.history(), ['AAPL', 'SPY']), date(2026, 10, 7))
        self.assertIsNone(script._fecha_sesion_mercado(self.history(), ['MISSING']))

    def test_monthly_reference_and_missing_history(self):
        prices = pd.Series([100., 120.], index=pd.to_datetime(['2026-09-04', '2026-10-07']))
        self.assertEqual(script._variacion_desde_dias_atras(prices, date(2026, 10, 7), 30), 20)
        self.assertIsNone(script._variacion_desde_dias_atras(prices, date(2026, 10, 7), 365))
        self.assertIsNone(script._variacion_desde_dias_atras(None, date(2026, 10, 7), 30))

    def test_csv_percentages_and_ticker_normalization(self):
        parsed = script._parsear_csv_holdings('Ticker,Name,Weight\nBRK.B,Berkshire,7%\nAAPL,Apple,6%\n')
        self.assertEqual(parsed.ticker.tolist(), ['BRK-B', 'AAPL'])
        self.assertEqual(parsed.peso_pct.tolist(), [7, 6])
        with self.assertRaises(ValueError):
            script._parsear_csv_holdings('Name,Weight\nApple,7\n')

    def test_prices_export_impact_and_preserve_existing_output_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'base.json'
            output = Path(temp) / 'prices.json'
            base.write_text(json.dumps({'componentes': [
                {'ticker': 'AAPL', 'nombre': 'Apple', 'peso_pct': 7},
                {'ticker': 'MISSING', 'nombre': 'Missing', 'peso_pct': .1}]}))
            with patch.object(script, '_descargar_precios_batch', return_value=self.history()), \
                 patch.object(script, '_descargar_historico_largo', return_value=None):
                self.assertTrue(script.actualizar_precios(base, output))
            result = json.loads(output.read_text())
            self.assertEqual(result['componentes'][0]['impacto_indice_pct'], .7)
            self.assertEqual(result['variacion_real_SPY'], 5)
            self.assertEqual(result['fecha_datos_mercado'], '2026-10-07')
            self.assertEqual(result['total_componentes'], 1)
            self.assertEqual(len(result['errores']), 1)
            original = output.read_bytes()
            with patch.object(script, '_descargar_precios_batch', side_effect=ConnectionError('offline')):
                self.assertFalse(script.actualizar_precios(base, output))
            self.assertEqual(output.read_bytes(), original)

    def test_official_workbook_and_incomplete_response(self):
        workbook = io.BytesIO()
        rows = [['Fund Name:', 'SPY', None], ['Name', 'Ticker', 'Weight']]
        rows += [['Apple', 'AAPL', 7]] * 400
        pd.DataFrame(rows).to_excel(workbook, header=False, index=False)
        response = Mock(content=workbook.getvalue())
        with patch.object(script.requests, 'get', return_value=response) as get:
            self.assertEqual(len(script._pesos_oficiales()), 400)
            get.assert_called_once_with(script.URL_HOLDINGS_OFICIALES, timeout=script.TIMEOUT_RED)
            response.raise_for_status.assert_called_once()
        workbook = io.BytesIO()
        pd.DataFrame(rows[:3]).to_excel(workbook, header=False, index=False)
        with patch.object(script.requests, 'get', return_value=Mock(content=workbook.getvalue())):
            with self.assertRaises(ValueError):
                script._pesos_oficiales()

    def test_cli_output_directory_leaves_repository_data_unchanged(self):
        original = script.ARCHIVO_PESOS_BASE.read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / 'nested'
            subprocess.run([sys.executable, str(Path(script.__file__)), 'pesos',
                            '--output-dir', str(output_dir)], check=True, capture_output=True)
            payload = json.loads((output_dir / 'SPY_componentes_base.json').read_text())
            self.assertGreater(payload['total_componentes'], 400)
        self.assertEqual(script.ARCHIVO_PESOS_BASE.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
