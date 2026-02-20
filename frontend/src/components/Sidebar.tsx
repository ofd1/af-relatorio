"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
    {
        href: "/dashboard",
        label: "Dashboard",
        icon: (
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <rect x="2" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
                <rect x="11" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
                <rect x="2" y="11" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
                <rect x="11" y="11" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
            </svg>
        ),
    },
    {
        href: "/upload",
        label: "Upload",
        icon: (
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M10 3v10M6 7l4-4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M3 13v2a2 2 0 002 2h10a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
        ),
    },
    {
        href: "/depara",
        label: "DEPARA",
        icon: (
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M3 5h14M3 10h14M3 15h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
        ),
    },
    {
        href: "/export",
        label: "Exportar",
        icon: (
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M10 13V3M6 9l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M3 13v2a2 2 0 002 2h10a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
        ),
    },
];

interface SidebarProps {
    companyName: string;
}

export default function Sidebar({ companyName }: SidebarProps) {
    const [expanded, setExpanded] = useState(true);
    const pathname = usePathname();

    return (
        <aside
            className={`fixed top-0 left-0 h-screen bg-primary text-white flex flex-col z-50 transition-all duration-300 ${expanded ? "w-[240px]" : "w-[60px]"
                }`}
        >
            {/* Logo + Toggle */}
            <div className="flex items-center h-16 px-4 border-b border-white/10">
                {expanded && (
                    <span className="text-lg font-bold tracking-tight whitespace-nowrap">
                        AF<span className="text-primary-light"> Relatório</span>
                    </span>
                )}
                <button
                    onClick={() => setExpanded(!expanded)}
                    className={`p-1.5 rounded-lg hover:bg-white/10 transition-colors ${expanded ? "ml-auto" : "mx-auto"
                        }`}
                    title={expanded ? "Recolher menu" : "Expandir menu"}
                >
                    <svg
                        width="18"
                        height="18"
                        viewBox="0 0 18 18"
                        fill="none"
                        className={`transition-transform duration-300 ${expanded ? "" : "rotate-180"}`}
                    >
                        <path d="M11 4L6 9l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </button>
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-4 flex flex-col gap-1 px-2">
                {NAV_ITEMS.map((item) => {
                    const active = pathname === item.href || pathname.startsWith(item.href + "/");
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group ${active
                                    ? "bg-white/15 text-white font-medium"
                                    : "text-white/70 hover:bg-white/8 hover:text-white"
                                }`}
                            title={item.label}
                        >
                            <span className="flex-shrink-0">{item.icon}</span>
                            {expanded && (
                                <span className="text-sm whitespace-nowrap">{item.label}</span>
                            )}
                            {active && !expanded && (
                                <span className="absolute left-0 w-[3px] h-6 bg-primary-light rounded-r" />
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Company selector at bottom */}
            <div className="px-3 py-4 border-t border-white/10">
                {expanded ? (
                    <div className="flex items-center gap-2 px-2 py-2 rounded-lg bg-white/8 cursor-pointer hover:bg-white/12 transition-colors">
                        <div className="w-7 h-7 rounded-full bg-primary-light flex items-center justify-center text-xs font-bold flex-shrink-0">
                            {companyName.charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                            <p className="text-xs font-medium truncate">{companyName}</p>
                            <p className="text-[10px] text-white/50">Empresa ativa</p>
                        </div>
                    </div>
                ) : (
                    <div
                        className="w-8 h-8 mx-auto rounded-full bg-primary-light flex items-center justify-center text-xs font-bold cursor-pointer"
                        title={companyName}
                    >
                        {companyName.charAt(0).toUpperCase()}
                    </div>
                )}
            </div>
        </aside>
    );
}
