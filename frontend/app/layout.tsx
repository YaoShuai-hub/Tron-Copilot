import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { TronProvider } from "@/components/TronProvider";
import { NetworkProvider } from "@/contexts/NetworkContext";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
    title: "TRON Asset Management Copilot",
    description: "AI-powered blockchain assistant for TRON ecosystem",
    viewport: "width=device-width, initial-scale=1, maximum-scale=1",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" className="dark">
            <body className={inter.className}>
                <TronProvider>
                    <NetworkProvider>
                        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
                            {children}
                        </div>
                    </NetworkProvider>
                </TronProvider>
            </body>
        </html>
    );
}
