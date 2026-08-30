export function money(v: number): string {
  const sign = v < 0 ? "−$" : "$";
  return sign + Math.round(Math.abs(v)).toLocaleString("en-US");
}

export function moneyShort(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "−$" : "$";
  if (abs >= 1_000_000) return sign + (abs / 1_000_000).toFixed(abs >= 10_000_000 ? 1 : 2) + "M";
  if (abs >= 1_000) return sign + (abs / 1_000).toFixed(0) + "k";
  return money(v);
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
