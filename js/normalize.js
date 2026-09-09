// ---------------------------------------------------------------------------
// Adaptador de datos. Si el proveedor de datos cambia los nombres de campo,
// o el JSON viene envuelto en una clave distinta, se arregla ACÁ, sin tocar
// nada del resto de la app (tabla, estadísticas, captura, etc. siempre
// reciben el mismo shape: { ticker, nombre, peso, variacion_diaria, impacto_qqq }).
// ---------------------------------------------------------------------------

// Acepta tanto los nombres de campo del JSON de ejemplo (variacion_diaria,
// impacto_qqq) como los que use una fuente real distinta (variacion_pct,
// impacto_indice_pct, peso_pct), para no depender de una convención exacta.
function normalizeItem(item) {
  return {
    ticker: item.ticker,
    nombre: item.nombre,
    peso: item.peso !== undefined ? item.peso : item.peso_pct,
    variacion_diaria: item.variacion_pct !== undefined ? item.variacion_pct : item.variacion_diaria,
    impacto_qqq: item.impacto_indice_pct !== undefined ? item.impacto_indice_pct : item.impacto_qqq,
  };
}

// Acepta un array plano, { componentes: [...] } (formato de script.py) o
// { constituyentes: [...] }.
export function normalizeFeed(json) {
  if (Array.isArray(json)) {
    return { items: json.map(normalizeItem), root: null };
  }
  if (json && Array.isArray(json.componentes)) {
    return { items: json.componentes.map(normalizeItem), root: json };
  }
  if (json && Array.isArray(json.constituyentes)) {
    return { items: json.constituyentes.map(normalizeItem), root: json };
  }
  throw new Error('Se esperaba un array, o un objeto con "componentes" o "constituyentes".');
}
