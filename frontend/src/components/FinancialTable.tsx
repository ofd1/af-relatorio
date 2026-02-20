"use client";

import { useState, useMemo, Fragment } from "react";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface FinancialTableProps {
    rows: Record<string, any>[];
    structure?: { parents?: string[] };
}

export default function FinancialTable({ rows, structure }: FinancialTableProps) {
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
    const [showPercent, setShowPercent] = useState(false);

    // Extract month columns (all columns except the first label column)
    const columns = useMemo(() => {
        if (rows.length === 0) return [];
        return Object.keys(rows[0]);
    }, [rows]);

    const labelCol = columns[0] || "Conta";
    const valueColumns = columns.slice(1);

    const parentLabels = useMemo(() => {
        return new Set(structure?.parents || []);
    }, [structure]);

    // Determine hierarchy: rows where label is in parents are collapsible
    const processedRows = useMemo(() => {
        const result: { row: Record<string, any>; level: number; isParent: boolean; parentKey: string | null }[] = [];
        let currentParent: string | null = null;

        for (const row of rows) {
            const label = String(row[labelCol] || "").trim();
            const isParent = parentLabels.has(label) || label === label.toUpperCase();

            if (isParent) {
                currentParent = label;
                result.push({ row, level: 0, isParent: true, parentKey: null });
            } else {
                result.push({
                    row,
                    level: currentParent ? 1 : 0,
                    isParent: false,
                    parentKey: currentParent,
                });
            }
        }
        return result;
    }, [rows, labelCol, parentLabels]);

    const toggleRow = (label: string) => {
        setExpandedRows((prev) => {
            const next = new Set(prev);
            if (next.has(label)) {
                next.delete(label);
            } else {
                next.add(label);
            }
            return next;
        });
    };

    // Format cell value
    const formatCell = (value: any, colIndex: number) => {
        if (value === "" || value === null || value === undefined) return "—";
        const num = typeof value === "number" ? value : parseFloat(value);
        if (isNaN(num)) return value;

        if (showPercent && colIndex > 0) {
            // Vertical analysis: find the first row's value for this column as base
            const baseRow = rows[0];
            if (baseRow) {
                const baseVal = parseFloat(baseRow[valueColumns[colIndex - 1]]);
                if (baseVal && baseVal !== 0) {
                    const pct = (num / Math.abs(baseVal)) * 100;
                    return `${pct.toFixed(1)}%`;
                }
            }
        }

        return new Intl.NumberFormat("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(num);
    };

    if (rows.length === 0) {
        return (
            <div className="card p-8 text-center text-gray-text">
                <p>Nenhum dado disponível.</p>
            </div>
        );
    }

    return (
        <div className="card overflow-hidden">
            {/* Toggle */}
            <div className="flex items-center justify-end px-4 py-2 border-b border-gray-100">
                <button
                    onClick={() => setShowPercent(!showPercent)}
                    className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${showPercent
                            ? "bg-primary-light text-white"
                            : "bg-gray-100 text-gray-text hover:bg-gray-200"
                        }`}
                >
                    {showPercent ? "Análise Vertical (%)" : "Valores Absolutos"}
                </button>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="bg-secondary">
                            {columns.map((col, i) => (
                                <th
                                    key={col}
                                    className={`px-4 py-3 text-xs font-semibold text-gray-text uppercase tracking-wider whitespace-nowrap ${i === 0 ? "text-left sticky left-0 bg-secondary z-10 min-w-[250px]" : "text-right"
                                        }`}
                                >
                                    {col}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {processedRows.map(({ row, level, isParent, parentKey }, idx) => {
                            const label = String(row[labelCol] || "").trim();

                            // Hide children if parent is collapsed
                            if (parentKey && !expandedRows.has(parentKey)) return null;

                            return (
                                <Fragment key={idx}>
                                    <tr
                                        className={`border-b border-gray-50 transition-colors hover:bg-blue-50/30 ${isParent ? "bg-gray-50/50" : ""
                                            }`}
                                    >
                                        {columns.map((col, colIdx) => {
                                            if (colIdx === 0) {
                                                return (
                                                    <td
                                                        key={col}
                                                        className={`px-4 py-2.5 font-medium sticky left-0 bg-white z-10 whitespace-nowrap ${isParent ? "text-primary font-semibold" : "text-foreground"
                                                            }`}
                                                        style={{ paddingLeft: `${16 + level * 24}px` }}
                                                    >
                                                        {isParent && (
                                                            <button
                                                                onClick={() => toggleRow(label)}
                                                                className="inline-flex items-center justify-center w-5 h-5 mr-2 rounded hover:bg-gray-200 transition-colors"
                                                            >
                                                                <svg
                                                                    width="12"
                                                                    height="12"
                                                                    viewBox="0 0 12 12"
                                                                    className={`transition-transform ${expandedRows.has(label) ? "rotate-90" : ""
                                                                        }`}
                                                                >
                                                                    <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                                                                </svg>
                                                            </button>
                                                        )}
                                                        {label}
                                                    </td>
                                                );
                                            }

                                            const val = row[col];
                                            const numVal = typeof val === "number" ? val : parseFloat(val);
                                            const isNeg = !isNaN(numVal) && numVal < 0;

                                            return (
                                                <td
                                                    key={col}
                                                    className={`px-4 py-2.5 text-right whitespace-nowrap tabular-nums ${isNeg ? "text-negative" : ""
                                                        } ${isParent ? "font-semibold" : ""}`}
                                                >
                                                    {formatCell(val, colIdx)}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                </Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
