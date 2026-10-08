import { formatPercent } from '../format.js';

// ---------------------------------------------------------------------------
// Franja de estadísticas ("cinta de cotización") debajo del header. Si
// querés agregar/quitar un dato de la franja (ej. "promedio de peso"), es
// acá, editando el array `items`.
// ---------------------------------------------------------------------------

export function renderStats(statsStrip, data, root = null) {
  statsStrip.replaceChildren();
  const summary = data.reduce((result, item) => {
    const variation = Number(item.variacion_diaria);
    const impact = Number(item.impacto_SPY);
    if (variation > 0) result.up += 1;
    if (variation < 0) result.down += 1;
    if (Number.isFinite(impact)) result.netImpact += impact;
    return result;
  }, { up: 0, down: 0, netImpact: 0 });

  const items = [
    { text: data.length + ' acciones', tone: null },
    { text: summary.up + ' suben', tone: 'gain' },
    { text: summary.down + ' bajan', tone: 'loss' },
    {
      text: 'Impacto neto de ' + formatPercent(summary.netImpact, true),
      tone: summary.netImpact > 0 ? 'gain' : summary.netImpact < 0 ? 'loss' : null,
    },
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
