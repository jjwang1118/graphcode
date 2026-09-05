import { useEffect, useState } from 'react';

import { analyze } from './api/client';
import type { GraphDocument } from './api/types';
import { GraphCanvas } from './components/GraphCanvas';
import { Sidebar } from './components/Sidebar';
import type { LayoutId } from './graph/layouts';
import { layoutFor } from './graph/levels';
import { palette } from './graph/style';
import { viewEdgeTypes, type ViewId } from './graph/views';
import type { ExternalMode } from './api/types';

/** 一次查詢的條件。全部都是後端的參數，前端只是收集它們。 */
interface Query {
  view: ViewId;
  level: number | null;
  externals: ExternalMode;
}

export default function App() {
  const [path, setPath] = useState('');
  const [graph, setGraph] = useState<GraphDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [level, setLevel] = useState<number | null>(3);
  const [externals, setExternals] = useState<ExternalMode>('grouped');
  const [view, setView] = useState<ViewId>('all');
  const [layout, setLayout] = useState<LayoutId>(layoutFor(3));
  const [spacing, setSpacing] = useState(2.2);
  const [query, setQuery] = useState('');
  // 已經分析過的路徑。換層級要重打一次，得知道上次打的是哪個路徑。
  const [analyzed, setAnalyzed] = useState<string | null>(null);

  async function run(target: string, request: Query) {
    setLoading(true);
    setError(null);
    try {
      setGraph(
        await analyze({
          path: target,
          edge_types: viewEdgeTypes[request.view],
          level: request.level,
          externals: request.externals,
        }),
      );
      setAnalyzed(target);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '分析失敗');
      setGraph(null);
      setAnalyzed(null);
    } finally {
      setLoading(false);
    }
  }

  // 換層級／視圖＝換一個請求參數，不是換元件。收合與篩選都由後端做，前端不碰
  // 圖的運算。
  useEffect(() => {
    if (analyzed) void run(analyzed, { view, level, externals });
    // 只認這三個：path 改了要按分析鈕，不該邊打字邊送請求。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, level, externals]);

  function changeLevel(next: number | null) {
    setLevel(next);
    // 排版跟著層級走：檔案層是樹狀好排，收合過的有環。之後仍可手動改。
    setLayout(layoutFor(next));
  }

  return (
    <div style={{ display: 'flex', height: '100%', background: palette.background }}>
      <Sidebar
        path={path}
        onPathChange={setPath}
        onAnalyze={() => void run(path, { view, level, externals })}
        loading={loading}
        level={level}
        onLevelChange={changeLevel}
        externals={externals}
        onExternalsChange={setExternals}
        view={view}
        onViewChange={setView}
        layout={layout}
        onLayoutChange={setLayout}
        spacing={spacing}
        onSpacingChange={setSpacing}
        graph={graph}
        error={error}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header
          style={{
            padding: 10,
            borderBottom: `1px solid ${palette.border}`,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜尋節點名稱⋯⋯符合的會發亮，其餘變暗"
            style={{
              flex: 1,
              boxSizing: 'border-box',
              padding: '8px 12px',
              background: palette.panel,
              border: `1px solid ${palette.border}`,
              borderRadius: 20,
              color: palette.text,
              fontFamily: 'inherit',
              fontSize: 13,
            }}
          />
          {query && (
            <span style={{ fontSize: 12, color: palette.textDim }}>
              Esc 或清空即可還原
            </span>
          )}
        </header>

        <main style={{ flex: 1, minHeight: 0 }}>
          <GraphCanvas graph={graph} layout={layout} spacing={spacing} query={query} />
        </main>
      </div>
    </div>
  );
}
