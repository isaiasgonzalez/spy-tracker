"""Validación del CSV del usuario, sin dependencias externas."""
import csv
from datetime import datetime, timezone
import io
import math
import re
from typing import Any, TypedDict

INDEX_TICKER = 'SPY'
MIN_COMPONENTS = 400
MIN_TOTAL_WEIGHT = 95
MAX_TOTAL_WEIGHT = 105
TICKER_PATTERN = re.compile(r'[A-Z][A-Z-]{0,9}')
ALIASES = {
    'ticker': ('ticker', 'symbol', 'holding ticker'),
    'nombre': ('company', 'name', 'security name', 'nombre'),
    'peso_pct': ('weight', 'weight (%)', '% of net assets', 'portfolio weight', 'peso_pct'),
}


class WeightItem(TypedDict):
    ticker: str
    nombre: str
    peso_pct: float


def _find_columns(header: list[str]) -> dict[str, int | None]:
    normalized = [value.strip().lower() for value in header]
    return {
        key: next((normalized.index(alias) for alias in aliases if alias in normalized), None)
        for key, aliases in ALIASES.items()
    }


def read_weights(text: str) -> list[WeightItem]:
    rows = csv.reader(io.StringIO(text.lstrip('\ufeff')))
    columns = None
    for row in rows:
        found = _find_columns(row)
        if found['ticker'] is not None and found['peso_pct'] is not None:
            columns = found
            break
    if columns is None:
        raise ValueError('El CSV necesita columnas Symbol/Ticker y Weight.')
    result: list[WeightItem] = []
    seen: set[str] = set()
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
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError(f'Ticker inválido: {ticker}')
        if ticker in seen:
            raise ValueError(f'Ticker duplicado: {ticker}')
        seen.add(ticker)
        result.append({'ticker': ticker, 'nombre': name, 'peso_pct': weight})
    total = sum(r['peso_pct'] for r in result)
    if not MIN_TOTAL_WEIGHT <= total <= MAX_TOTAL_WEIGHT:
        raise ValueError(f'Los pesos deben sumar cerca de 100%; suman {total:.4f}%. Usá puntos porcentuales.')
    if len(result) < MIN_COMPONENTS:
        raise ValueError(f'Se esperaba la composición completa del SPY (al menos {MIN_COMPONENTS} acciones).')
    return sorted(result, key=lambda r: r['peso_pct'], reverse=True)


def weights_payload(items: list[WeightItem]) -> dict[str, Any]:
    return {
        'indice': INDEX_TICKER,
        'fuente': 'csv_usuario',
        'fecha_actualizacion': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'total_componentes': len(items),
        'componentes': items,
    }


def apply_weights(feed: dict[str, Any], items: list[WeightItem]) -> dict[str, Any]:
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
    updated.update(
        componentes=rows,
        total_componentes=len(rows),
        errores=missing,
        cobertura_peso_pct=round(sum(r['peso_pct'] for r in rows), 4),
    )
    return updated
