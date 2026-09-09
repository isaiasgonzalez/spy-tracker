import { columns } from '../config.js';
import { state } from '../state.js';
import { buildDelta } from './delta.js';
import { formatPercent } from '../format.js';

// ---------------------------------------------------------------------------
// Tabla principal: orden, encabezado clickeable y filas. Las columnas salen
// de config.js, así que este archivo no hardcodea "Ticker", "Peso", etc.
// ---------------------------------------------------------------------------

export function sortAndRenderTable(container) {
  const key = state.sortState.key;
  const dir = state.sortState.dir;
  const col = columns.find(function (c) { return c.key === key; });
  const query = state.searchQuery.trim().toLowerCase();
  const filtered = query
    ? state.rawData.filter(function (item) { return String(item.ticker).toLowerCase().includes(query); })
    : state.rawData.slice();
  const sorted = filtered.sort(function (a, b) {
    let av = a[key];
    let bv = b[key];
    if (col.type === 'number') {
      av = Number(av);
      bv = Number(bv);
      return dir === 'asc' ? av - bv : bv - av;
    }
    av = String(av).toLowerCase();
    bv = String(bv).toLowerCase();
    if (av < bv) return dir === 'asc' ? -1 : 1;
    if (av > bv) return dir === 'asc' ? 1 : -1;
    return 0;
  });
  renderTable(container, sorted);
}

function onHeaderActivate(container, key) {
  if (state.sortState.key === key) {
    state.sortState.dir = state.sortState.dir === 'asc' ? 'desc' : 'asc';
  } else {
    const col = columns.find(function (c) { return c.key === key; });
    state.sortState.key = key;
    state.sortState.dir = col.type === 'number' ? 'desc' : 'asc';
  }
  sortAndRenderTable(container);
}

function renderTable(container, data) {
  container.replaceChildren();

  const scrollWrap = document.createElement('div');
  scrollWrap.className = 'overflow-x-auto';

  const table = document.createElement('table');
  table.className = 'w-full text-sm border-collapse';
  table.setAttribute('aria-label', 'Composición del QQQ');

  table.appendChild(buildHead(container));

  const tbody = document.createElement('tbody');
  if (data.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = columns.length;
    td.className = 'px-4 py-14 text-center text-[var(--ink-700)] text-sm';
    td.textContent = 'No hay datos disponibles.';
    tr.appendChild(td);
    tbody.appendChild(tr);
  } else {
    data.forEach(function (item) { tbody.appendChild(buildRow(item)); });
  }
  table.appendChild(tbody);

  scrollWrap.appendChild(table);
  container.appendChild(scrollWrap);
}

function buildHead(container) {
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  headRow.className = 'border-b border-[var(--ink-150)]';

  columns.forEach(function (col) {
    const isActive = state.sortState.key === col.key;

    const th = document.createElement('th');
    th.scope = 'col';
    th.tabIndex = 0;
    th.setAttribute('aria-sort', isActive ? (state.sortState.dir === 'asc' ? 'ascending' : 'descending') : 'none');
    th.className = [
      'select-none cursor-pointer whitespace-nowrap px-4 py-3 font-data text-[11px] uppercase tracking-wider transition-colors',
      'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--ink-700)]',
      isActive ? 'text-[var(--ink-950)]' : 'text-[var(--ink-700)] hover:text-[var(--ink-950)]',
      col.align === 'right' ? 'text-right' : 'text-left',
    ].join(' ');

    const inner = document.createElement('span');
    inner.className = 'inline-flex items-center gap-1.5' + (col.align === 'right' ? ' flex-row-reverse' : '');

    const label = document.createElement('span');
    label.textContent = col.label;
    inner.appendChild(label);

    if (isActive) {
      const tri = document.createElement('span');
      tri.className = state.sortState.dir === 'asc' ? 'tri-up' : 'tri-down';
      inner.appendChild(tri);
    }

    th.appendChild(inner);
    th.addEventListener('click', function () { onHeaderActivate(container, col.key); });
    th.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onHeaderActivate(container, col.key);
      }
    });
    headRow.appendChild(th);
  });

  thead.appendChild(headRow);
  return thead;
}

// Link de cada ticker. Si en algún momento querés apuntar a otro sitio
// (Google Finance, Bloomberg, etc.) o armar la URL de otra forma, es acá y
// nada más se entera.
function buildTickerUrl(ticker) {
  return 'https://finance.yahoo.com/quote/' + encodeURIComponent(ticker) + '/';
}

function buildTickerLink(ticker) {
  const a = document.createElement('a');
  a.href = buildTickerUrl(ticker);
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  a.className = 'font-data font-medium text-[var(--ink-950)] hover:underline underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ink-700)]';
  a.textContent = ticker; // Requisito 4: siempre textContent, nunca innerHTML.
  // Evita que el click en el link también dispare el ordenamiento de la
  // columna si el link estuviera anidado dentro de algo clickeable.
  a.addEventListener('click', function (e) { e.stopPropagation(); });
  return a;
}

function buildRow(item) {
  const tr = document.createElement('tr');
  tr.className = 'border-b border-[var(--ink-150)] last:border-0 hover:bg-[var(--paper)] transition-colors';

  const tdTicker = document.createElement('td');
  tdTicker.className = 'px-4 py-3 whitespace-nowrap';
  tdTicker.appendChild(buildTickerLink(item.ticker));

  const tdNombre = document.createElement('td');
  tdNombre.className = 'px-4 py-3 text-[var(--ink-700)]';
  tdNombre.textContent = item.nombre;

  const tdPeso = document.createElement('td');
  tdPeso.className = 'px-4 py-3 text-right font-data text-[var(--ink-950)]';
  tdPeso.textContent = formatPercent(item.peso, false);

  const tdVar = document.createElement('td');
  tdVar.className = 'px-4 py-3 text-right font-data';
  tdVar.appendChild(buildDelta(item.variacion_diaria));

  const tdImpacto = document.createElement('td');
  tdImpacto.className = 'px-4 py-3 text-right font-data';
  tdImpacto.appendChild(buildDelta(item.impacto_qqq));

  tr.append(tdTicker, tdNombre, tdPeso, tdVar, tdImpacto);
  return tr;
}