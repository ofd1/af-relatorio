"use client";

import { useState, useEffect, ReactNode } from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import api from "@/lib/api";

export default function DashboardLayout({ children }: { children: ReactNode }) {
    const [companyName, setCompanyName] = useState("Empresa");
    const [periods, setPeriods] = useState<string[]>([]);
    const [sidebarExpanded, setSidebarExpanded] = useState(true);

    useEffect(() => {
        async function fetchSummary() {
            try {
                const res = await api.get("/api/data/summary");
                setCompanyName(res.data.empresa || "Empresa Padrão");
                setPeriods(res.data.periods || []);
            } catch {
                // Fallback values remain
            }
        }
        fetchSummary();

        const handleToggle = () => setSidebarExpanded((prev) => !prev);
        window.addEventListener("sidebar-toggle", handleToggle);
        return () => window.removeEventListener("sidebar-toggle", handleToggle);
    }, []);

    const periodLabel =
        periods.length > 0
            ? `${periods[0]} — ${periods[periods.length - 1]}`
            : "Carregando...";

    return (
        <div className="flex min-h-screen">
            <Sidebar companyName={companyName} />
            <div
                className={`flex-1 flex flex-col transition-all duration-300 ${sidebarExpanded ? "ml-[240px]" : "ml-[60px]"
                    }`}
            >
                <Header companyName={companyName} period={periodLabel} />
                <main className="flex-1 p-6">{children}</main>
            </div>
        </div>
    );
}
