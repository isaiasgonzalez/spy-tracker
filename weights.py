"""Validación del CSV del usuario, sin dependencias externas."""
import csv
import io
import math
import re
from datetime import datetime, timezone


def read_weights(text):
    rows = csv.reader(io.StringIO(text.lstrip('\ufeff')))
    aliases = {'ticker': ('ticker', 'symbol', 'holding ticker'),
               'nombre': ('company', 'name', 'security name', 'nombre'),
               'peso_pct': ('weight', 'weight (%)', '% of net assets', 'portfolio weight', 'peso_pct')}
    columns = None
    for row in rows:
        header = [v.strip().lower() for v in row]
        found = {key: next((header.index(a) for a in names if a in header), None)
                 for key, names in aliases.items()}
        if found['ticker'] is not None and found['peso_pct'] is not None:
            columns = found
            break
    if columns is None:
        raise ValueError('El CSV necesita columnas Symbol/Ticker y Weight.')
    result, seen = [], set()
    for number, row in enumerate(rows, 1):
        if not row or not any(v.strip() for v in row):
            continue
        try:
            ticker = row[columns['ticker']].strip().upper().replace('.', '-')
            weight = float(row[columns['peso_pct']].strip().rstrip('%'))
            name = row[columns['nombre']].strip() if columns['nombre'] is not None else ticker
        except (ValueError, IndexError) as exc:
            raise ValueError(f'Fila de datos {number}: peso o columnas inválidos.') from exc
        if not math.isfinite(weight) or not 0 <= weight <= 100:
            raise ValueError(f'Peso inválido para {ticker}')
        # El dashboard representa acciones; omite futuros y posiciones de peso cero.
        if ticker.endswith('=F') or weight == 0:
            continue
        if not re.fullmatch(r'[A-Z][A-Z\-]{0,9}', ticker):
            raise ValueError(f'Ticker inválido: {ticker}')
        if ticker in seen:
            raise ValueError(f'Ticker duplicado: {ticker}')
        seen.add(ticker)
        result.append({'ticker': ticker, 'nombre': name, 'peso_pct': weight})
    total = sum(r['peso_pct'] for r in result)
    if not 95 <= total <= 105:
        raise ValueError(f'Los pesos deben sumar cerca de 100%; suman {total:.4f}%. Usá puntos porcentuales.')
    if len(result) < 400:
        raise ValueError('Se esperaba la composición completa del SPY (al menos 400 acciones).')
    return sorted(result, key=lambda r: r['peso_pct'], reverse=True)


def weights_payload(items):
    return {'indice': 'SPY', 'fuente': 'csv_usuario',
            'fecha_actualizacion': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'total_componentes': len(items), 'componentes': items}


def apply_weights(feed, items):
    updated = dict(feed)
    old = {r['ticker']: r for r in feed['componentes']}
    rows, missing = [], []
    for item in items:
        if item['ticker'] not in old:
            missing.append({'ticker': item['ticker'], 'motivo': 'pendiente de precios con los nuevos pesos'})
            continue
        row = dict(old[item['ticker']])
        row.update(item)
        row['impacto_indice_pct'] = round(float(row['variacion_pct']) * item['peso_pct'] / 100, 5)
        rows.append(row)
    updated.update(componentes=rows, total_componentes=len(rows), errores=missing,
                   cobertura_peso_pct=round(sum(r['peso_pct'] for r in rows), 4))
    return updated
