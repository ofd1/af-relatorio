"use client";

import { useEffect, useState, useCallback } from "react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    LineChart,
    Line,
    Legend,
} from "recharts";
import api from "@/lib/api";
import KpiCard from "@/components/KpiCard";
import FinancialTable from "@/components/FinancialTable";
import { formatCompact, formatPercent } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface IndicatorData {
    year: string;
    margins?: {
        margem_bruta: number;
        margem_ebitda: number;
        margem_operacional: number;
        margem_liquida: number;
    };
    absolute?: {
        receita_bruta: number;
        receita_liquida: number;
        lucro_bruto: number;
        ebitda: number;
        lucro_operacional: number;
        lucro_liquido: number;
    };
}

interface StatementData {
    rows: Record<string, any>[];
    structure?: { parents?: string[] };
}

const TABS = ["DRE", "BP", "DFC"] as const;
type Tab = (typeof TABS)[number];

export default function DashboardPage() {
    const [year, setYear] = useState("2025");
    const [availableYears, setAvailableYears] = useState<string[]>(["2025"]);
    const [indicators, setIndicators] = useState<IndicatorData | null>(null);
    const [activeTab, setActiveTab] = useState<Tab>("DRE");
    const [statementData, setStatementData] = useState<StatementData | null>(null);
    const [chartData, setChartData] = useState<any[]>([]);
    const [marginData, setMarginData] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [stmtLoading, setStmtLoading] = useState(false);

    // Fetch summary for available years
    useEffect(() => {
        api
            .get("/api/data/summary")
            .then((res) => {
                if (res.data.years?.length) setAvailableYears(res.data.years);
            })
            .catch(() => { });
    }, []);

    // Fetch indicators
    useEffect(() => {
        setLoading(true);
        api
            .get(`/api/data/indicators?year=${year}`)
            .then((res) => setIndicators(res.data))
            .catch(() => { })
            .finally(() => setLoading(false));
    }, [year]);

    // Fetch DRE data for charts
    useEffect(() => {
        api
            .get(`/api/data/dre?year=${year}`)
            .then((res) => {
                const rows: Record<string, any>[] = res.data.rows || [];
                if (rows.length === 0) return;

                const cols = Object.keys(rows[0]);
                const monthCols = cols.filter(
                    (c) => c !== cols[0] && c !== "Total" && c !== "TOTAL" && c !== "Acumulado"
                );

                // Find specific rows by label
                const findRow = (label: string) =>
                    rows.find((r) => String(r[cols[0]] || "").trim() === label);

                const receitaRow = findRow("Receita Líquida");
                const custoRow = findRow("Custo dos Serviços Prestados") || findRow("(-) Custos");
                const lucroRow = findRow("Lucro Bruto");

                // Bar chart data
                const barData = monthCols.map((month) => ({
                    name: month,
                    receita: Math.abs(parseFloat(receitaRow?.[month]) || 0),
                    custos: Math.abs(parseFloat(custoRow?.[month]) || 0),
                    lucro: parseFloat(lucroRow?.[month]) || 0,
                }));
                setChartData(barData);

                // Line chart: margins
                const margBrutaRow = findRow("Margem Bruta (%)");
                const margEbitdaRow = findRow("Margem EBITDA (%)");
                const margLiqRow = findRow("Margem Líquida (%)");

                if (margBrutaRow || margEbitdaRow || margLiqRow) {
                    const lineData = monthCols.map((month) => ({
                        name: month,
                        bruta: parseFloat(margBrutaRow?.[month]) || 0,
                        ebitda: parseFloat(margEbitdaRow?.[month]) || 0,
                        liquida: parseFloat(margLiqRow?.[month]) || 0,
                    }));
                    setMarginData(lineData);
                } else if (receitaRow) {
                    // Calculate margins from absolute values
                    const lineData = monthCols.map((month) => {
                        const rec = parseFloat(receitaRow?.[month]) || 1;
                        return {
                            name: month,
                            bruta: ((parseFloat(lucroRow?.[month]) || 0) / Math.abs(rec)) * 100,
                            ebitda: ((parseFloat(findRow("EBITDA")?.[month]) || 0) / Math.abs(rec)) * 100,
                            liquida: ((parseFloat(findRow("Lucro Líquido")?.[month]) || 0) / Math.abs(rec)) * 100,
                        };
                    });
                    setMarginData(lineData);
                }
            })
            .catch(() => { });
    }, [year]);

    // Fetch active tab statement
    const fetchStatement = useCallback(
        async (tab: Tab) => {
            setStmtLoading(true);
            try {
                const endpoint = tab.toLowerCase();
                const res = await api.get(`/api/data/${endpoint}?year=${year}`);
                setStatementData(res.data);
            } catch {
                setStatementData(null);
            } finally {
                setStmtLoading(false);
            }
        },
        [year]
    );

    useEffect(() => {
        fetchStatement(activeTab);
    }, [activeTab, fetchStatement]);

    const abs = indicators?.absolute;
    const margins = indicators?.margins;

    const tooltipFormatter = (value: any) =>
        new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(Number(value));

    return (
        <div className="space-y-6">
            {/* Filters */}
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-primary">Dashboard</h2>
                <select
                    value={year}
                    onChange={(e) => setYear(e.target.value)}
                    className="px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-light/30 focus:border-primary-light outline-none"
                >
                    {availableYears.map((y) => (
                        <option key={y} value={y}>
                            {y}
                        </option>
                    ))}
                </select>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <KpiCard
                    title="Receita Líquida"
                    value={loading ? "..." : formatCompact(abs?.receita_liquida || 0)}
                    icon={
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <path d="M2 15l5-5 3 3 8-8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    }
                />
                <KpiCard
                    title="Lucro Líquido"
                    value={loading ? "..." : formatCompact(abs?.lucro_liquido || 0)}
                    variation={margins ? formatPercent(margins.margem_liquida) : undefined}
                    variationType={
                        (abs?.lucro_liquido || 0) >= 0 ? "positive" : "negative"
                    }
                    icon={
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" />
                            <path d="M10 6v8M7 9h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                    }
                />
                <KpiCard
                    title="Margem EBITDA"
                    value={loading ? "..." : `${margins?.margem_ebitda?.toFixed(1) || 0}%`}
                    variationType={
                        (margins?.margem_ebitda || 0) >= 15 ? "positive" : (margins?.margem_ebitda || 0) >= 0 ? "neutral" : "negative"
                    }
                    icon={
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <rect x="3" y="8" width="3" height="9" rx="1" stroke="currentColor" strokeWidth="1.5" />
                            <rect x="8.5" y="5" width="3" height="12" rx="1" stroke="currentColor" strokeWidth="1.5" />
                            <rect x="14" y="3" width="3" height="14" rx="1" stroke="currentColor" strokeWidth="1.5" />
                        </svg>
                    }
                />
                <KpiCard
                    title="Margem Bruta"
                    value={loading ? "..." : `${margins?.margem_bruta?.toFixed(1) || 0}%`}
                    variationType={
                        (margins?.margem_bruta || 0) >= 30 ? "positive" : (margins?.margem_bruta || 0) >= 0 ? "neutral" : "negative"
                    }
                    icon={
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <path d="M3 17V7l4 4 3-6 4 3 3-5v14H3z" stroke="currentColor" strokeWidth="1.5" fill="currentColor" fillOpacity="0.1" strokeLinejoin="round" />
                        </svg>
                    }
                />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Bar chart */}
                <div className="card p-5">
                    <h3 className="text-sm font-semibold text-primary mb-4">
                        Receita vs Custos vs Lucro Bruto
                    </h3>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={chartData} barGap={2}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                            <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="#9ca3af" />
                            <YAxis tick={{ fontSize: 11 }} stroke="#9ca3af" tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                            <Tooltip formatter={tooltipFormatter} />
                            <Legend wrapperStyle={{ fontSize: 12 }} />
                            <Bar dataKey="receita" name="Receita" fill="#4a90d9" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="custos" name="Custos" fill="#ef4444" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="lucro" name="Lucro Bruto" fill="#10b981" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* Line chart */}
                <div className="card p-5">
                    <h3 className="text-sm font-semibold text-primary mb-4">
                        Evolução das Margens (%)
                    </h3>
                    <ResponsiveContainer width="100%" height={280}>
                        <LineChart data={marginData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                            <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="#9ca3af" />
                            <YAxis tick={{ fontSize: 11 }} stroke="#9ca3af" tickFormatter={(v) => `${v}%`} />
                            <Tooltip formatter={(v: any) => `${Number(v).toFixed(1)}%`} />
                            <Legend wrapperStyle={{ fontSize: 12 }} />
                            <Line type="monotone" dataKey="bruta" name="M. Bruta" stroke="#4a90d9" strokeWidth={2} dot={{ r: 3 }} />
                            <Line type="monotone" dataKey="ebitda" name="EBITDA" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                            <Line type="monotone" dataKey="liquida" name="M. Líquida" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Financial statements tabs */}
            <div>
                <div className="flex gap-1 mb-4">
                    {TABS.map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${activeTab === tab
                                ? "bg-primary text-white"
                                : "bg-white text-gray-text hover:bg-gray-100 border border-gray-200"
                                }`}
                        >
                            {tab}
                        </button>
                    ))}
                </div>

                {stmtLoading ? (
                    <div className="card p-12 text-center">
                        <div className="inline-block w-8 h-8 border-2 border-primary-light/30 border-t-primary-light rounded-full animate-spin" />
                    </div>
                ) : (
                    <FinancialTable
                        rows={statementData?.rows || []}
                        structure={statementData?.structure}
                    />
                )}
            </div>
        </div>
    );
}
