import type { Metadata, Viewport } from "next";
import { Manrope } from "next/font/google";

import { ToastProvider } from "@/components/ui/toast";
import { AuthProvider } from "@/components/providers/auth-provider";

import "./globals.css";

/**
 * One family for the entire product.
 *
 * Manrope covers display, UI, body and numerals: 800 gives confident page
 * headings, 600–700 carries navigation and section titles, and its tabular
 * figures keep metrics aligned in stat cards and tables. Loading a single
 * family also removes two font requests from the critical path.
 */
const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: {
    default: "TEL Education Link — Student Portal",
    template: "%s · TEL Student Portal",
  },
  description:
    "The student portal for TEL Education Link: timetable, attendance, results, papers, practice and announcements in one place.",
  applicationName: "TEL Student Portal",
  robots: { index: false, follow: false },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#f4f7f9",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={manrope.variable}>
      <body className="min-h-dvh antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[70] focus:rounded-control focus:bg-surface focus:px-4 focus:py-2 focus:shadow-overlay"
        >
          Skip to main content
        </a>
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
