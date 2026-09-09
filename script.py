#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

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

# Ver la nota en el docstring del módulo: esta URL es la parte más frágil
# del pipeline porque depende del sitio del emisor del fondo.
URL_HOLDINGS_OFICIALES = (
    "https://www..com/us/financial-products/etfs/holdings/main/"
    "holdings/0?audienceType=Investor&action=download&ticker=SPY"
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("SPY_pipeline")


# --------------------------------------------------------------------------
# Utilidades de red
# --------------------------------------------------------------------------

def _descargar_texto(url: str, timeout: int = TIMEOUT_RED, intentos: int = MAX_REINTENTOS) -> str:
    """Descarga el contenido de una URL como texto, con reintentos básicos ante fallos de red."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    ultimo_error: Optional[Exception] = None
    for intento in range(1, intentos + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.RequestException as e:
            ultimo_error = e
            log.warning("Descarga de %s falló (intento %s/%s): %s", url, intento, intentos, e)
            if intento < intentos:
                time.sleep(ESPERA_ENTRE_REINTENTOS)
    raise ConnectionError(f"No se pudo descargar {url} tras {intentos} intentos") from ultimo_error


def _descargar_precios_batch(tickers: list[str]) -> pd.DataFrame:
    """Una sola llamada batch a yfinance para todos los tickers, con reintentos básicos."""
    ultimo_error: Optional[Exception] = None
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            datos = yf.download(
                tickers=tickers,
                period=PERIODO_DESCARGA_PRECIOS,
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
                timeout=TIMEOUT_RED,
            )
            if datos is None or datos.empty:
                raise ValueError("yfinance devolvió un DataFrame vacío.")
            return datos
        except Exception as e:  # noqa: BLE001 - cualquier falla de red/API dispara reintento
            ultimo_error = e
            log.warning(
                "Descarga batch de precios falló (intento %s/%s): %s", intento, MAX_REINTENTOS, e
            )
            if intento < MAX_REINTENTOS:
                time.sleep(ESPERA_ENTRE_REINTENTOS)
    raise ConnectionError("No se pudieron descargar los precios tras varios intentos") from ultimo_error


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
        "ticker": df[col_ticker].astype(str).str.strip().str.upper(),
        "nombre": df[col_nombre].astype(str).str.strip() if col_nombre else "",
        "peso_pct": _normalizar_a_porcentaje(pesos_limpios),
    })

    salida = salida.dropna(subset=["ticker", "peso_pct"])
    salida = salida[salida["ticker"].str.match(r"^[A-Z][A-Z.\-]{0,9}$")]
    salida["ticker"] = salida["ticker"].str.replace(".", "-", regex=False)

    return salida.sort_values("peso_pct", ascending=False).reset_index(drop=True)


def _pesos_desde_yfinance_top10(ticker_fondo: str = TICKER_INDICE) -> pd.DataFrame:
    """
    Fallback: trae el Top 10 de holdings del fondo vía yfinance.

    Yahoo Finance sólo expone el Top 10 de un ETF (no la lista completa),
    así que este camino nunca cubre el 100% de los componentes del SPY,
    pero permite que el pipeline funcione sin depender de una URL externa.
    """
    fondo = yf.Ticker(ticker_fondo)
    top10 = fondo.funds_data.top_holdings
    if top10 is None or top10.empty:
        raise ValueError("yfinance no devolvió holdings para el fondo.")

    df = top10.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_nombre = "name" if "name" in df.columns else None
    col_peso = next((c for c in df.columns if "percent" in c or "weight" in c), None)
    if col_peso is None:
        raise ValueError("No se encontró una columna de ponderación en el top_holdings de yfinance.")

    salida = pd.DataFrame({
        "ticker": [str(i).strip().upper() for i in df.index],
        "nombre": df[col_nombre].astype(str).str.strip() if col_nombre else "",
        "peso_pct": _normalizar_a_porcentaje(df[col_peso]),
    })
    salida["ticker"] = salida["ticker"].str.replace(".", "-", regex=False)
    salida = salida.dropna(subset=["ticker", "peso_pct"])
    return salida.sort_values("peso_pct", ascending=False).reset_index(drop=True)


def actualizar_pesos() -> bool:
    """
    Carga los componentes y ponderaciones desde el archivo local spy500.csv.
    """
    log.info("=== actualizar_pesos: iniciando ===")
    
    archivo_csv = DIRECTORIO_SCRIPT / "spy500.csv"
    if not archivo_csv.exists():
        log.error("No se encontró el archivo %s en la carpeta del script.", archivo_csv)
        return False

    try:
        contenido_csv = archivo_csv.read_text(encoding="utf-8")
        componentes = _parsear_csv_holdings(contenido_csv)
        fuente = "csv_local_100"
        log.info("Se obtuvieron %s componentes correctamente desde spy500.csv.", len(componentes))
    except Exception as e:
        log.error("Falló el procesamiento del CSV local: %s", e)
        return False

    payload = {
        "indice": TICKER_INDICE,
        "fuente": fuente,
        "fecha_actualizacion": datetime.now().isoformat(timespec="seconds"),
        "total_componentes": len(componentes),
        "componentes": componentes.to_dict(orient="records"),
    }

    try:
        ARCHIVO_PESOS_BASE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        log.error("No se pudo escribir el archivo base %s: %s", ARCHIVO_PESOS_BASE, e)
        return False

    log.info("Pesos guardados en %s (%s componentes).", ARCHIVO_PESOS_BASE, len(componentes))
    return True


# --------------------------------------------------------------------------
# actualizar_precios()
# --------------------------------------------------------------------------

def _cargar_componentes_base() -> pd.DataFrame:
    if not ARCHIVO_PESOS_BASE.exists():
        raise FileNotFoundError(f"No existe {ARCHIVO_PESOS_BASE}. Ejecutá actualizar_pesos() primero.")
    data = json.loads(ARCHIVO_PESOS_BASE.read_text(encoding="utf-8"))
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

    volumen_serie = _serie(historial, ticker, "Volume")
    volumen = None
    if volumen_serie is not None:
        volumen_serie = volumen_serie.dropna()
        if not volumen_serie.empty:
            volumen = int(volumen_serie.iloc[-1])
            if volumen <= 0:
                return None  # sin volumen operado: sesión inválida para este activo

    precio_actual = float(cierres.iloc[-1])
    precio_anterior = float(cierres.iloc[-2])
    if precio_anterior == 0:
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
    mucho más largo, y solo para el índice (no para los 102 componentes).
    Devuelve None ante cualquier fallo, en vez de interrumpir todo el
    pipeline: variación mensual/anual son "nice to have", no el dato
    principal.
    """
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


def _variacion_desde_dias_atras(cierres: pd.Series, fecha_referencia: date, dias_atras: int) -> Optional[float]:
    """
    Variación % entre el último cierre disponible y el cierre más cercano
    (hacia atrás) a `fecha_referencia - dias_atras` días de calendario.
    Se usa días de calendario (no ruedas de mercado) porque es como la
    gente piensa "hace un mes" / "hace un año", y como se calcula en
    Yahoo Finance.
    """
    if cierres is None or cierres.empty:
        return None
    fecha_objetivo = fecha_referencia - timedelta(days=dias_atras)
    fechas_previas = cierres.index[cierres.index.date <= fecha_objetivo]
    if fechas_previas.empty:
        return None  # no hay suficiente historial para ese horizonte todavía
    valor_referencia = cierres.loc[fechas_previas[-1]]
    if isinstance(valor_referencia, pd.Series):
        # Índice con fechas duplicadas: nos quedamos con el último valor
        valor_referencia = valor_referencia.iloc[-1]
    precio_referencia = float(valor_referencia)
    precio_actual = float(cierres.iloc[-1])
    if precio_referencia == 0:
        return None
    return round((precio_actual - precio_referencia) / precio_referencia * 100, 4)


def actualizar_precios() -> bool:
    """
    Toma los componentes guardados por actualizar_pesos(), descarga sus
    precios en UNA sola llamada batch a yfinance, valida que haya datos de
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
        base = _cargar_componentes_base()
    except (FileNotFoundError, ValueError) as e:
        log.error(str(e))
        return False

    tickers = base["ticker"].tolist()
    # Se agrega el propio índice como referencia adicional para validar la sesión de mercado
    tickers_a_pedir = list(dict.fromkeys(tickers + [TICKER_INDICE]))

    log.info("Descargando precios de %s tickers en una sola llamada batch...", len(tickers_a_pedir))
    try:
        historial = _descargar_precios_batch(tickers_a_pedir)
    except Exception as e:  # noqa: BLE001 - fallo de red/API ya reintentado en _descargar_precios_batch
        log.error("Fallo de red/API al descargar precios: %s", e)
        return False

    fecha_mercado = _fecha_sesion_mercado(historial, tickers_a_pedir)
    if fecha_mercado is None:
        log.error("No se pudo determinar una sesión de mercado válida en los datos descargados.")
        return False

    hoy = datetime.now().date()
    mercado_operado_hoy = fecha_mercado == hoy
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

    # Variación mensual/anual: histórico aparte, solo del índice. Si falla
    # (red, ticker sin suficiente historia, etc.) quedan en None y el
    # frontend ya sabe mostrar "—" en vez de romper.
    cierres_largos = _descargar_historico_largo(TICKER_INDICE)
    var_mensual_SPY = _variacion_desde_dias_atras(cierres_largos, fecha_mercado, DIAS_MES)
    var_anual_SPY = _variacion_desde_dias_atras(cierres_largos, fecha_mercado, DIAS_ANIO)

    payload = {
        "indice": TICKER_INDICE,
        "fecha_actualizacion": datetime.now().isoformat(timespec="seconds"),
        "fecha_datos_mercado": fecha_mercado.isoformat(),
        "mercado_operado_hoy": mercado_operado_hoy,
        "variacion_real_SPY": var_real_SPY,
        "variacion_mensual_SPY": var_mensual_SPY,
        "variacion_anual_SPY": var_anual_SPY,
        "total_componentes": len(filas),
        "componentes": filas,
        "errores": errores,
    }

    try:
        ARCHIVO_SALIDA.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        log.error("No se pudo escribir %s: %s", ARCHIVO_SALIDA, e)
        return False

    log.info(
        "Listo. %s componentes exportados a %s (%s con errores).",
        len(filas), ARCHIVO_SALIDA, len(errores),
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
            "pesos: componentes + ponderaciones oficiales | "
            "precios: precios batch + variación %% + impacto | "
            "todo: ambos pasos en secuencia"
        ),
    )
    args = parser.parse_args()

    if args.modo == "pesos":
        ok = actualizar_pesos()
    elif args.modo == "precios":
        ok = actualizar_precios()
    else:  # todo
        ok = actualizar_pesos()
        if ok:
            ok = actualizar_precios()
        else:
            log.error("Se omite actualizar_precios() porque actualizar_pesos() falló.")

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - red de seguridad final para errores no previstos
        log.exception("Error inesperado no manejado.")
        sys.exit(1)