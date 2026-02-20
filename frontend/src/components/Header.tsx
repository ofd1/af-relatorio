"use client";

interface HeaderProps {
    companyName: string;
    period: string;
}

export default function Header({ companyName, period }: HeaderProps) {
    return (
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 sticky top-0 z-40">
            <div>
                <h1 className="text-lg font-semibold text-primary">{companyName}</h1>
                <p className="text-xs text-gray-text -mt-0.5">{period}</p>
            </div>
            <div className="flex items-center gap-3">
                <button
                    onClick={() => {
                        document.cookie = "af_session=; max-age=0; path=/";
                        window.location.href = "/";
                    }}
                    className="text-sm text-gray-text hover:text-negative transition-colors flex items-center gap-1.5"
                >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M6 2H4a2 2 0 00-2 2v8a2 2 0 002 2h2M11 11l3-3m0 0l-3-3m3 3H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Sair
                </button>
            </div>
        </header>
    );
}
