// ---------------------------------------------------------------------------
// Formato de números. Si mañana querés cambiar decimales, separador de miles,
// o el símbolo usado para "sin dato", es acá.
// ---------------------------------------------------------------------------

export function formatSigned(value, unit) {
  const num = Number(value);
  if (Number.isNaN(num)) return '—';
  const formatted = Math.abs(num).toFixed(2) + unit;
  if (num > 0) return '+' + formatted;
  if (num < 0) return '-' + formatted;
  return formatted;
}

export function formatPercent(value, withSign) {
  const num = Number(value);
  if (Number.isNaN(num)) return '—';
  if (!withSign) return Math.abs(num).toFixed(2) + '%';
  return formatSigned(num, '%');
}
