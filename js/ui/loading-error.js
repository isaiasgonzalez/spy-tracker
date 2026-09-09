// ---------------------------------------------------------------------------
// Estados de "cargando" y "error". Tocá este archivo si querés cambiar el
// spinner, el mensaje de error, o qué tan detallado es el diagnóstico.
// ---------------------------------------------------------------------------

export function renderLoading(container, statsStrip) {
  statsStrip.classList.add('hidden');
  container.replaceChildren();
  const wrap = document.createElement('div');
  wrap.className = 'flex items-center justify-center gap-3 py-16 text-[var(--ink-700)]';
  const spinner = document.createElement('div');
  spinner.className = 'h-3.5 w-3.5 rounded-full border-2 border-[var(--ink-150)] border-t-[var(--ink-700)] animate-spin';
  const text = document.createElement('span');
  text.className = 'font-data text-xs uppercase tracking-wide';
  text.textContent = 'Cargando datos';
  wrap.append(spinner, text);
  container.appendChild(wrap);
}

export function renderError(container, statsStrip, err) {
  statsStrip.classList.add('hidden');
  container.replaceChildren();
  const wrap = document.createElement('div');
  wrap.className = 'px-6 py-14 text-center';
  const title = document.createElement('p');
  title.className = 'text-sm font-medium text-[var(--loss)]';
  title.textContent = 'No se pudieron cargar los datos.';
  const detail = document.createElement('p');
  detail.className = 'font-data text-xs text-[var(--ink-700)] mt-3 max-w-md mx-auto leading-relaxed';
  detail.textContent = 'Verificá que "qqq_data.json" esté junto a este archivo y que lo estés sirviendo desde un servidor local (no abierto como file://). Detalle: ' + err.message;
  wrap.append(title, detail);
  container.appendChild(wrap);
}
