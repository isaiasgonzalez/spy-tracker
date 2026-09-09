import { formatSigned } from '../format.js';

// ---------------------------------------------------------------------------
// Piezas visuales reutilizadas por la tabla en pantalla y por la tarjeta de
// captura. Si querés cambiar cómo se ve un número positivo/negativo (color,
// triángulo, etc.), es acá y se refleja en los dos lugares.
// ---------------------------------------------------------------------------

// Requisito 3: verde para positivo, rojo para negativo.
// unit es opcional (por defecto '%'); el resumen descargable la usa con ' pp'.
export function buildDelta(value, unit) {
  const displayUnit = unit || '%';
  const num = Number(value);
  const positive = num > 0;
  const negative = num < 0;

  const span = document.createElement('span');
  span.className = 'inline-flex items-center justify-end ' +
    (positive ? 'text-[var(--gain)]' : negative ? 'text-[var(--loss)]' : 'text-[var(--ink-700)]');

  if (positive || negative) {
    const tri = document.createElement('span');
    tri.className = positive ? 'tri-up' : 'tri-down';
    span.appendChild(tri);
  }

  const numSpan = document.createElement('span');
  numSpan.textContent = formatSigned(num, displayUnit); // dato en texto plano vía textContent
  span.appendChild(numSpan);
  return span;
}

// Versión sin triángulo: solo color + signo (+/-). Se usa SOLO dentro de la
// tarjeta de captura (capture.js), que es la única parte de la app donde no
// queremos el ícono de flecha, para que la imagen quede más limpia. El color
// (verde/rojo) ya comunica la dirección, así que el signo alcanza.
export function buildDeltaInline(value, unit) {
  const displayUnit = unit || '%';
  const num = Number(value);
  const positive = num > 0;
  const negative = num < 0;
  const color = positive ? 'var(--gain)' : negative ? 'var(--loss)' : 'var(--ink-700)';

  const span = document.createElement('span');
  span.style.color = color;
  span.textContent = formatSigned(num, displayUnit);
  return span;
}