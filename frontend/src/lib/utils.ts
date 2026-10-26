export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

function parse(value: string): Date {
  const hasZone = /Z$|[+-]\d{2}:\d{2}$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function formatDate(value: string | null | undefined, withTime = true): string {
  if (!value) {
    return "—";
  }
  const date = parse(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function formatDay(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  }).format(date);
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = parse(value);
  const diffMinutes = Math.round((date.getTime() - Date.now()) / 60000);
  const formatter = new Intl.RelativeTimeFormat("id-ID", { numeric: "auto" });
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["minute", 60],
    ["hour", 24],
    ["day", 30],
    ["month", 12],
  ];
  let amount = diffMinutes;
  for (const [unit, factor] of units) {
    if (Math.abs(amount) < factor) {
      return formatter.format(amount, unit);
    }
    amount = Math.round(amount / factor);
  }
  return formatter.format(amount, "year");
}

export function formatPercent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function hoursLabel(hours: number | null): string {
  if (hours === null || Number.isNaN(hours)) {
    return "waktu tidak diketahui";
  }
  if (hours < 1) {
    return `${Math.round(hours * 60)} menit`;
  }
  return `${hours.toFixed(1)} jam`;
}

export function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}
