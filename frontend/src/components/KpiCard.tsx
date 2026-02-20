import { ReactNode } from "react";

interface KpiCardProps {
    title: string;
    value: string;
    variation?: string;
    variationType?: "positive" | "negative" | "neutral";
    icon: ReactNode;
}

export default function KpiCard({
    title,
    value,
    variation,
    variationType = "neutral",
    icon,
}: KpiCardProps) {
    const variationColor =
        variationType === "positive"
            ? "text-positive bg-positive/10"
            : variationType === "negative"
                ? "text-negative bg-negative/10"
                : "text-gray-text bg-gray-100";

    return (
        <div className="card card-hover p-5">
            <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-text font-medium">{title}</p>
                    <p className="text-2xl font-bold text-primary mt-1 tracking-tight">
                        {value}
                    </p>
                    {variation && (
                        <span
                            className={`inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full text-xs font-medium ${variationColor}`}
                        >
                            {variationType === "positive" && "▲"}
                            {variationType === "negative" && "▼"}
                            {variation}
                        </span>
                    )}
                </div>
                <div className="w-10 h-10 rounded-xl bg-primary-light/10 flex items-center justify-center text-primary-light flex-shrink-0">
                    {icon}
                </div>
            </div>
        </div>
    );
}
