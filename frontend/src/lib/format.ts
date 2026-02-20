/**
 * Utility formatters for the dashboard.
 */

/** Format number as BRL currency (R$ 1.234,56) */
export function formatCurrency(value: number): string {
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(value);
}

/** Format number as compact (1.2M, 345K, etc.) */
export function formatCompact(value: number): string {
    if (Math.abs(value) >= 1_000_000) {
        return `R$ ${(value / 1_000_000).toFixed(1)}M`;
    }
    if (Math.abs(value) >= 1_000) {
        return `R$ ${(value / 1_000).toFixed(0)}K`;
    }
    return formatCurrency(value);
}

/** Format percentage with sign */
export function formatPercent(value: number): string {
    const sign = value > 0 ? "+" : "";
    return `${sign}${value.toFixed(1)}%`;
}

/** Format number for table cells: red if negative */
export function formatTableValue(value: number | string): string {
    if (typeof value === "string") return value;
    return new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value);
}
