"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import api from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface ProcessingResult {
    periodo?: string;
    linhas_importadas?: number;
    novas_contas?: any[];
    validacoes?: Record<string, any>;
    warnings?: string[];
    message?: string;
}

export default function UploadPage() {
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [result, setResult] = useState<ProcessingResult | null>(null);
    const [error, setError] = useState("");

    const onDrop = useCallback((accepted: File[]) => {
        if (accepted.length > 0) {
            setFile(accepted[0]);
            setResult(null);
            setError("");
        }
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "application/vnd.ms-excel": [".xls"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
        },
        maxFiles: 1,
    });

    const handleUpload = async () => {
        if (!file) return;
        setUploading(true);
        setProgress(0);
        setError("");
        setResult(null);

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await api.post("/api/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" },
                onUploadProgress: (e) => {
                    if (e.total) {
                        setProgress(Math.round((e.loaded / e.total) * 100));
                    }
                },
            });
            setResult(res.data);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Erro ao processar arquivo.");
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto space-y-6">
            <h2 className="text-xl font-bold text-primary">Upload de Balancete</h2>

            {/* Dropzone */}
            <div
                {...getRootProps()}
                className={`card card-hover p-10 text-center cursor-pointer transition-all border-2 border-dashed ${isDragActive
                        ? "border-primary-light bg-primary-light/5"
                        : file
                            ? "border-positive/40 bg-positive/5"
                            : "border-gray-300 hover:border-primary-light/50"
                    }`}
            >
                <input {...getInputProps()} />
                <div className="flex flex-col items-center gap-3">
                    {file ? (
                        <>
                            <div className="w-14 h-14 rounded-2xl bg-positive/10 flex items-center justify-center">
                                <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                                    <path d="M9 12l2 2 4-4" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                    <circle cx="12" cy="12" r="9" stroke="#10b981" strokeWidth="2" />
                                </svg>
                            </div>
                            <div>
                                <p className="text-sm font-medium text-foreground">{file.name}</p>
                                <p className="text-xs text-gray-text mt-1">
                                    {(file.size / 1024).toFixed(0)} KB • Clique ou arraste para trocar
                                </p>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="w-14 h-14 rounded-2xl bg-primary-light/10 flex items-center justify-center">
                                <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                                    <path d="M12 5v10M8 9l4-4 4 4" stroke="#4a90d9" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                    <path d="M4 15v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="#4a90d9" strokeWidth="2" strokeLinecap="round" />
                                </svg>
                            </div>
                            <div>
                                <p className="text-sm font-medium text-foreground">
                                    {isDragActive ? "Solte o arquivo aqui" : "Arraste ou clique para selecionar"}
                                </p>
                                <p className="text-xs text-gray-text mt-1">
                                    Arquivos .xls ou .xlsx (balancete Hinova)
                                </p>
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* Upload button */}
            {file && !result && (
                <button
                    onClick={handleUpload}
                    disabled={uploading}
                    className="w-full py-3 bg-primary-light hover:bg-primary-light/90 disabled:opacity-50 text-white font-medium rounded-xl transition-all flex items-center justify-center gap-2"
                >
                    {uploading ? (
                        <>
                            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            Processando...
                        </>
                    ) : (
                        "Enviar e Processar"
                    )}
                </button>
            )}

            {/* Progress bar */}
            {uploading && (
                <div className="card p-4">
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-gray-text">Progresso</span>
                        <span className="text-xs font-semibold text-primary">{progress}%</span>
                    </div>
                    <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-primary-light to-primary rounded-full transition-all duration-300"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="card p-4 border-l-4 border-negative bg-negative/5">
                    <div className="flex items-start gap-2">
                        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="flex-shrink-0 mt-0.5">
                            <circle cx="9" cy="9" r="7" stroke="#ef4444" strokeWidth="1.5" />
                            <path d="M9 6v3.5M9 11.5h.01" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                        <p className="text-sm text-negative">{error}</p>
                    </div>
                </div>
            )}

            {/* Result summary */}
            {result && (
                <div className="card overflow-hidden">
                    <div className="px-5 py-4 bg-positive/5 border-b border-positive/10">
                        <div className="flex items-center gap-2">
                            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                                <circle cx="10" cy="10" r="8" stroke="#10b981" strokeWidth="1.5" />
                                <path d="M7 10l2 2 4-4" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" />
                            </svg>
                            <h3 className="text-sm font-semibold text-positive">Processamento Concluído</h3>
                        </div>
                    </div>

                    <div className="p-5 space-y-4">
                        {result.message && (
                            <p className="text-sm text-foreground">{result.message}</p>
                        )}

                        <div className="grid grid-cols-2 gap-3">
                            {result.periodo && (
                                <div className="bg-secondary rounded-lg px-4 py-3">
                                    <p className="text-xs text-gray-text">Período</p>
                                    <p className="text-sm font-semibold mt-0.5">{result.periodo}</p>
                                </div>
                            )}
                            {result.linhas_importadas !== undefined && (
                                <div className="bg-secondary rounded-lg px-4 py-3">
                                    <p className="text-xs text-gray-text">Linhas importadas</p>
                                    <p className="text-sm font-semibold mt-0.5">{result.linhas_importadas}</p>
                                </div>
                            )}
                        </div>

                        {/* New accounts */}
                        {result.novas_contas && result.novas_contas.length > 0 && (
                            <div>
                                <h4 className="text-xs font-semibold text-gray-text uppercase tracking-wider mb-2">
                                    Novas Contas ({result.novas_contas.length})
                                </h4>
                                <div className="space-y-1">
                                    {result.novas_contas.map((conta, i) => (
                                        <div
                                            key={i}
                                            className="flex items-center justify-between px-3 py-2 text-sm bg-warning/5 rounded-lg border border-warning/15"
                                        >
                                            <span>{conta.titulo || conta.codigo || JSON.stringify(conta)}</span>
                                            <span className="text-xs text-warning font-medium">
                                                {conta.status || "Pendente"}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Validations */}
                        {result.validacoes && (
                            <div>
                                <h4 className="text-xs font-semibold text-gray-text uppercase tracking-wider mb-2">
                                    Validações
                                </h4>
                                <div className="space-y-1">
                                    {Object.entries(result.validacoes).map(([key, val]) => (
                                        <div
                                            key={key}
                                            className="flex items-center justify-between px-3 py-2 text-sm bg-secondary rounded-lg"
                                        >
                                            <span className="text-gray-700">{key}</span>
                                            <span className={`text-xs font-medium ${val ? "text-positive" : "text-negative"}`}>
                                                {val ? "✓ OK" : "✗ Falhou"}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Warnings */}
                        {result.warnings && result.warnings.length > 0 && (
                            <div>
                                <h4 className="text-xs font-semibold text-gray-text uppercase tracking-wider mb-2">
                                    Avisos ({result.warnings.length})
                                </h4>
                                <div className="space-y-1">
                                    {result.warnings.map((w, i) => (
                                        <div
                                            key={i}
                                            className="flex items-start gap-2 px-3 py-2 text-sm bg-warning/5 rounded-lg border border-warning/15"
                                        >
                                            <span className="text-warning mt-0.5">⚠</span>
                                            <span className="text-gray-700">{w}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Upload another */}
                        <button
                            onClick={() => {
                                setFile(null);
                                setResult(null);
                            }}
                            className="text-sm text-primary-light hover:underline"
                        >
                            ← Enviar outro arquivo
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
