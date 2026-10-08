import { columns } from '../config.js';
import { state } from '../state.js';
import { buildDelta } from './delta.js';
import { formatPercent } from '../format.js';

// ---------------------------------------------------------------------------
// Tabla principal: orden, encabezado clickeable y filas. Las columnas salen
// de config.js, así que este archivo no hardcodea "Ticker", "Peso", etc.
// ---------------------------------------------------------------------------

export function sortAndRenderTable(container) {
  const { key, dir } = state.sortState;
  const column = columns.find((item) => item.key === key);
  const query = state.searchQuery.trim().toLowerCase();
  const filtered = query
    ? state.rawData.filter((item) => item.ticker.toLowerCase().includes(query))
    : state.rawData.slice();
  const direction = dir === 'asc' ? 1 : -1;
  const sorted = filtered.sort((a, b) => {
    if (column.type === 'number') {
      const left = a[key] === null ? Number.NaN : Number(a[key]);
      const right = b[key] === null ? Number.NaN : Number(b[key]);
      if (!Number.isFinite(left) && !Number.isFinite(right)) return 0;
      if (!Number.isFinite(left)) return 1;
      if (!Number.isFinite(right)) return -1;
      return (left - right) * direction;
    }
    return String(a[key]).localeCompare(String(b[key]), 'es', { sensitivity: 'base' }) * direction;
  });
  renderTable(container, sorted);
}

function onHeaderActivate(container, key) {
  if (state.sortState.key === key) {
    state.sortState.dir = state.sortState.dir === 'asc' ? 'desc' : 'asc';
  } else {
    const col = columns.find((item) => item.key === key);
    state.sortState.key = key;
    state.sortState.dir = col.type === 'number' ? 'desc' : 'asc';
  }
  sortAndRenderTable(container);
}

function renderTable(container, data) {
  container.replaceChildren();
  container.setAttribute('aria-busy', 'false');

  const scrollWrap = document.createElement('div');
  scrollWrap.className = 'overflow-x-auto';

  const table = document.createElement('table');
  table.className = 'w-full text-sm border-collapse';
  table.setAttribute('aria-label', 'Composición del SPY');

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
    const rows = document.createDocumentFragment();
    data.forEach((item) => rows.appendChild(buildRow(item)));
    tbody.appendChild(rows);
  }
  table.appendChild(tbody);

  scrollWrap.appendChild(table);
  container.appendChild(scrollWrap);
}

function buildHead(container) {
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  headRow.className = 'border-b border-[var(--ink-150)]';

  columns.forEach((col) => {
    const isActive = state.sortState.key === col.key;

    const th = document.createElement('th');
    th.scope = 'col';
    th.setAttribute('aria-sort', isActive ? (state.sortState.dir === 'asc' ? 'ascending' : 'descending') : 'none');
    th.className = `whitespace-nowrap px-2 py-1 ${col.align === 'right' ? 'text-right' : 'text-left'}`;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = [
      'inline-flex w-full items-center gap-1.5 px-2 py-2 font-data text-[11px] uppercase tracking-wider transition-colors',
      'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--ink-700)]',
      isActive ? 'text-[var(--ink-950)]' : 'text-[var(--ink-700)] hover:text-[var(--ink-950)]',
      col.align === 'right' ? 'justify-start flex-row-reverse' : 'justify-start',
    ].join(' ');
    button.setAttribute('aria-label', `Ordenar por ${col.label}`);

    const label = document.createElement('span');
    label.textContent = col.label;
    button.appendChild(label);

    if (isActive) {
      const tri = document.createElement('span');
      tri.className = state.sortState.dir === 'asc' ? 'tri-up' : 'tri-down';
      button.appendChild(tri);
    }

    button.addEventListener('click', () => onHeaderActivate(container, col.key));
    th.appendChild(button);
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
  tdImpacto.appendChild(buildDelta(item.impacto_SPY));

  tr.append(tdTicker, tdNombre, tdPeso, tdVar, tdImpacto);
  return tr;
}
