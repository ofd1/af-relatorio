"use client";

import { useEffect, useState, useMemo } from "react";
import api from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface DEPARAItem {
    [key: string]: any;
}

export default function DEPARAPage() {
    const [data, setData] = useState<DEPARAItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState<"all" | "OK" | "Pendente">("all");
    const [groupFilter, setGroupFilter] = useState<string>("all");
    const [searchTerm, setSearchTerm] = useState("");
    const [editingRow, setEditingRow] = useState<string | null>(null);
    const [editValue, setEditValue] = useState("");
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const res = await api.get("/api/depara");
            setData(res.data.depara || []);
        } catch {
            // empty
        } finally {
            setLoading(false);
        }
    };

    // Derive columns and groups from data
    const columns = useMemo(() => {
        if (data.length === 0) return [];
        return Object.keys(data[0]);
    }, [data]);

    const groups = useMemo(() => {
        const set = new Set<string>();
        data.forEach((row) => {
            const g = row.grupo || row.Grupo || row.tipo || "";
            if (g) set.add(String(g));
        });
        return Array.from(set);
    }, [data]);

    // Get key fields
    const codigoKey = columns.find((c) =>
        ["codigo", "codigo_conta", "Código", "Codigo"].includes(c)
    ) || columns[0];
    const tituloKey = columns.find((c) =>
        ["titulo", "titulo_conta", "Título", "Titulo", "titulo_original"].includes(c)
    ) || columns[1];
    const classificacaoKey = columns.find((c) =>
        ["classificacao", "Classificação", "classificacao_padrao"].includes(c)
    ) || columns[2];
    const grupoKey = columns.find((c) =>
        ["grupo", "Grupo", "tipo"].includes(c)
    ) || "";
    const statusKey = columns.find((c) =>
        ["status", "Status"].includes(c)
    ) || "";

    // Filtered data
    const filtered = useMemo(() => {
        return data.filter((row) => {
            // Status filter
            if (statusFilter !== "all") {
                const status = String(row[statusKey] || "").trim();
                if (statusFilter === "Pendente" && status !== "Pendente") return false;
                if (statusFilter === "OK" && status !== "OK") return false;
            }
            // Group filter
            if (groupFilter !== "all") {
                const g = String(row[grupoKey] || "").trim();
                if (g !== groupFilter) return false;
            }
            // Search
            if (searchTerm) {
                const term = searchTerm.toLowerCase();
                return Object.values(row).some((v) =>
                    String(v || "").toLowerCase().includes(term)
                );
            }
            return true;
        });
    }, [data, statusFilter, groupFilter, searchTerm, statusKey, grupoKey]);

    // Distinct classifications for dropdown
    const classifications = useMemo(() => {
        const set = new Set<string>();
        data.forEach((row) => {
            const c = String(row[classificacaoKey] || "").trim();
            if (c) set.add(c);
        });
        return Array.from(set).sort();
    }, [data, classificacaoKey]);

    const handleSave = async (codigo: string) => {
        setSaving(true);
        try {
            await api.put(`/api/depara/${encodeURIComponent(codigo)}`, {
                classificacao: editValue,
            });
            // Update local data
            setData((prev) =>
                prev.map((row) =>
                    String(row[codigoKey]) === codigo
                        ? { ...row, [classificacaoKey]: editValue, [statusKey]: "OK" }
                        : row
                )
            );
            setEditingRow(null);
            setToast({ type: "success", message: `Conta ${codigo} atualizada com sucesso.` });
            setTimeout(() => setToast(null), 3000);
        } catch (err: any) {
            setToast({ type: "error", message: err.response?.data?.detail || "Erro ao salvar." });
            setTimeout(() => setToast(null), 4000);
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <div className="w-8 h-8 border-2 border-primary-light/30 border-t-primary-light rounded-full animate-spin" />
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-primary">DEPARA de Contas</h2>
                <span className="text-sm text-gray-text">
                    {filtered.length} de {data.length} registros
                </span>
            </div>

            {/* Filters */}
            <div className="card p-4 flex flex-wrap gap-3 items-center">
                <input
                    type="text"
                    placeholder="Buscar..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="flex-1 min-w-[200px] px-3 py-2 text-sm bg-secondary border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-light/30 focus:border-primary-light outline-none"
                />
                <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as any)}
                    className="px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-light/30 outline-none"
                >
                    <option value="all">Todos Status</option>
                    <option value="OK">OK</option>
                    <option value="Pendente">Pendente</option>
                </select>
                {groups.length > 0 && (
                    <select
                        value={groupFilter}
                        onChange={(e) => setGroupFilter(e.target.value)}
                        className="px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-primary-light/30 outline-none"
                    >
                        <option value="all">Todos Grupos</option>
                        {groups.map((g) => (
                            <option key={g} value={g}>{g}</option>
                        ))}
                    </select>
                )}
            </div>

            {/* Table */}
            <div className="card overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-secondary border-b border-gray-200">
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-text uppercase tracking-wider">
                                    Código
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-text uppercase tracking-wider">
                                    Título Original
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-text uppercase tracking-wider min-w-[250px]">
                                    Classificação
                                </th>
                                {grupoKey && (
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-text uppercase tracking-wider">
                                        Grupo
                                    </th>
                                )}
                                {statusKey && (
                                    <th className="px-4 py-3 text-center text-xs font-semibold text-gray-text uppercase tracking-wider">
                                        Status
                                    </th>
                                )}
                                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-text uppercase tracking-wider w-[80px]">
                                    Ação
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map((row, idx) => {
                                const codigo = String(row[codigoKey] || "");
                                const status = String(row[statusKey] || "");
                                const isPending = status === "Pendente";
                                const isEditing = editingRow === codigo;

                                return (
                                    <tr
                                        key={idx}
                                        className={`border-b border-gray-50 transition-colors ${isPending ? "bg-warning/5" : "hover:bg-blue-50/30"
                                            }`}
                                    >
                                        <td className="px-4 py-2.5 font-mono text-xs text-gray-600">
                                            {codigo}
                                        </td>
                                        <td className="px-4 py-2.5">{String(row[tituloKey] || "")}</td>
                                        <td className="px-4 py-2.5">
                                            {isEditing ? (
                                                <div className="flex gap-2">
                                                    <input
                                                        list="classifications"
                                                        value={editValue}
                                                        onChange={(e) => setEditValue(e.target.value)}
                                                        className="flex-1 px-2 py-1 text-sm border border-primary-light rounded-md focus:ring-2 focus:ring-primary-light/30 outline-none"
                                                        autoFocus
                                                    />
                                                    <datalist id="classifications">
                                                        {classifications.map((c) => (
                                                            <option key={c} value={c} />
                                                        ))}
                                                    </datalist>
                                                </div>
                                            ) : (
                                                <span className={isPending ? "text-warning font-medium" : ""}>
                                                    {String(row[classificacaoKey] || "—")}
                                                </span>
                                            )}
                                        </td>
                                        {grupoKey && (
                                            <td className="px-4 py-2.5">
                                                <span className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary font-medium">
                                                    {String(row[grupoKey] || "")}
                                                </span>
                                            </td>
                                        )}
                                        {statusKey && (
                                            <td className="px-4 py-2.5 text-center">
                                                <span
                                                    className={`inline-block px-2 py-0.5 text-xs rounded-full font-medium ${isPending
                                                            ? "bg-warning/15 text-warning"
                                                            : "bg-positive/10 text-positive"
                                                        }`}
                                                >
                                                    {status || "—"}
                                                </span>
                                            </td>
                                        )}
                                        <td className="px-4 py-2.5 text-center">
                                            {isEditing ? (
                                                <div className="flex items-center justify-center gap-1">
                                                    <button
                                                        onClick={() => handleSave(codigo)}
                                                        disabled={saving}
                                                        className="p-1 text-positive hover:bg-positive/10 rounded transition-colors"
                                                        title="Salvar"
                                                    >
                                                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                                                            <path d="M4 8l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                                                        </svg>
                                                    </button>
                                                    <button
                                                        onClick={() => setEditingRow(null)}
                                                        className="p-1 text-negative hover:bg-negative/10 rounded transition-colors"
                                                        title="Cancelar"
                                                    >
                                                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                                                            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                                                        </svg>
                                                    </button>
                                                </div>
                                            ) : (
                                                <button
                                                    onClick={() => {
                                                        setEditingRow(codigo);
                                                        setEditValue(String(row[classificacaoKey] || ""));
                                                    }}
                                                    className="p-1 text-gray-text hover:text-primary-light hover:bg-primary-light/10 rounded transition-colors"
                                                    title="Editar"
                                                >
                                                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                                                        <path d="M11.5 2.5l2 2-8 8H3.5v-2l8-8z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                                                    </svg>
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Toast */}
            {toast && (
                <div
                    className={`fixed bottom-6 right-6 px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 z-50 animate-fade-in ${toast.type === "success"
                            ? "bg-positive text-white"
                            : "bg-negative text-white"
                        }`}
                >
                    {toast.type === "success" ? "✓" : "✗"} {toast.message}
                </div>
            )}
        </div>
    );
}
