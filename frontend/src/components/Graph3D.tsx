// 3D 畫布（實驗）。分支 experiment/3d，不在 main 上。
//
// 換掉的只有「畫布」這一層——`transform.ts` 刻意不 import cytoscape，所以同一份
// elements 兩種畫布都吃得下；`api/`、`Sidebar`、`App` 與整個後端都不用動。
//
// 跟 Cytoscape 版一樣：**實例放 ref，不放 state**。放 state 會讓 React 重新渲染
// 整個場景，鏡頭角度與位置全部消失。

import ForceGraph3D, { type ForceGraph3DInstance } from '3d-force-graph';
import { useEffect, useRef, useState } from 'react';
import SpriteText from 'three-spritetext';

import type { GraphDocument, NodeType } from '../api/types';
import { palette } from '../graph/style';
import { toElements } from '../graph/transform';

interface Props {
  graph: GraphDocument | null;
  /** 節點間距。3D 版本改的是力導向的理想邊長，不是事後縮放座標。 */
  spacing: number;
}

// 型別決定顏色與大小，跟 2D 版同一套編碼標準（style.ts 的 palette）。
const SIZE: Record<NodeType, number> = {
  repo: 9,
  directory: 6,
  file: 3.5,
  external_package: 4.5,
  module: 3.5,
  class: 3.5,
  function: 3,
};

const COLOR: Record<NodeType, string> = {
  repo: palette.repo,
  directory: palette.directory,
  file: palette.file,
  external_package: palette.external,
  module: palette.file,
  class: palette.accent,
  function: palette.accent,
};

// 瀏覽器有沒有 WebGL。沒有的話 three.js 畫不出任何東西，而且不一定會拋錯——
// 畫面就只是一片空白，分不出是資料問題還是環境問題。
const WEBGL = (() => {
  try {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('webgl2') ?? canvas.getContext('webgl');
    return context ? '✓' : '✗ 無法取得';
  } catch {
    return '✗ 例外';
  }
})();

// 函式庫的 link 型別只保證有 source / target，我們額外掛的欄位得自己認。
function isImport(link: object): boolean {
  return (link as { type?: string }).type === 'imports';
}

// d3 跑完之後 source / target 會從 id 字串換成節點物件，兩種都要認得。
function endsOf(link: object): [string, string] {
  const { source, target } = link as { source: unknown; target: unknown };
  return [idOf(source), idOf(target)];
}

function idOf(end: unknown): string {
  return typeof end === 'object' && end !== null
    ? String((end as { id?: unknown }).id)
    : String(end);
}

/** 淡化用的顏色。3D 沒有 2D 那種整體 opacity，只能讓顏色自己帶 alpha。 */
const DIM_NODE = 'rgba(91,107,140,0.12)';
const DIM_LINK = 'rgba(70,112,92,0.05)';

