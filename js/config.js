// ---------------------------------------------------------------------------
// Configuración central. Si querés agregar/quitar una columna, cambiar el
// orden, o apuntar a otro archivo de datos: TODO pasa por acá y nada más.
// ---------------------------------------------------------------------------

export const DATA_URL = 'qqq_data.json';

// Definición de columnas: la fuente única de verdad para encabezados, orden y
// tipo de dato. table.js recorre este array para dibujar el encabezado y las
// filas, así que agregar una columna nueva es agregar un objeto acá.
export const columns = [
  { key: 'ticker', label: 'Ticker', type: 'string', align: 'left' },
  { key: 'nombre', label: 'Nombre', type: 'string', align: 'left' },
  { key: 'peso', label: 'Peso (%)', type: 'number', align: 'right' },
  { key: 'variacion_diaria', label: 'Variación Diaria (%)', type: 'number', align: 'right' },
  { key: 'impacto_qqq', label: 'Impacto en el QQQ', type: 'number', align: 'right' },
];
