import { state, getQqqTotal } from './state.js';
import { formatSigned, formatPercent } from './format.js';
import { buildDeltaInline } from './ui/delta.js';

// ---------------------------------------------------------------------------
// Feature autocontenida: "Descargar resumen" (tarjeta PNG con top 5 que
// suben / top 5 que bajan). Todo lo que tiene que ver con esta feature vive
// en este único archivo - podés cambiar cuántos movers muestra, el diseño
// de la tarjeta, o el nombre del archivo descargado sin tocar la tabla ni
// el resto de la app.
// ---------------------------------------------------------------------------

export function initCapture(captureBtn, captureBtnLabel) {
  captureBtn.addEventListener('click', function () {
    onCaptureClick(captureBtn, captureBtnLabel);
  });
}

async function onCaptureClick(captureBtn, captureBtnLabel) {
  if (!state.rawData || state.rawData.length === 0 || typeof html2canvas === 'undefined') return;

  captureBtn.disabled = true;
  captureBtnLabel.textContent = 'Generando…';

  const card = buildCaptureCard();
  document.body.appendChild(card);

  try {
    // Evita que la imagen salga con la tipografía de reemplazo si los
    // webfonts todavía no terminaron de cargar en el momento del clic.
    if (document.fonts && document.fonts.ready) {
      try { await document.fonts.ready; } catch (e) { /* no crítico */ }
    }
    const canvas = await html2canvas(card, { scale: 2, backgroundColor: null });
    const link = document.createElement('a');
    link.href = canvas.toDataURL('image/png');
    link.download = 'QQQ_resumen_' + new Date().toISOString().slice(0, 10) + '.png';
    link.click();
    captureBtnLabel.textContent = 'Listo ✓';
  } catch (err) {
    console.error('Error al generar la imagen:', err);
    captureBtnLabel.textContent = 'No se pudo generar';
  } finally {
    document.body.removeChild(card);
    setTimeout(function () {
      captureBtnLabel.textContent = 'Descargar resumen';
      captureBtn.disabled = false;
    }, 1800);
  }
}

// Cuántos movers mostrar en cada columna de la tarjeta. Cambiar esto es el
// único paso para pasar de "top 5" a "top 3" o "top 10".
const TOP_N = 5;

// Arma, fuera de pantalla, la tarjeta que se convierte en imagen. Diseño
// compacto y centrado: todo el bloque de contenido se alinea al centro, sin
// flechitas (solo el signo +/- comunica dirección), con el mínimo de aire
// necesario para que las secciones se distingan. Igual que el resto del
// archivo: todo dato dinámico entra vía textContent.
function buildCaptureCard() {
  const total = getQqqTotal();
  const topSuba = state.rawData.slice().sort(function (a, b) { return Number(b.impacto_qqq) - Number(a.impacto_qqq); }).slice(0, TOP_N);
  const topBaja = state.rawData.slice().sort(function (a, b) { return Number(a.impacto_qqq) - Number(b.impacto_qqq); }).slice(0, TOP_N);
  const sumSuba = topSuba.reduce(function (acc, it) { return acc + Number(it.impacto_qqq || 0); }, 0);
  const sumBaja = topBaja.reduce(function (acc, it) { return acc + Number(it.impacto_qqq || 0); }, 0);
  const fechaHoy = new Date().toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });

  const MONO = '"IBM Plex Mono", monospace';
  const SERIF = '"Fraunces", serif';

  const card = document.createElement('div');
  card.style.cssText =
    'position:fixed; left:-9999px; top:0; width:680px; padding:32px; box-sizing:border-box;' +
    'background-color:var(--paper); color:var(--ink-950); font-family:"IBM Plex Sans", sans-serif; text-align:center;';

  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom:20px;';
  const eyebrow = document.createElement('p');
  eyebrow.style.cssText = 'font-family:' + MONO + '; font-size:11px; letter-spacing:0.2em; text-transform:uppercase; color:var(--ink-700); margin:0 0 6px 0;';
  eyebrow.textContent = 'Resumen diario · ' + fechaHoy;
  const title = document.createElement('p');
  title.style.cssText = 'font-family:' + SERIF + '; font-weight:500; font-size:26px; color:var(--ink-950); margin:0 0 8px 0;';
  title.textContent = 'Invesco QQQ';
  const legend = document.createElement('p');
  legend.style.cssText = 'font-family:' + MONO + '; font-size:10px; letter-spacing:0.05em; color:var(--ink-700); margin:0;';
  legend.textContent = 'qqq-tracker.vercel.app | x.com/isaias3g';
  header.append(eyebrow, title, legend);

  // Cifra principal: variación total del índice en el día.
  const hero = document.createElement('div');
  hero.style.cssText = 'margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid var(--ink-150);';
  const heroLabel = document.createElement('p');
  heroLabel.style.cssText = 'font-family:' + MONO + '; font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:var(--ink-700); margin:0 0 4px 0;';
  heroLabel.textContent = 'Variación del índice hoy';
  const total_positive = total > 0;
  const total_negative = total < 0;
  const heroColor = total_positive ? 'var(--gain)' : total_negative ? 'var(--loss)' : 'var(--ink-950)';
  const heroNum = document.createElement('p');
  heroNum.style.cssText =
    'font-family:' + MONO + '; font-variant-numeric:tabular-nums; font-size:40px; font-weight:500; color:' + heroColor + '; margin:0;';
  heroNum.textContent = formatPercent(total, true);
  hero.append(heroLabel, heroNum);

  const cols = document.createElement('div');
  cols.style.cssText = 'display:flex; justify-content:center;';
  const colSuba = buildMoverColumn('Impulsan la suba', 'gain', topSuba, sumSuba, total);
  const colBaja = buildMoverColumn('Presionan a la baja', 'loss', topBaja, sumBaja, total);
  colSuba.style.cssText += 'flex:1 1 0%; min-width:0; padding-right:20px;';
  colBaja.style.cssText += 'flex:1 1 0%; min-width:0; padding-left:20px; border-left:1px solid var(--ink-150);';
  cols.append(colSuba, colBaja);

  card.append(header, hero, cols);
  return card;
}

