import { DATA_URL } from './config.js';
import { normalizeFeed } from './normalize.js';
import { state, getQqqTotal, getMonthlyTotal, getYearlyTotal } from './state.js';
import { renderLoading, renderError } from './ui/loading-error.js';
import { renderStats } from './ui/stats.js';
import { renderIndexPerformance } from './ui/index-performance.js';
import { sortAndRenderTable } from './ui/table.js';
import { initCapture } from './capture.js';
import { initSearch } from './ui/search.js';

// ---------------------------------------------------------------------------
// Orquestador. No tiene lógica propia de negocio: solo agarra los elementos
// del DOM, los pasa a cada módulo, y dispara la carga inicial de datos. Si
// agregás una feature nueva, se conecta acá con 1-2 líneas.
// ---------------------------------------------------------------------------

const container = document.getElementById('state-container');
const statsStrip = document.getElementById('stats-strip');
const indexPerformanceEl = document.getElementById('index-performance');
const footerLegend = document.getElementById('footer-legend');
const captureBtn = document.getElementById('btn-captura');
const captureBtnLabel = document.getElementById('btn-captura-label');
const searchInput = document.getElementById('input-buscar-ticker');

// Requisito 6: leyenda fija en el pie de página.
footerLegend.textContent = 'Datos diferidos 30 min - Solo con fines informativos - x.com/isaias3g';

initCapture(captureBtn, captureBtnLabel);
initSearch(searchInput, function () { sortAndRenderTable(container); });

init();

async function init() {
  renderLoading(container, statsStrip);
  indexPerformanceEl.classList.add('hidden');
  captureBtn.disabled = true;
  searchInput.disabled = true;
  try {
    const res = await fetch(DATA_URL, { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const json = await res.json();
    const normalized = normalizeFeed(json);
    state.rawData = normalized.items;
    state.rootData = normalized.root;
    renderStats(statsStrip, state.rawData);
    renderIndexPerformance(indexPerformanceEl, {
      daily: getQqqTotal(),
      monthly: getMonthlyTotal(),
      yearly: getYearlyTotal(),
    });
    sortAndRenderTable(container);
    captureBtn.disabled = false;
    searchInput.disabled = false;
  } catch (err) {
    renderError(container, statsStrip, err);
    indexPerformanceEl.classList.add('hidden');
  }
}