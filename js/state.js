// ---------------------------------------------------------------------------
// Estado compartido. Un solo objeto mutable que importan los módulos que
// necesitan leer/escribir los datos actuales (tabla, estadísticas, captura).
// Evita tener que pasar rawData/rootData/sortState como parámetros por todos
// lados.
// ---------------------------------------------------------------------------

export const state = {
  rawData: [],
  rootData: null, // objeto raíz del JSON cuando trae variacion_real_qqq (ver normalize.js)
  sortState: { key: 'peso', dir: 'desc' },
  searchQuery: '', // texto tipeado en el buscador de ticker (ver ui/search.js)
};

// Usa la variación real del índice si vino en el JSON (rootData.variacion_real_qqq);
// si no, cae de vuelta a la suma de impactos como estimación.
export function getQqqTotal() {
  if (state.rootData && state.rootData.variacion_real_qqq !== undefined && state.rootData.variacion_real_qqq !== null) {
    return Number(state.rootData.variacion_real_qqq);
  }
  return state.rawData.reduce(function (sum, d) { return sum + Number(d.impacto_qqq || 0); }, 0);
}

// Variación del índice en horizontes más largos (mes, año). A diferencia del
// diario, acá no hay forma de estimarla sumando impactos de constituyentes,
// así que si el JSON no trae el campo, devuelve null (y la UI muestra "—").
// Acepta varios nombres de campo posibles en la raíz del JSON, mismo criterio
// que normalize.js usa para los constituyentes.
export function getMonthlyTotal() {
  return readPeriodField(['variacion_mensual_qqq', 'variacion_1m_qqq', 'variacion_mes_qqq']);
}

export function getYearlyTotal() {
  return readPeriodField(['variacion_anual_qqq', 'variacion_1y_qqq', 'variacion_anio_qqq']);
}

function readPeriodField(candidateKeys) {
  if (!state.rootData) return null;
  for (const key of candidateKeys) {
    const v = state.rootData[key];
    if (v !== undefined && v !== null) return Number(v);
  }
  return null;
}