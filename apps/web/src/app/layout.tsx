import type { Metadata } from "next";
import { JetBrains_Mono, Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { Providers } from "@/components/providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Learning Task Tracker",
  description: "Project-based learning workspace with AI guidance",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased min-h-screen`}
      >
        <Providers>{children}</Providers>
        {process.env.NEXT_PUBLIC_DEBUG === "true" && (
          <Link
            href="/debug"
            className="fixed bottom-4 right-4 z-50 bg-yellow-500 hover:bg-yellow-400 text-black text-xs font-bold px-3 py-2 rounded-full shadow-lg"
          >
            🔍 Debug
          </Link>
        )}
      </body>
    </html>
  );
}
