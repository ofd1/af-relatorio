import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AF Relatório — Automação Financeira",
  description:
    "Sistema de automação de relatórios financeiros: DRE, BP, DFC, indicadores e exportações.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased">{children}</body>
    </html>
  );
}
