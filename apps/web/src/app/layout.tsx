import type { Metadata } from "next";
import { productName } from "@/lib/product";
import "./globals.css";

export const metadata: Metadata = {
  title: productName,
  description: "Contributor, presenter, and admin workspace for software ecosystem updates.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
