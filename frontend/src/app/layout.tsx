import type { Metadata } from "next";
import "./globals.css";
import AppLayout from "@/components/AppLayout";
import { BackendProvider } from "@/components/BackendContext";

export const metadata: Metadata = {
  title: "CareerFlow AI - Intelligent Career Assistant",
  description: "AI-Powered Job Discovery, CV Optimization, Auto-Application, and Interview Prep System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <BackendProvider>
          <AppLayout>{children}</AppLayout>
        </BackendProvider>
      </body>
    </html>
  );
}
