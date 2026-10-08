// ---------------------------------------------------------------------------
// Formato de números. Si mañana querés cambiar decimales, separador de miles,
// o el símbolo usado para "sin dato", es acá.
// ---------------------------------------------------------------------------

function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

export function formatSigned(value, unit = '') {
  const number = toFiniteNumber(value);
  if (number === null) return '—';
  const formatted = `${Math.abs(number).toFixed(2)}${unit}`;
  if (number > 0) return `+${formatted}`;
  if (number < 0) return `-${formatted}`;
  return formatted;
}

export function formatPercent(value, withSign = false) {
  const number = toFiniteNumber(value);
  if (number === null) return '—';
  return withSign ? formatSigned(number, '%') : `${Math.abs(number).toFixed(2)}%`;
}
