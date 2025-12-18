import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/contexts/auth-context";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_APP_URL || "https://thoth.dynastyedge.com"
  ),
  title: "Thoth | AI-Powered Dynasty Fantasy Analytics",
  description:
    "The most sophisticated dynasty fantasy football analytics platform. Machine learning projections, real-time KTC valuations, and AI-powered insights. Built for champions.",
  keywords: [
    "dynasty fantasy football",
    "KTC values",
    "trade analyzer",
    "fantasy football AI",
    "dynasty rankings",
    "ML projections",
    "Thoth analytics",
  ],
  authors: [{ name: "Thoth Analytics" }],
  creator: "Thoth Analytics",
  openGraph: {
    title: "Thoth | AI-Powered Dynasty Fantasy Analytics",
    description:
      "The most sophisticated dynasty fantasy football analytics platform. Machine learning projections and AI-powered insights.",
    type: "website",
    siteName: "Thoth",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Thoth - Dynasty Fantasy Analytics",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Thoth | AI-Powered Dynasty Fantasy Analytics",
    description:
      "The most sophisticated dynasty fantasy football analytics platform.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#D4AF37",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
      </head>
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
