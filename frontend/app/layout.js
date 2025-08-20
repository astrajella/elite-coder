"use client";
import './globals.css'
export const metadata = { title: 'AI Code Agent' }
export default function RootLayout({ children }) {
  return (<html lang="en"><body>{children}
<div id="toast" className="fixed bottom-4 right-4 z-50 hidden bg-slate-800 text-white text-sm px-3 py-2 rounded-lg shadow-lg border border-slate-700"></div>
</body></html>);
}
