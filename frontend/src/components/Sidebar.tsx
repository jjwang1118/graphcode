import { useEffect, useState } from 'react';

import type { GraphDocument } from '../api/types';
import { layoutLabels, type LayoutId } from '../graph/layouts';
import { palette } from '../graph/style';
import { viewLabels, type ViewId } from '../graph/views';

interface Props {
  path: string;
  onPathChange: (path: string) => void;
  onAnalyze: () => void;
  loading: boolean;
  view: ViewId;
  onViewChange: (view: ViewId) => void;
  layout: LayoutId;
  onLayoutChange: (layout: LayoutId) => void;
  spacing: number;
  onSpacingChange: (spacing: number) => void;
  graph: GraphDocument | null;
  error: string | null;
}

export function Sidebar({
  path,
  onPathChange,
  onAnalyze,
  loading,
  view,
  onViewChange,
  layout,
  onLayoutChange,
  spacing,
  onSpacingChange,
  graph,
  error,
}: Props) {
  return (
    <aside
      style={{
        width: 260,
        flexShrink: 0,
        background: palette.panel,
        borderRight: `1px solid ${palette.border}`,
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
        overflowY: 'auto',
      }}
    >
      <div style={{ fontSize: 15, letterSpacing: 2, color: palette.directory }}>
        CODEGRAPH
      </div>

      <Section title="專案路徑">
        <input
          value={path}
          onChange={(event) => onPathChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !loading) onAnalyze();
          }}
          placeholder="/home/you/project"
          style={field}
        />
        <button
          onClick={onAnalyze}
          disabled={loading || !path}
          style={{
            ...field,
            marginTop: 8,
            cursor: loading || !path ? 'default' : 'pointer',
            background: loading || !path ? palette.border : palette.directory,
            color: loading || !path ? palette.textDim : '#04121a',
            borderColor: 'transparent',
          }}
        >
          {loading ? '分析中…' : '分析'}
        </button>
        {error && (
          <div style={{ marginTop: 8, fontSize: 12, color: '#ff8a8a' }}>{error}</div>
        )}
      </Section>

      <Section title="視圖">
        <select
          value={view}
          onChange={(event) => onViewChange(event.target.value as ViewId)}
          style={field}
        >
          {Object.entries(viewLabels).map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
        <div style={{ ...caption, marginTop: 6, lineHeight: 1.4 }}>
          切視圖＝換一個查詢條件，會重新向後端要一次
        </div>
      </Section>

      <Section title="排版">
        <select
          value={layout}
          onChange={(event) => onLayoutChange(event.target.value as LayoutId)}
          style={field}
        >
          {Object.entries(layoutLabels).map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>

        <SpacingSlider value={spacing} onCommit={onSpacingChange} />
      </Section>

      <Section title="圖例">
        <Legend color={palette.repo} shape="hexagon" label="repo" />
        <Legend color={palette.directory} shape="square" label="directory" />
        <Legend color={palette.file} shape="circle" label="file" />
        <Legend color={palette.external} shape="diamond" label="external package" />
        <div style={{ ...caption, marginTop: 8, lineHeight: 1.5 }}>
          細暗線＝contains（骨架）
          <br />
          粗亮線＝imports（依賴）
          <br />
          線上的數字＝同一對之間有幾筆
        </div>
      </Section>

      {graph && (
        <Section title="統計">
          <Row label="節點" value={graph.meta.node_count} />
          <Row label="邊" value={graph.meta.edge_count} />
          <Row label="循環" value={graph.meta.cycles.length} />
          {/* 只在不是 0 的時候顯示：平常沒事就不該佔版面，出事一定要看得到 */}
          {graph.meta.parse_failures > 0 && (
            <Row label="解析失敗" value={graph.meta.parse_failures} warn />
          )}
          {graph.meta.ambiguous_imports > 0 && (
            <Row label="來源不確定" value={graph.meta.ambiguous_imports} warn />
          )}
          {graph.meta.unresolved_imports > 0 && (
            <Row label="接不到目標" value={graph.meta.unresolved_imports} warn />
          )}
        </Section>
      )}
    </aside>
  );
}

const field: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: '7px 9px',
  background: palette.background,
  border: `1px solid ${palette.border}`,
  borderRadius: 4,
  color: palette.text,
  fontFamily: 'inherit',
  fontSize: 13,
};

const caption: React.CSSProperties = {
  fontSize: 11,
  letterSpacing: 1,
  color: palette.textDim,
};

// 間距只是幾何縮放、不重跑排版，所以可以邊拖邊套用。
function SpacingSlider({
  value,
  onCommit,
}: {
  value: number;
  onCommit: (value: number) => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);

  return (
    <>
      <label style={{ ...caption, display: 'block', marginTop: 12 }}>
        節點間距 {draft.toFixed(1)}
      </label>
      <input
        type="range"
        min={0.8}
        max={5}
        step={0.1}
        value={draft}
        onChange={(event) => {
          const next = Number(event.target.value);
          setDraft(next);
          onCommit(next);
        }}
        style={{ width: '100%', accentColor: palette.directory }}
      />
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <div style={{ ...caption, marginBottom: 8 }}>{title.toUpperCase()}</div>
      {children}
    </section>
  );
}

function Legend({
  color,
  shape,
  label,
}: {
  color: string;
  shape: 'hexagon' | 'square' | 'circle' | 'diamond';
  label: string;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 12,
        color: palette.text,
        marginBottom: 6,
      }}
    >
      <span
        style={{
          width: shape === 'hexagon' ? 14 : 11,
          height: shape === 'hexagon' ? 14 : 11,
          background: color,
          borderRadius: shape === 'circle' ? '50%' : shape === 'square' ? 3 : 0,
          clipPath: CLIP[shape],
        }}
      />
      {label}
    </div>
  );
}

const CLIP: Record<string, string | undefined> = {
  hexagon: 'polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)',
  diamond: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)',
};

function Row({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 12,
        color: warn ? palette.danger : palette.text,
        marginBottom: 4,
      }}
    >
      <span style={{ color: palette.textDim }}>{label}</span>
      <span>{value}</span>
    </div>
  );
}
