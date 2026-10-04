import type { ReactNode } from "react";

export const metadata = {
  title: "Wavecell AI",
  description: "SMS Maritime remote travel assistant for smart and feature phones",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}