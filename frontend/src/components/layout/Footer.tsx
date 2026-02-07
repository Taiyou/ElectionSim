export default function Footer() {
  return (
    <footer className="bg-gray-100 dark:bg-gray-900 border-t mt-12">
      <div className="max-w-7xl mx-auto px-4 py-6 text-center text-sm text-gray-500">
        <p>衆議院選挙AI予測システム</p>
        <p className="mt-1">
          Perplexity + Grok + Claude による複数AI統合分析
        </p>
        <p className="mt-1 text-xs">
          ※ 本サイトの予測はAIによる推定であり、実際の選挙結果を保証するものではありません
        </p>
      </div>
    </footer>
  );
}
