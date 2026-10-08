#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import logging
import math
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional

from weights import read_weights

import pandas as pd
import requests
import yfinance as yf

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------

TICKER_INDICE = "SPY"

DIRECTORIO_SCRIPT = Path(__file__).resolve().parent
ARCHIVO_PESOS_BASE = DIRECTORIO_SCRIPT / "SPY_componentes_base.json"
ARCHIVO_SALIDA = DIRECTORIO_SCRIPT / "SPY_data.json"

# Archivo oficial de composición diaria publicado por State Street.
URL_HOLDINGS_OFICIALES = (
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
    "holdings-daily-us-en-spy.xlsx"
)

TIMEOUT_RED = 15  # segundos
MAX_REINTENTOS = 3
ESPERA_ENTRE_REINTENTOS = 2  # segundos
PERIODO_DESCARGA_PRECIOS = "5d"  # margen para saltar fines de semana/feriados

# Historial largo, SOLO para el ticker del índice (SPY), usado para calcular
# variación mensual y anual reales. "2y" da margen de sobra para encontrar
# una sesión de referencia a ~30 y ~365 días de calendario hacia atrás,
# incluso salteando fines de semana/feriados.
PERIODO_DESCARGA_PRECIOS_LARGO = "2y"
DIAS_MES = 30
DIAS_ANIO = 365
SOLO_MERCADO_ABIERTO = False


class MercadoCerrado(Exception):
    pass


def _mercado_esta_abierto() -> bool:
    """Carga el calendario NYSE sólo cuando un modo de precios lo necesita."""
    from market_hours import market_is_open

    return market_is_open()


