import { state } from '../state.js';

// ---------------------------------------------------------------------------
// Búsqueda instantánea por ticker. Conecta el input del DOM con
// state.searchQuery; el filtro real vive en table.js (sortAndRenderTable),
// que ya lee ese campo. Acá solo escuchamos el evento "input" (se dispara
// con cada tecla, a diferencia de "change") y disparamos el re-render.
// ---------------------------------------------------------------------------

export function initSearch(inputEl, onChange) {
  inputEl.addEventListener('input', function () {
    state.searchQuery = inputEl.value;
    onChange();
  });
}