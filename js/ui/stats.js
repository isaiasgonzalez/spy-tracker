import { formatPercent } from '../format.js';

// ---------------------------------------------------------------------------
// Franja de estadísticas ("cinta de cotización") debajo del header. Si
// querés agregar/quitar un dato de la franja (ej. "promedio de peso"), es
// acá, editando el array `items`.
// ---------------------------------------------------------------------------

export function renderStats(statsStrip, data, root = null) {
  statsStrip.replaceChildren();
  const up = data.filter(function (d) { return Number(d.variacion_diaria) > 0; }).length;
  const down = data.filter(function (d) { return Number(d.variacion_diaria) < 0; }).length;
  const netImpact = data.reduce(function (sum, d) { return sum + Number(d.impacto_SPY || 0); }, 0);

  const items = [
    { text: data.length + ' acciones', tone: null },
    { text: up + ' suben', tone: 'gain' },
    { text: down + ' bajan', tone: 'loss' },
    { text: 'Impacto neto de ' + formatPercent(netImpact, true), tone: netImpact > 0 ? 'gain' : netImpact < 0 ? 'loss' : null },
  ];

  const marketDate = root && root.fecha_datos_mercado;
  if (root && Array.isArray(root.errores) && root.errores.length) {
    items.push({ text: root.errores.length + ' acciones sin datos válidos', tone: null });
  }
  if (marketDate && /^\d{4}-\d{2}-\d{2}$/.test(marketDate)) {
    const [year, month, day] = marketDate.split('-');
    items.push({ text: 'Datos de mercado: ' + day + '/' + month + '/' + year, tone: null });
  } else {
    items.push({ text: 'Fecha de mercado no disponible', tone: null });
  }

  items.forEach(function (it, idx) {
    if (idx > 0) {
      const dot = document.createElement('span');
      dot.className = 'text-[var(--ink-150)]';
      dot.textContent = '·';
      statsStrip.appendChild(dot);
    }
    const span = document.createElement('span');
    span.className = it.tone === 'gain' ? 'text-[var(--gain)]' : it.tone === 'loss' ? 'text-[var(--loss)]' : '';
    span.textContent = it.text;
    statsStrip.appendChild(span);
  });

  statsStrip.classList.remove('hidden');
}
