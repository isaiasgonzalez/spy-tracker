// ---------------------------------------------------------------------------
// Estado compartido. Un solo objeto mutable que importan los módulos que
// necesitan leer/escribir los datos actuales (tabla, estadísticas, captura).
// Evita tener que pasar rawData/rootData/sortState como parámetros por todos
// lados.
// ---------------------------------------------------------------------------

export const state = {
  rawData: [],
  rootData: null, // objeto raíz del JSON cuando trae variacion_real_SPY (ver normalize.js)
  sortState: { key: 'peso', dir: 'desc' },
  searchQuery: '', // texto tipeado en el buscador de ticker (ver ui/search.js)
};

function readFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function readRootNumber(candidateKeys) {
  if (!state.rootData) return null;
  for (const key of candidateKeys) {
    const value = readFiniteNumber(state.rootData[key]);
    if (value !== null) return value;
  }
  return null;
}

// Usa la variación real del índice si vino en el JSON (rootData.variacion_real_SPY);
// si no, cae de vuelta a la suma de impactos como estimación.
export function getSPYTotal() {
  const reported = readRootNumber(['variacion_real_SPY']);
  return reported ?? state.rawData.reduce((sum, item) => sum + (readFiniteNumber(item.impacto_SPY) ?? 0), 0);
}

// Variación del índice en horizontes más largos (mes, año). A diferencia del
// diario, acá no hay forma de estimarla sumando impactos de constituyentes,
// así que si el JSON no trae el campo, devuelve null (y la UI muestra "—").
// Acepta varios nombres de campo posibles en la raíz del JSON, mismo criterio
// que normalize.js usa para los constituyentes.
export function getMonthlyTotal() {
  return readRootNumber(['variacion_mensual_SPY', 'variacion_1m_SPY', 'variacion_mes_SPY']);
}

export function getYearlyTotal() {
  return readRootNumber(['variacion_anual_SPY', 'variacion_1y_SPY', 'variacion_anio_SPY']);
}