// Columna de movers: contenido centrado, filas compactas, sin flechitas (el
// color + signo alcanza para indicar dirección).
function buildMoverColumn(heading, tone, items, sum, total) {
  const MONO = '"IBM Plex Mono", monospace';
  const col = document.createElement('div'); // el flex/padding/border final se fija en buildCaptureCard()

  const h = document.createElement('p');
  h.style.cssText =
    'font-family:' + MONO + '; font-size:11px; text-transform:uppercase; letter-spacing:0.05em; font-weight:600; margin:0 0 10px 0;' +
    'color:' + (tone === 'gain' ? 'var(--gain)' : 'var(--loss)') + ';';
  h.textContent = heading;
  col.appendChild(h);

  // Etiquetas de columna, una sola vez (no por fila), con una línea fina debajo.
  const labelsRow = document.createElement('div');
  labelsRow.style.cssText =
    'display:flex; align-items:baseline; justify-content:center; gap:14px; padding-bottom:4px; margin-bottom:0; border-bottom:1px solid var(--ink-150);';
  const labelTicker = document.createElement('span');
  labelTicker.style.cssText = 'font-family:' + MONO + '; font-size:10px; text-transform:uppercase; letter-spacing:0.05em; color:var(--ink-700); width:54px; text-align:center;';
  labelTicker.textContent = 'Ticker';
  const labelVar = document.createElement('span');
  labelVar.style.cssText = 'font-family:' + MONO + '; font-size:10px; text-transform:uppercase; letter-spacing:0.05em; color:var(--ink-700); width:56px; text-align:center;';
  labelVar.textContent = 'Var.';
  const labelAporte = document.createElement('span');
  labelAporte.style.cssText = 'font-family:' + MONO + '; font-size:10px; text-transform:uppercase; letter-spacing:0.05em; color:var(--ink-700); width:60px; text-align:center;';
  labelAporte.textContent = 'Aporte';
  labelsRow.append(labelTicker, labelVar, labelAporte);
  col.appendChild(labelsRow);

  items.forEach(function (item, idx) {
    const row = document.createElement('div');
    row.style.cssText =
      'display:flex; align-items:center; justify-content:center; gap:14px; padding:6px 0;' +
      (idx < items.length - 1 ? 'border-bottom:1px solid var(--ink-150);' : '');

    const ticker = document.createElement('span');
    ticker.style.cssText = 'font-family:' + MONO + '; font-size:14px; font-weight:500; color:var(--ink-950); width:54px; text-align:center; white-space:nowrap;';
    ticker.textContent = item.ticker;

    const varWrap = document.createElement('span');
    varWrap.style.cssText = 'width:56px; font-size:13px; text-align:center; display:inline-block;';
    varWrap.appendChild(buildDeltaInline(item.variacion_diaria));

    const aporteWrap = document.createElement('span');
    aporteWrap.style.cssText = 'width:60px; font-size:13px; text-align:center; display:inline-block;';
    aporteWrap.appendChild(buildDeltaInline(item.impacto_qqq, ' pp'));

    row.append(ticker, varWrap, aporteWrap);
    col.appendChild(row);
  });

  const caption = document.createElement('p');
  caption.style.cssText = 'font-family:' + MONO + '; font-size:11px; color:var(--ink-700); text-align:center; margin:10px 0 0 0;';
  caption.textContent = 'Aportan ' + formatSigned(sum, ' pp') + ' sobre el ' + formatPercent(total, true) + ' del día';
  col.appendChild(caption);

  return col;
}