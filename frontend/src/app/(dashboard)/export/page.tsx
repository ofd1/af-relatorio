"use client";

import { useState } from "react";
import api from "@/lib/api";

const CHART_OPTIONS = [
    { id: "receita_custos_lucro", label: "Receita vs Custos vs Lucro Bruto" },
    { id: "evolucao_margens", label: "Evolução das Margens" },
    { id: "composicao_despesas", label: "Composição de Despesas (pizza)" },
    { id: "dre_resumida", label: "DRE resumida" },
    { id: "bp_resumido", label: "BP resumido" },
];

export default function ExportPage() {
    const [year, setYear] = useState("2025");
    const [selectedCharts, setSelectedCharts] = useState<string[]>([]);
    const [downloading, setDownloading] = useState<"excel" | "pdf" | null>(null);

    const toggleChart = (id: string) => {
        setSelectedCharts((prev) =>
            prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
        );
    };

    const handleExcelDownload = async () => {
        setDownloading("excel");
        try {
            const res = await api.get(`/api/export/excel?year=${year}`, {
                responseType: "blob",
            });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const a = document.createElement("a");
            a.href = url;
            a.download = `relatorio_financeiro_${year}.xlsx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch {
            alert("Erro ao baixar Excel.");
        } finally {
            setDownloading(null);
        }
    };

    const handlePdfDownload = async () => {
        setDownloading("pdf");
        try {
            const res = await api.post(
                `/api/export/pdf?year=${parseInt(year)}`,
                { year: parseInt(year), charts: selectedCharts },
                { responseType: "blob" }
            );
            const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
            const a = document.createElement("a");
            a.href = url;
            a.download = `relatorio_financeiro_${year}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch {
            alert("Erro ao gerar PDF.");
        } finally {
            setDownloading(null);
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-6">
            <h2 className="text-xl font-bold text-primary">Exportar Relatórios</h2>

            {/* Year selector */}
            <div className="card p-4 flex items-center gap-4">
                <label className="text-sm font-medium text-gray-text">Período:</label>
                <select
                    value={year}
                    onChange={(e) => setYear(e.target.value)}
                    className="px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-light/30 outline-none"
                >
                    {["2023", "2024", "2025", "2026"].map((y) => (
                        <option key={y} value={y}>{y}</option>
                    ))}
                </select>
            </div>

            {/* Excel Export */}
            <div className="card overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 bg-secondary/50">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-positive/10 flex items-center justify-center">
                            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                                <rect x="2" y="2" width="14" height="14" rx="2" stroke="#10b981" strokeWidth="1.5" />
                                <path d="M5 6h8M5 9h8M5 12h5" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" />
                            </svg>
                        </div>
                        <h3 className="text-sm font-semibold text-foreground">Exportar Excel</h3>
                    </div>
                </div>
                <div className="p-5">
                    <p className="text-sm text-gray-text mb-4">
                        Gera arquivo Excel formatado com abas DRE, BP e DFC para o ano selecionado.
                    </p>
                    <button
                        onClick={handleExcelDownload}
                        disabled={downloading === "excel"}
                        className="px-5 py-2.5 bg-positive hover:bg-positive/90 disabled:opacity-50 text-white font-medium rounded-xl transition-all flex items-center gap-2 text-sm"
                    >
                        {downloading === "excel" ? (
                            <>
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Gerando...
                            </>
                        ) : (
                            <>
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                                    <path d="M8 10V2M5 7l3 3 3-3M3 12v1.5a1.5 1.5 0 001.5 1.5h7a1.5 1.5 0 001.5-1.5V12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                                </svg>
                                Baixar Excel
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* PDF Export */}
            <div className="card overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100 bg-secondary/50">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-negative/10 flex items-center justify-center">
                            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                                <rect x="3" y="1" width="12" height="16" rx="2" stroke="#ef4444" strokeWidth="1.5" />
                                <path d="M7 5h4M7 8h4M7 11h2" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" />
                            </svg>
                        </div>
                        <h3 className="text-sm font-semibold text-foreground">Gerar PDF</h3>
                    </div>
                </div>
                <div className="p-5 space-y-4">
                    <p className="text-sm text-gray-text">
                        Selecione as seções para incluir no relatório PDF:
                    </p>

                    <div className="space-y-2">
                        {CHART_OPTIONS.map((opt) => (
                            <label
                                key={opt.id}
                                className={`flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-colors border ${selectedCharts.includes(opt.id)
                                        ? "border-primary-light bg-primary-light/5"
                                        : "border-gray-200 hover:bg-gray-50"
                                    }`}
                            >
                                <input
                                    type="checkbox"
                                    checked={selectedCharts.includes(opt.id)}
                                    onChange={() => toggleChart(opt.id)}
                                    className="w-4 h-4 text-primary-light rounded border-gray-300 focus:ring-primary-light/50 accent-[#4a90d9]"
                                />
                                <span className="text-sm">{opt.label}</span>
                            </label>
                        ))}
                    </div>

                    <button
                        onClick={handlePdfDownload}
                        disabled={downloading === "pdf"}
                        className="px-5 py-2.5 bg-primary hover:bg-primary-dark disabled:opacity-50 text-white font-medium rounded-xl transition-all flex items-center gap-2 text-sm"
                    >
                        {downloading === "pdf" ? (
                            <>
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                                Gerando PDF...
                            </>
                        ) : (
                            <>
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                                    <rect x="2" y="1" width="12" height="14" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
                                    <path d="M5 5h6M5 8h6M5 11h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                                </svg>
                                Gerar PDF
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}
