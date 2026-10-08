// ---------------------------------------------------------------------------
// Adaptador de datos. Si el proveedor de datos cambia los nombres de campo,
// o el JSON viene envuelto en una clave distinta, se arregla ACÁ, sin tocar
// nada del resto de la app (tabla, estadísticas, captura, etc. siempre
// reciben el mismo shape: { ticker, nombre, peso, variacion_diaria, impacto_SPY }).
// ---------------------------------------------------------------------------

// Acepta tanto los nombres de campo del JSON de ejemplo (variacion_diaria,
// impacto_SPY) como los que use una fuente real distinta (variacion_pct,
// impacto_indice_pct, peso_pct), para no depender de una convención exacta.
function firstDefined(...values) {
  return values.find((value) => value !== undefined && value !== null);
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalizeItem(item) {
  return {
    ticker: String(item.ticker ?? '').trim().toUpperCase(),
    nombre: String(item.nombre ?? ''),
    peso: toNumber(firstDefined(item.peso, item.peso_pct)),
    variacion_diaria: toNumber(firstDefined(item.variacion_pct, item.variacion_diaria)),
    impacto_SPY: toNumber(firstDefined(item.impacto_indice_pct, item.impacto_SPY)),
  };
}

// Acepta un array plano, { componentes: [...] } (formato de script.py) o
// { constituyentes: [...] }.
export function normalizeFeed(json) {
  const root = Array.isArray(json) ? null : json;
  const source = Array.isArray(json)
    ? json
    : firstDefined(json?.componentes, json?.constituyentes);

  if (!Array.isArray(source)) {
    throw new TypeError('Se esperaba un array, o un objeto con "componentes" o "constituyentes".');
  }

  const items = source.map(normalizeItem).filter((item) => item.ticker);
  return { items, root };
}
