import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import "./globals.css"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "CrisisMonitor",
  description: "Monitor crisis one tweet at a time",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased flex flex-col items-center p-6`}
      >
        {/* Navigation Bar */}
        <nav className="flex items-center justify-between w-full max-w-3xl mb-4">
          <h1 className="text-3xl font-bold">CrisisMonitor</h1>
        </nav>

        {/* Page Content */}
        <main className="w-full max-w-3xl">{children}</main>
      </body>
    </html>
  )
}
