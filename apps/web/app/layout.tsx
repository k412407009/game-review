import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "game-review · 5 评委 × 7 维度评审",
  description:
    "对外部已上线游戏 (商店页 + gameplay 视频) 或内部立项 PPT 做结构化评审, 产出 Word + Excel + Markdown 三件套",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="min-h-dvh flex flex-col">
          <header className="border-b border-ink-700 bg-ink-900/80 backdrop-blur sticky top-0 z-10">
            <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
              <Link href="/" className="flex items-center gap-2 font-semibold">
                <span className="inline-block w-2 h-2 bg-accent-400 rounded-full"></span>
                <span>game-review</span>
                <span className="text-xs text-ink-400 font-normal">
                  · Phase 3 MVP
                </span>
              </Link>
              <nav className="flex items-center gap-4 text-sm text-ink-300">
                <Link href="/" className="hover:text-white">
                  提交评审
                </Link>
                <Link href="/jobs" className="hover:text-white">
                  历史记录
                </Link>
                <a
                  href="https://github.com/k412407009/game-review"
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-white"
                >
                  GitHub
                </a>
              </nav>
            </div>
          </header>
          <main className="flex-1 max-w-5xl w-full mx-auto px-6 py-8">
            {children}
          </main>
          <footer className="border-t border-ink-700 text-sm text-ink-400">
            <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
              <span>5 评委 × 7 维度</span>
              <span>
                API: <code className="font-mono text-ink-300">localhost:8787</code>
              </span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
