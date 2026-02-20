"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.post("/api/login", { password });
      router.push("/dashboard");
    } catch (err: unknown) {
      if (
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { status?: number } }).response?.status === 401
      ) {
        setError("Senha incorreta.");
      } else {
        setError("Erro ao conectar ao servidor.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary via-primary-dark to-[#0f2640] relative overflow-hidden">
      {/* Decorative circles */}
      <div className="absolute top-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-primary-light/8 blur-3xl" />
      <div className="absolute bottom-[-15%] left-[-10%] w-[400px] h-[400px] rounded-full bg-primary-light/5 blur-3xl" />

      <div className="w-full max-w-sm px-6 relative z-10">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white/10 backdrop-blur-sm mb-4 border border-white/10">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <path d="M8 24V12l8-8 8 8v12H8z" fill="#4a90d9" fillOpacity="0.3" stroke="white" strokeWidth="1.5" />
              <path d="M13 24v-6h6v6" stroke="white" strokeWidth="1.5" />
              <rect x="12" y="14" width="3" height="3" rx="0.5" fill="white" fillOpacity="0.6" />
              <rect x="17" y="14" width="3" height="3" rx="0.5" fill="white" fillOpacity="0.6" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            AF <span className="text-primary-light">Relatório</span>
          </h1>
          <p className="text-sm text-white/50 mt-1">Automação Financeira</p>
        </div>

        {/* Login form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Digite a senha"
              autoFocus
              className="w-full px-4 py-3 bg-white/10 backdrop-blur-sm border border-white/15 rounded-xl text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-primary-light/50 focus:border-transparent transition-all text-sm"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-negative/15 border border-negative/20">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="6.5" stroke="#ef4444" strokeWidth="1.5" />
                <path d="M8 5v3M8 10h.01" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <p className="text-xs text-negative">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !password}
            className="w-full py-3 bg-primary-light hover:bg-primary-light/90 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-xl transition-all text-sm flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Entrando...
              </>
            ) : (
              "Entrar"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