export function Graph3D({ graph, spacing }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const scene = useRef<ForceGraph3DInstance | null>(null);
  // 起不來的原因要說出來。畫面一片空白時分不出是沒資料、尺寸 0 還是 WebGL 掛了。
  const [failure, setFailure] = useState<string | null>(null);
  // 分開記，否則 ResizeObserver 晚一步觸發會把資料那一項蓋掉。
  const [size, setSize] = useState('尺寸未知');
  const [loaded, setLoaded] = useState('尚未載入資料');
  // 跟 2D 的 hover 一樣：選中的節點與它的鄰居保持原色，其餘全部淡掉。
  // 放 ref 不放 state——accessor 是建立實例時就註冊的，只能讀得到 ref 的當下值。
  const focus = useRef<Set<string> | null>(null);
  const neighbours = useRef(new Map<string, Set<string>>());

  // 只建立一次。重建會失去鏡頭角度。
  useEffect(() => {
    const container = box.current;
    if (!container) return;

    let instance: ForceGraph3DInstance;
    try {
      instance = new ForceGraph3D(container, {
        // 背景透明，才看得到底下那三層 CSS 動態背景（跟 2D 同一組）
        rendererConfig: { alpha: true, antialias: true },
      })
        .backgroundColor('rgba(0,0,0,0)')
        .showNavInfo(false)
        .nodeLabel('label')
        .nodeVal('size')
        .nodeColor((node: object) => {
          const point = node as { id: string; color: string };
          const lit = focus.current;
          return !lit || lit.has(point.id) ? point.color : DIM_NODE;
        })
        .nodeOpacity(0.95)
        .nodeResolution(16)
        // 標籤是加在球體「之外」的一個文字精靈，不是取代球體
        .nodeThreeObjectExtend(true)
        .nodeThreeObject((node: object) => {
          const point = node as { label?: string; size?: number };
          const text = new SpriteText(point.label ?? '');
          text.color = palette.text;
          text.textHeight = 3;
          // 3d-force-graph 的球半徑約是 nodeVal 的立方根乘上一個常數，往上讓開。
          // SpriteText 的型別定義沒有露出 three 的 position，得自己認。
          const placed = text as unknown as {
            position: { set(x: number, y: number, z: number): void };
          };
          placed.position.set(0, Math.cbrt(point.size ?? 1) * 4 + 3, 0);
          return text;
        })
        .linkColor((link) => {
          const own = isImport(link) ? palette.edgeImports : palette.edge;
          const lit = focus.current;
          if (!lit) return own;
          const [source, target] = endsOf(link);
          return lit.has(source) && lit.has(target) ? own : DIM_LINK;
        })
        .linkWidth((link) => (isImport(link) ? 0.6 : 0.3))
        .linkOpacity(0.55)
        .linkDirectionalArrowLength((link) => (isImport(link) ? 3 : 0))
        .linkDirectionalArrowRelPos(1)
        // hover 與點擊都吃：hover 是 2D 的行為，點擊是滑不準時的備案
        .onNodeHover((node) => light(node as { id: string } | null))
        .onNodeClick((node) => light(node as { id: string } | null))
        // 點空白處還原
        .onBackgroundClick(() => light(null));
    } catch (cause) {
      // 最常見的是 WebGL 起不來（顯示卡驅動、遠端桌面、瀏覽器設定）
      setFailure(cause instanceof Error ? cause.message : '3D 畫布無法初始化');
      return;
    }

    scene.current = instance;

    // 沒有節點就是還原。Cytoscape 的 class 換一下就重畫，3D 得自己把 accessor
    // 重新餵回去逼它重新求值。
    function light(node: { id: string } | null) {
      if (node === null) {
        focus.current = null;
      } else {
        const lit = new Set<string>([node.id]);
        neighbours.current.get(node.id)?.forEach((id) => lit.add(id));
        focus.current = lit;
      }
      instance.nodeColor(instance.nodeColor()).linkColor(instance.linkColor());
    }

    // 掛載當下容器可能還沒有尺寸，用 ResizeObserver 才不會卡在 0×0。
    const observer = new ResizeObserver(() => {
      instance.width(container.clientWidth).height(container.clientHeight);
      setSize(`${container.clientWidth}×${container.clientHeight}`);
    });
    observer.observe(container);
    instance.width(container.clientWidth).height(container.clientHeight);
    setSize(`${container.clientWidth}×${container.clientHeight}`);

    return () => {
      observer.disconnect();
      try {
        instance._destructor();
      } catch {
        // 銷毀失敗不該讓 React 的卸載流程中斷
      }
      scene.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = scene.current;
    if (!instance || !graph) return;

    const elements = toElements(graph);

    // 鄰居表：hover 要在一瞬間答出「這個節點連到誰」，不能每次掃全部的邊。
    const adjacency = new Map<string, Set<string>>();
    for (const edge of elements.edges) {
      const { source, target } = edge.data;
      if (!adjacency.has(source)) adjacency.set(source, new Set());
      if (!adjacency.has(target)) adjacency.set(target, new Set());
      adjacency.get(source)?.add(target);
      adjacency.get(target)?.add(source);
    }
    neighbours.current = adjacency;
    focus.current = null;

    instance.graphData({
      nodes: elements.nodes.map((node) => ({
        id: node.data.id,
        label: node.data.label,
        type: node.data.type,
        size: SIZE[node.data.type],
        color: node.data.parseError ? palette.danger : COLOR[node.data.type],
      })),
      links: elements.edges.map((edge) => ({
        source: edge.data.source,
        target: edge.data.target,
        type: edge.data.type,
      })),
    });
    setLoaded(`節點 ${elements.nodes.length} 邊 ${elements.edges.length}`);

    // 力導向要跑一會兒座標才穩定，跑完再把鏡頭對到整張圖上。沒有這一步，鏡頭
    // 停在預設位置，圖可能整個在視野外——看起來就是「什麼都沒有」。
    const framed = setTimeout(() => instance.zoomToFit(600, 60), 1200);
    return () => clearTimeout(framed);
  }, [graph]);

  // 2D 版的間距是「排完之後拉開座標」，3D 版直接調力導向的理想邊長——3D 的排版
  // 是持續在跑的，改參數就會自己重新鬆開，不必自己動座標。
  //
  // **一定要等資料進去才能碰 d3**：沒有資料時模擬還不存在，`d3ReheatSimulation()`
  // 會丟 `Cannot read properties of undefined (reading 'tick')`，而那個例外會把整
  // 個 render loop 打斷——之後再放資料進去也畫不出來，畫面就是一片空白。
  useEffect(() => {
    const instance = scene.current;
    if (!instance || !graph) return;

    const link = instance.d3Force('link');
    if (link) link.distance(24 * spacing);
    instance.d3ReheatSimulation();
  }, [spacing, graph]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* 跟 2D 同一組動態背景。3D 的畫布是透明的，所以這三層在它底下透出來。 */}
      <div className="bg-grid" />
      <div className="bg-glow" />
      <div className="bg-scan" />
      <div ref={box} style={{ position: 'relative', width: '100%', height: '100%' }} />

      {/* 實驗版的診斷列：空白時分不出哪裡壞了，所以把狀態直接印在畫面上 */}
      <div
        style={{
          position: 'absolute',
          left: 12,
          top: 10,
          fontSize: 11,
          color: palette.textDim,
          pointerEvents: 'none',
        }}
      >
        3D · WebGL {WEBGL} · {size} · {loaded}
      </div>

      {(failure || !graph) && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: failure ? palette.danger : palette.textDim,
            fontSize: 13,
            pointerEvents: 'none',
            textAlign: 'center',
            padding: 24,
          }}
        >
          {failure ?? '還沒有資料——左邊輸入路徑按「分析」'}
        </div>
      )}
    </div>
  );
}
