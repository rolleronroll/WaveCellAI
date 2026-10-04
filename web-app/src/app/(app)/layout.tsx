// Main app root layout

import "./globals.css";
import type { ReactNode } from "react";
import Nav from "@/components/Nav";

// export default function AppLayout({ children }: { children: ReactNode }) {
//   return <>{children}</>;
// }


export const metadata = { title: "WaveCellAI SMS" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}
