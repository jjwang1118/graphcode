import { useEffect, useState } from 'react';

import type { ExternalMode, GraphDocument } from '../api/types';
import { layoutLabels, type LayoutId } from '../graph/layouts';
import {
  externalLabels,
  levelFromKey,
  levelKey,
  levels,
} from '../graph/levels';
import { palette } from '../graph/style';
import { viewLabels, type ViewId } from '../graph/views';

interface Props {
  path: string;
  onPathChange: (path: string) => void;
  onAnalyze: () => void;
  loading: boolean;
  level: number | null;
  onLevelChange: (level: number | null) => void;
  externals: ExternalMode;
  onExternalsChange: (externals: ExternalMode) => void;
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
  level,
  onLevelChange,
  externals,
  onExternalsChange,
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

      <Section title="層級">
        <select
          value={levelKey(level)}
          onChange={(event) => onLevelChange(levelFromKey(event.target.value))}
          style={field}
        >
          {levels.map((option) => (
            <option key={levelKey(option.value)} value={levelKey(option.value)}>
              {option.label}
            </option>
          ))}
        </select>

        <label style={{ ...caption, display: 'block', marginTop: 12 }}>外部套件</label>
        <select
          value={externals}
          onChange={(event) => onExternalsChange(event.target.value as ExternalMode)}
          style={{ ...field, marginTop: 4 }}
        >
          {Object.entries(externalLabels).map(([mode, label]) => (
            <option key={mode} value={mode}>
              {label}
            </option>
          ))}
        </select>

        <div style={{ ...caption, marginTop: 8, lineHeight: 1.4 }}>
          收合在後端做，換層級會重新向後端要一次
        </div>
      </Section>

      {/* 視圖切換（全部／目錄樹／依賴圖）先停用：收合之後 contains 表現成「你在
          哪一層」，那個軸自然消失。程式碼留著，要回頭把 SHOW_VIEWS 打開即可。 */}
      {SHOW_VIEWS && (
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
        </Section>
      )}

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

        <div
          style={{
            marginTop: 12,
            paddingTop: 12,
            borderTop: `1px solid ${palette.border}`,
            display: 'flex',
            flexDirection: 'column',
            gap: 9,
          }}
        >
          <LineLegend color={palette.edge} thickness={2} label="contains" note="骨架" />
          <LineLegend
            color={palette.edgeImports}
            thickness={3.5}
            label="imports"
            note="依賴"
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <span
              style={{
                width: 30,
                textAlign: 'center',
                fontSize: 12,
                color: palette.text,
                background: palette.background,
                border: `1px solid ${palette.border}`,
                borderRadius: 3,
                padding: '1px 0',
              }}
            >
              5
            </span>
            <span style={{ fontSize: 12.5, color: palette.text }}>
              同一對之間有幾筆
            </span>
          </div>
        </div>
      </Section>

      {graph && (
        <Section title="統計">
          <div style={{ display: 'flex', gap: 18, marginBottom: 10 }}>
            <Stat label="節點" value={graph.meta.node_count} />
            <Stat label="邊" value={graph.meta.edge_count} />
            <Stat label="循環" value={graph.meta.cycles.length} />
          </div>
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

//: 視圖切換暫時停用，見上方註解。改成 true 就回到收合方案之前的樣子。
const SHOW_VIEWS = false;

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
        gap: 9,
        fontSize: 12.5,
        color: palette.text,
        marginBottom: 7,
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

// 兩種邊在畫面上長什麼樣，圖例就畫成什麼樣——用文字描述「細暗線」很難對得起來。
function LineLegend({
  color,
  thickness,
  label,
  note,
}: {
  color: string;
  thickness: number;
  label: string;
  note: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
      <span
        style={{
          width: 30,
          height: thickness,
          background: color,
          borderRadius: thickness,
          flexShrink: 0,
        }}
      />
      <span style={{ fontSize: 12.5, color: palette.text }}>
        {label}
        <span style={{ color: palette.textDim, marginLeft: 8 }}>{note}</span>
      </span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div style={{ fontSize: 20, color: palette.text, lineHeight: 1.1 }}>{value}</div>
      <div style={{ ...caption, marginTop: 2 }}>{label}</div>
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