def _comprobar_mercado() -> None:
    if SOLO_MERCADO_ABIERTO and not _mercado_esta_abierto():
        raise MercadoCerrado("La rueda cerró; no se iniciarán nuevas consultas.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("SPY_pipeline")


# --------------------------------------------------------------------------
# Utilidades de red
# --------------------------------------------------------------------------

def _descargar_precios_batch(tickers: list[str]) -> pd.DataFrame:
    """Concurrencia acotada; reintenta solo los símbolos sin cierres válidos."""
    pendientes = list(dict.fromkeys(tickers))
    resultados = {}
    for intento in range(MAX_REINTENTOS):
        fallidos = []
        for inicio in range(0, len(pendientes), 40):
            _comprobar_mercado()
            lote = pendientes[inicio:inicio + 40]
            try:
                datos = yf.download(tickers=lote, period=PERIODO_DESCARGA_PRECIOS,
                                    interval="1d", group_by="ticker", auto_adjust=False,
                                    threads=8, progress=False, timeout=TIMEOUT_RED)
            except Exception as exc:
                log.warning("Falló un lote de precios: %s", exc)
                fallidos.extend(lote)
                continue
            for ticker in lote:
                try:
                    frame = datos[ticker] if isinstance(datos.columns, pd.MultiIndex) else datos
                    if "Close" not in frame or len(frame["Close"].dropna()) < 2:
                        raise ValueError("Sin cierres suficientes")
                    resultados[ticker] = frame
                except (KeyError, ValueError, TypeError, AttributeError):
                    fallidos.append(ticker)
        pendientes = fallidos
        if not pendientes:
            break
        if intento + 1 < MAX_REINTENTOS:
            _comprobar_mercado()
            time.sleep(ESPERA_ENTRE_REINTENTOS * (2 ** intento))
    if not resultados:
        raise ConnectionError("No se pudieron descargar precios válidos.")
    return pd.concat(resultados, axis=1)


# --------------------------------------------------------------------------
# actualizar_pesos()
# --------------------------------------------------------------------------

def _normalizar_a_porcentaje(serie: pd.Series) -> pd.Series:
    """
    Normaliza una serie de pesos a puntos porcentuales (0-100).

    Algunas fuentes expresan el peso como fracción (0.0523) y otras ya como
    porcentaje (5.23). Como ningún componente individual del SPY supera
    ~15% del índice, se usa ese umbral como heurística para decidir si
    hace falta multiplicar por 100.
    """
    serie = pd.to_numeric(serie, errors="coerce")
    no_nulos = serie.dropna()
    if not no_nulos.empty and no_nulos.max() <= 1.5:
        return serie * 100
    return serie


def _parsear_csv_holdings(contenido: str) -> pd.DataFrame:
    """
    Convierte el texto del CSV en un DataFrame procesado.
    Tolera comas vacías al inicio y formatos con porcentaje.
    """
    lineas = [l for l in contenido.splitlines() if l.strip()]

    idx_header = None
    for i, linea in enumerate(lineas):
        celdas = {c.strip().strip('"').lower() for c in linea.split(",")}
        if celdas & {"symbol", "ticker", "holding ticker"}:
            idx_header = i
            break

    if idx_header is None:
        raise ValueError("No se encontró una fila de encabezado con Symbol/Ticker.")

    df = pd.read_csv(io.StringIO("\n".join(lineas[idx_header:])))
    df.columns = [str(c).strip().lower() for c in df.columns]

    def _buscar_columna(alias: list[str]) -> Optional[str]:
        return next((a for a in alias if a in df.columns), None)

    col_ticker = _buscar_columna(["symbol", "ticker", "holding ticker"])
    col_nombre = _buscar_columna(["company", "name", "security name"])
    col_peso = _buscar_columna(["weight", "weight (%)", "% of net assets", "portfolio weight"])

    if not col_ticker or not col_peso:
        raise ValueError("El CSV no tiene columnas válidas de Ticker/Weight.")

    # Limpiar porcentaje (%) del texto si viene formateado como "12.38%"
    pesos_limpios = df[col_peso].astype(str).str.replace("%", "", regex=False).str.strip()

    salida = pd.DataFrame({
        "ticker": df[col_ticker],
        "nombre": df[col_nombre].fillna("").astype(str).str.strip() if col_nombre else "",
        "peso_pct": _normalizar_a_porcentaje(pesos_limpios),
    })

    salida = salida.dropna(subset=["ticker", "peso_pct"])
    salida["ticker"] = salida["ticker"].astype(str).str.strip().str.upper()
    salida = salida[salida["ticker"].str.match(r"^[A-Z][A-Z.\-]{0,9}$")]
    salida["ticker"] = salida["ticker"].str.replace(".", "-", regex=False)

    return salida.sort_values("peso_pct", ascending=False).reset_index(drop=True)


def _pesos_oficiales() -> pd.DataFrame:
    respuesta = requests.get(URL_HOLDINGS_OFICIALES, timeout=TIMEOUT_RED)
    respuesta.raise_for_status()
    tabla = pd.read_excel(io.BytesIO(respuesta.content), header=None)
    for i, fila in tabla.iterrows():
        columnas = {str(v).strip().lower() for v in fila}
        if {"ticker", "name", "weight"}.issubset(columnas):
            datos = tabla.iloc[i + 1:].copy()
            datos.columns = [str(v).strip() for v in fila]
            componentes = _parsear_csv_holdings(datos.to_csv(index=False))
            if len(componentes) < 400:
                raise ValueError("La composición oficial no contiene suficientes acciones del SPY.")
            return componentes
    raise ValueError("No se encontró el encabezado de la composición oficial.")


def actualizar_pesos(archivo_salida: Path = ARCHIVO_PESOS_BASE, fuente: str = "local") -> bool:
    """
    Carga componentes y ponderaciones desde el CSV local o State Street.
    """
    log.info("=== actualizar_pesos: iniciando ===")
    
    try:
        if fuente == "oficial":
            componentes = _pesos_oficiales()
            fuente_payload = "ssga_oficial"
        else:
            archivo_csv = DIRECTORIO_SCRIPT / "spy500.csv"
            componentes = pd.DataFrame(read_weights(archivo_csv.read_text(encoding="utf-8-sig")))
            fuente_payload = "csv_local_100"
        log.info("Se obtuvieron %s componentes desde la fuente %s.", len(componentes), fuente)
    except Exception as e:
        log.error("Falló la carga de pesos (%s): %s", fuente, e)
        return False

    payload = {
        "indice": TICKER_INDICE,
        "fuente": fuente_payload,
        "fecha_actualizacion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_componentes": len(componentes),
        "componentes": componentes.to_dict(orient="records"),
    }

    try:
        temporal = archivo_salida.with_suffix(".tmp")
        temporal.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(archivo_salida)
    except OSError as e:
        log.error("No se pudo escribir el archivo base %s: %s", archivo_salida, e)
        return False

    log.info("Pesos guardados en %s (%s componentes).", archivo_salida, len(componentes))
    return True


# --------------------------------------------------------------------------
# actualizar_precios()
# --------------------------------------------------------------------------

def _cargar_componentes_base(archivo_base: Path = ARCHIVO_PESOS_BASE) -> pd.DataFrame:
    if not archivo_base.exists():
        raise FileNotFoundError(f"No existe {archivo_base}. Ejecutá actualizar_pesos() primero.")
    data = json.loads(archivo_base.read_text(encoding="utf-8"))
    df = pd.DataFrame(data.get("componentes", []))
    if df.empty:
        raise ValueError("El archivo base no contiene componentes.")
    return df


def _serie(historial: pd.DataFrame, ticker: str, campo: str) -> Optional[pd.Series]:
    """Extrae una columna (Close/Volume) de un ticker del DataFrame batch de yfinance."""
    try:
        return historial[ticker][campo]
    except (KeyError, TypeError):
        return None


def _fecha_sesion_mercado(historial: pd.DataFrame, tickers: list[str]) -> Optional[date]:
    """
    Determina la última sesión de mercado válida por consenso: la fecha
    más frecuente entre los últimos cierres disponibles de todos los
    tickers descargados. Sirve como referencia para detectar componentes
    con datos obsoletos (halts, delistings, tickers mal escritos, etc.)
    y para saber si "el mercado operó" en la fecha esperada.
    """
    fechas = []
    for t in tickers:
        cierres = _serie(historial, t, "Close")
        if cierres is not None:
            cierres = cierres.dropna()
            if not cierres.empty:
                fechas.append(cierres.index[-1].date())
    if not fechas:
        return None
    return Counter(fechas).most_common(1)[0][0]


def _procesar_componente(ticker: str, historial: pd.DataFrame, fecha_mercado: date) -> Optional[dict]:
    """
    Calcula precio actual, precio anterior y variación % de un ticker,
    validando que su último dato corresponda a la sesión de mercado
    vigente (fecha_mercado) y que haya operado con volumen > 0. Devuelve
    None si el componente no pasa la validación (dato faltante, stale o
    sin operar).
    """
    cierres = _serie(historial, ticker, "Close")
    if cierres is None:
        return None
    cierres = cierres.dropna()
    if cierres.empty or cierres.index[-1].date() != fecha_mercado:
        return None  # dato obsoleto: no coincide con la sesión de referencia
    if len(cierres) < 2:
        return None  # no hay cierre anterior para calcular variación

    fecha_cierre = cierres.index[-1]
    volumen_serie = _serie(historial, ticker, "Volume")
    volumen = None
    if volumen_serie is not None:
        if fecha_cierre not in volumen_serie.index:
            return None
        valor_volumen = volumen_serie.loc[fecha_cierre]
        if isinstance(valor_volumen, pd.Series):
            valor_volumen = valor_volumen.iloc[-1]
        if pd.isna(valor_volumen):
            return None
        volumen = int(valor_volumen)
        if volumen <= 0:
            return None  # sin volumen operado: sesión inválida para este activo

    precio_actual = float(cierres.iloc[-1])
    precio_anterior = float(cierres.iloc[-2])
    if not math.isfinite(precio_actual) or not math.isfinite(precio_anterior) or precio_anterior <= 0 or precio_actual <= 0:
        return None

    variacion_pct = (precio_actual - precio_anterior) / precio_anterior * 100

    return {
        "precio_actual": round(precio_actual, 4),
        "precio_cierre_anterior": round(precio_anterior, 4),
        "variacion_pct": round(variacion_pct, 4),
        "volumen": volumen,
    }


def _descargar_historico_largo(ticker: str) -> Optional[pd.Series]:
    """
    Descarga histórico largo (PERIODO_DESCARGA_PRECIOS_LARGO) de un solo
    ticker, para calcular variaciones mensual/anual. Es una llamada aparte
    de la batch de precios diarios porque acá interesa un rango temporal
    mucho más largo, y solo para el índice (no para sus componentes).
    Devuelve None ante cualquier fallo, en vez de interrumpir todo el
    pipeline: variación mensual/anual son "nice to have", no el dato
    principal.
    """
    _comprobar_mercado()
    try:
        datos = yf.download(
            tickers=ticker,
            period=PERIODO_DESCARGA_PRECIOS_LARGO,
            interval="1d",
            auto_adjust=False,
            threads=True,
            progress=False,
            timeout=TIMEOUT_RED,
        )
        if datos is None or datos.empty or "Close" not in datos.columns:
            log.warning("Histórico largo de %s vino vacío o sin columna Close.", ticker)
            return None
        cierres = datos["Close"]
        # yfinance a veces devuelve columnas con MultiIndex (Close, TICKER)
        # incluso para un solo ticker, con lo cual esto sería un DataFrame
        # de una columna en vez de una Serie. Lo aplanamos a Serie.
        if isinstance(cierres, pd.DataFrame):
            cierres = cierres.iloc[:, 0]
        cierres = cierres.dropna()
        # yfinance a veces devuelve fechas duplicadas en el índice; nos
        # quedamos con la última ocurrencia para que cada fecha sea única
        # y evitar que .loc devuelva una Serie en vez de un escalar.
        if cierres.index.duplicated().any():
            log.warning("Histórico largo de %s tenía fechas duplicadas; se deduplicaron.", ticker)
            cierres = cierres[~cierres.index.duplicated(keep="last")]
        return cierres
    except Exception as e:  # noqa: BLE001 - no crítico, ver docstring
        log.warning("No se pudo descargar histórico largo de %s: %s", ticker, e)
        return None


def _referencias_periodos(fecha_mercado: date, archivo: Path) -> dict:
    if archivo.exists():
        try:
            cache = json.loads(archivo.read_text(encoding="utf-8"))
            if cache.get("fecha") == fecha_mercado.isoformat():
                return cache
        except (OSError, ValueError):
            pass
    cierres = _descargar_historico_largo(TICKER_INDICE)
    referencias = {"fecha": fecha_mercado.isoformat()}
    if cierres is None or cierres.empty:
        return referencias
    for key, days in (("mes", DIAS_MES), ("anio", DIAS_ANIO)):
        previos = cierres.loc[cierres.index.date <= fecha_mercado - timedelta(days=days)]
        if not previos.empty and math.isfinite(float(previos.iloc[-1])) and float(previos.iloc[-1]) > 0:
            referencias[key] = float(previos.iloc[-1])
    if "mes" in referencias and "anio" in referencias:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        temporal = archivo.with_suffix(".tmp")
        temporal.write_text(json.dumps(referencias), encoding="utf-8")
        temporal.replace(archivo)
    return referencias


def actualizar_precios(archivo_base: Path = ARCHIVO_PESOS_BASE, archivo_salida: Path = ARCHIVO_SALIDA) -> bool:
    """
    Toma los componentes guardados por actualizar_pesos(), descarga sus
    precios en lotes con concurrencia acotada y valida que haya datos de
    una sesión de mercado real (no stale/sin operar) y calcula:

      - variacion_pct: variación % del precio de cierre respecto al cierre
        anterior.
      - impacto_indice_pct: variacion_pct * (peso_pct / 100), es decir la
        contribución en puntos porcentuales de ese componente al retorno
        diario del índice.

    El resultado se exporta ordenado por peso (descendente) a
    ARCHIVO_SALIDA (SPY_data.json). Devuelve True/False según si se pudo
    generar la salida.
    """
    log.info("=== actualizar_precios: iniciando ===")

    try:
        base = _cargar_componentes_base(archivo_base)
    except (FileNotFoundError, ValueError) as e:
        log.error(str(e))
        return False

    tickers = base["ticker"].tolist()
    # Se agrega el propio índice como referencia adicional para validar la sesión de mercado
    tickers_a_pedir = list(dict.fromkeys(tickers + [TICKER_INDICE]))

    log.info("Descargando precios de %s tickers en lotes de hasta 40...", len(tickers_a_pedir))
    try:
        historial = _descargar_precios_batch(tickers_a_pedir)
    except MercadoCerrado:
        raise
    except Exception as e:  # noqa: BLE001 - fallo de red/API ya reintentado en _descargar_precios_batch
        log.error("Fallo de red/API al descargar precios: %s", e)
        return False

    fecha_mercado = _fecha_sesion_mercado(historial, tickers_a_pedir)
    if fecha_mercado is None:
        log.error("No se pudo determinar una sesión de mercado válida en los datos descargados.")
        return False

    hoy = datetime.now(ZoneInfo("America/New_York")).date()
    mercado_operado_hoy = fecha_mercado == hoy
    if SOLO_MERCADO_ABIERTO and not mercado_operado_hoy:
        log.error("No se publica: Yahoo aún no devolvió datos de la sesión actual.")
        return False
    if not mercado_operado_hoy:
        log.warning(
            "Los datos más recientes corresponden al %s, no a hoy (%s). Puede ser fin de "
            "semana/feriado o que la sesión de hoy aún no cerró; se continúa con la última "
            "sesión disponible.",
            fecha_mercado, hoy,
        )

    filas = []
    errores = []
    for _, comp in base.iterrows():
        ticker = str(comp["ticker"])
        datos = _procesar_componente(ticker, historial, fecha_mercado)
        if datos is None:
            errores.append({"ticker": ticker, "motivo": "sin datos válidos para la sesión de mercado vigente"})
            continue

        peso_pct = round(float(comp["peso_pct"]), 4)
        impacto_indice_pct = round(datos["variacion_pct"] * peso_pct / 100, 5)

        filas.append({
            "ticker": ticker,
            "nombre": comp.get("nombre", ""),
            "peso_pct": peso_pct,
            "precio_actual": datos["precio_actual"],
            "precio_cierre_anterior": datos["precio_cierre_anterior"],
            "variacion_pct": datos["variacion_pct"],
            "impacto_indice_pct": impacto_indice_pct,
            "volumen": datos["volumen"],
        })

    if not filas:
        log.error("No se pudo calcular ningún componente. Se aborta la exportación.")
        return False

    filas.sort(key=lambda r: r["peso_pct"], reverse=True)

    datos_indice = _procesar_componente(TICKER_INDICE, historial, fecha_mercado)
    var_real_SPY = datos_indice["variacion_pct"] if datos_indice else None

    peso_total = sum(float(c["peso_pct"]) for _, c in base.iterrows())
    peso_valido = sum(r["peso_pct"] for r in filas)
    if datos_indice is None or peso_total <= 0 or peso_valido / peso_total < 0.95:
        log.error("No se publica: falta SPY o la cobertura por peso es inferior al 95%.")
        return False

    # Las referencias históricas cambian una vez por sesión; el precio actual
    # siempre viene del mismo batch usado para la variación diaria.
    referencias = _referencias_periodos(fecha_mercado, archivo_salida.parent / ".price-cache" / "SPY_referencias.json")
    precio_indice = datos_indice["precio_actual"] if datos_indice else None
    def variacion(ref):
        valor = referencias.get(ref)
        return round((precio_indice - valor) / valor * 100, 4) if precio_indice and valor else None
    var_mensual_SPY = variacion("mes")
    var_anual_SPY = variacion("anio")

    payload = {
        "indice": TICKER_INDICE,
        "fecha_actualizacion": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fecha_datos_mercado": fecha_mercado.isoformat(),
        "mercado_operado_hoy": mercado_operado_hoy,
        "variacion_real_SPY": var_real_SPY,
        "variacion_mensual_SPY": var_mensual_SPY,
        "variacion_anual_SPY": var_anual_SPY,
        "cobertura_peso_pct": round(peso_valido, 4),
        "total_componentes": len(filas),
        "componentes": filas,
        "errores": errores,
    }

    if archivo_salida.exists():
        anterior = json.loads(archivo_salida.read_text(encoding="utf-8"))
        relevantes = {k: v for k, v in payload.items() if k != "fecha_actualizacion"}
        previos = {k: v for k, v in anterior.items() if k != "fecha_actualizacion"}
        if relevantes == previos:
            log.info("Sin cambios de mercado; no se reescribe el JSON.")
            return True

    try:
        temporal = archivo_salida.with_suffix(".tmp")
        temporal.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(archivo_salida)
    except OSError as e:
        log.error("No se pudo escribir %s: %s", archivo_salida, e)
        return False

    log.info(
        "Listo. %s componentes exportados a %s (%s con errores).",
        len(filas), archivo_salida, len(errores),
    )
    return True


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de datos del SPY (componentes, pesos y precios).")
    parser.add_argument(
        "modo",
        choices=["pesos", "precios", "todo"],
        help=(
            "pesos: componentes + ponderaciones locales u oficiales | "
            "precios: precios batch + variación %% + impacto | "
            "todo: ambos pasos en secuencia"
        ),
    )
    parser.add_argument("--solo-mercado-abierto", action="store_true", help="No consultar precios fuera de la rueda NYSE.")
    parser.add_argument("--output-dir", type=Path, default=DIRECTORIO_SCRIPT,
                        help="Directorio para los JSON generados (por defecto: junto al script).")
    parser.add_argument("--fuente-pesos", choices=["local", "oficial"], default="local",
                        help="CSV local o composición diaria de State Street para pesos/todo.")
    args = parser.parse_args()
    global SOLO_MERCADO_ABIERTO
    SOLO_MERCADO_ABIERTO = args.solo_mercado_abierto
    if SOLO_MERCADO_ABIERTO and args.modo != "pesos" and not _mercado_esta_abierto():
        log.info("NYSE cerrado: no se consultan precios.")
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archivo_base = args.output_dir / ARCHIVO_PESOS_BASE.name
    archivo_salida = args.output_dir / ARCHIVO_SALIDA.name
    # precios puede usar la base incluida si aún no se generó una en la salida.
    base_entrada = archivo_base if archivo_base.exists() else ARCHIVO_PESOS_BASE

    if args.modo == "pesos":
        ok = actualizar_pesos(archivo_base, args.fuente_pesos)
    elif args.modo == "precios":
        ok = actualizar_precios(base_entrada, archivo_salida)
    else:  # todo
        ok = actualizar_pesos(archivo_base, args.fuente_pesos)
        if ok:
            ok = actualizar_precios(archivo_base, archivo_salida)
        else:
            log.error("Se omite actualizar_precios() porque actualizar_pesos() falló.")

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except MercadoCerrado as exc:
        log.info(str(exc))
        sys.exit(0)
    except Exception:  # noqa: BLE001 - red de seguridad final para errores no previstos
        log.exception("Error inesperado no manejado.")
        sys.exit(1)
