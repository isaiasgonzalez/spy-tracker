import { DATA_URL } from './config.js';
import { normalizeFeed } from './normalize.js';
import { state, getSPYTotal, getMonthlyTotal, getYearlyTotal } from './state.js';
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

function getRequiredElement(id) {
  const element = document.getElementById(id);
  if (!element) throw new Error(`No se encontró el elemento #${id}.`);
  return element;
}

const elements = {
  container: getRequiredElement('state-container'),
  stats: getRequiredElement('stats-strip'),
  performance: getRequiredElement('index-performance'),
  footer: getRequiredElement('footer-legend'),
  captureButton: getRequiredElement('btn-captura'),
  captureLabel: getRequiredElement('btn-captura-label'),
  search: getRequiredElement('input-buscar-ticker'),
};

// Requisito 6: leyenda fija en el pie de página.
elements.footer.textContent = 'Datos de Yahoo Finance; pueden tener demora - Solo con fines informativos - x.com/isaias3g';

initCapture(elements.captureButton, elements.captureLabel);
initSearch(elements.search, () => sortAndRenderTable(elements.container));

loadDashboard();

async function fetchFeed() {
  const response = await fetch(DATA_URL, { cache: 'no-store' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function setControlsEnabled(enabled) {
  elements.captureButton.disabled = !enabled;
  elements.search.disabled = !enabled;
}

async function loadDashboard() {
  renderLoading(elements.container, elements.stats);
  elements.performance.classList.add('hidden');
  setControlsEnabled(false);

  try {
    const { items, root } = normalizeFeed(await fetchFeed());
    state.rawData = items;
    state.rootData = root;
    renderStats(elements.stats, items, root);
    renderIndexPerformance(elements.performance, {
      daily: getSPYTotal(),
      monthly: getMonthlyTotal(),
      yearly: getYearlyTotal(),
    });
    sortAndRenderTable(elements.container);
    setControlsEnabled(true);
  } catch (err) {
    const error = err instanceof Error ? err : new Error(String(err));
    renderError(elements.container, elements.stats, error);
    elements.performance.classList.add('hidden');
  }
}
