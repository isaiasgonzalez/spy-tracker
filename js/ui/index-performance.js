import { formatPercent } from '../format.js';

// ---------------------------------------------------------------------------
// Bloque "Año · Mes · Día" en la esquina superior derecha, con la variación
// REAL del índice QQQ (no de un constituyente puntual) en cada horizonte.
// Si el JSON no trae variación mensual o anual, se muestra un guion en vez
// de romper o mentir con un cero.
// ---------------------------------------------------------------------------

export function renderIndexPerformance(el, periods) {
  el.replaceChildren();

  const items = [
    { label: '1 Año', value: periods.yearly },
    { label: '1 Mes', value: periods.monthly },
    { label: 'Día', value: periods.daily },
  ];

  items.forEach(function (it) {
    const cell = document.createElement('div');
    cell.className = 'text-right';

    const label = document.createElement('p');
    label.className = 'font-data text-[10px] uppercase tracking-wide text-[var(--ink-700)] mb-0.5';
    label.textContent = it.label;

    const num = it.value;
    const positive = num !== null && num > 0;
    const negative = num !== null && num < 0;

    const value = document.createElement('p');
    value.className = 'font-data text-sm font-medium ' +
      (positive ? 'text-[var(--gain)]' : negative ? 'text-[var(--loss)]' : 'text-[var(--ink-700)]');
    value.textContent = num === null ? '—' : formatPercent(num, true);

    cell.append(label, value);
    el.appendChild(cell);
  });

  el.classList.remove('hidden');
}