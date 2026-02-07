import Link from "next/link";

export default function Header() {
  return (
    <header className="bg-gray-900 text-white">
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold">
          衆議院選挙 AI予測
        </Link>
        <nav className="flex gap-4 text-sm flex-wrap">
          <Link href="/" className="hover:text-blue-300 transition">
            ダッシュボード
          </Link>
          <Link href="/youtube" className="hover:text-red-300 transition">
            YouTube分析
          </Link>
          <Link href="/news" className="hover:text-indigo-300 transition">
            ニュース分析
          </Link>
          <Link href="/models" className="hover:text-green-300 transition">
            モデル比較
          </Link>
          <Link href="/battleground" className="hover:text-blue-300 transition">
            接戦区
          </Link>
          <Link href="/proportional" className="hover:text-blue-300 transition">
            比例代表
          </Link>
          <Link href="/how-it-works" className="hover:text-blue-300 transition">
            仕組み
          </Link>
        </nav>
      </div>
    </header>
  );
}
