// Cytoscape 畫布 ＋ 右下角縮圖。
//
// 實例放 ref 而不是 state：放 state 會讓 React 重新渲染整張圖，使用者的
// pan / zoom 與選取全部消失。React 只負責餵資料與觸發 layout。

import cytoscape from 'cytoscape';
import { useEffect, useRef } from 'react';

import type { GraphDocument } from '../api/types';
import { layoutOptions, type LayoutId } from '../graph/layouts';
import { graphStyle, minimapStyle, palette } from '../graph/style';
import { toElements } from '../graph/transform';

interface Props {
  graph: GraphDocument | null;
  layout: LayoutId;
  spacing: number;
  query: string;
}

export function GraphCanvas({ graph, layout, spacing, query }: Props) {
  const canvasBox = useRef<HTMLDivElement>(null);
  const minimapBox = useRef<HTMLDivElement>(null);
  const viewportBox = useRef<HTMLDivElement>(null);
  const cy = useRef<cytoscape.Core | null>(null);
  const mini = useRef<cytoscape.Core | null>(null);
  // hover 結束後要還原成搜尋當下的狀態，所以需要讀得到最新的 query。
  const queryRef = useRef(query);
  queryRef.current = query;
  // 目前套用在座標上的間距倍率。排版剛跑完是 1，之後靠比值往上疊。
  const spacingRef = useRef(spacing);

  // 只建立一次。重建會失去 pan / zoom。
  useEffect(() => {
    if (!canvasBox.current || !minimapBox.current) return;

    const main = cytoscape({
      container: canvasBox.current,
      style: graphStyle,
      wheelSensitivity: 0.5,
      minZoom: 0.05,
      maxZoom: 6,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    });
    const map = cytoscape({
      container: minimapBox.current,
      style: minimapStyle,
      userZoomingEnabled: false,
      userPanningEnabled: false,
      boxSelectionEnabled: false,
      autoungrabify: true,
    });
    cy.current = main;
    mini.current = map;

    main.on('mouseover', 'node', (event) => {
      main.elements().addClass('dim');
      event.target.closedNeighborhood().removeClass('dim').addClass('hl');
    });
    main.on('mouseout', 'node', () => {
      main.elements().removeClass('dim hl');
      highlight(main, queryRef.current);
    });
    main.on('viewport', () => drawViewport(main, map, viewportBox.current));

    // 點縮圖就把主畫布移到那個位置。
    map.on('tap', (event) => {
      const zoom = main.zoom();
      main.animate(
        {
          pan: {
            x: main.width() / 2 - event.position.x * zoom,
            y: main.height() / 2 - event.position.y * zoom,
          },
        },
        { duration: 200 },
      );
    });

    return () => {
      main.destroy();
      map.destroy();
      cy.current = null;
      mini.current = null;
    };
  }, []);

  // 換資料：只換 elements，不動實例。
  useEffect(() => {
    const main = cy.current;
    if (!main || !graph) return;

    const elements = toElements(graph);
    main.elements().remove();
    main.add([...elements.nodes, ...elements.edges]);
    runLayout(main, mini.current, viewportBox.current, layout, spacingRef);
    // layout 與 spacing 的變化由下面兩個 effect 處理，這裡只認 graph。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph]);

  // 換排版方式：整張圖會大搬家，重新 fit 才找得到東西。
  useEffect(() => {
    const main = cy.current;
    if (!main || main.elements().empty()) return;
    runLayout(main, mini.current, viewportBox.current, layout, spacingRef);
  }, [layout]);

  // 調間距：不重跑排版，只把座標等比例撐開。每條線都會等比例變長，而且很快。
  useEffect(() => {
    const main = cy.current;
    if (!main || main.elements().empty()) return;

    rescale(main, spacing / spacingRef.current);
    spacingRef.current = spacing;
    if (mini.current) {
      syncMinimap(main, mini.current);
      drawViewport(main, mini.current, viewportBox.current);
    }
  }, [spacing]);

  useEffect(() => {
    const main = cy.current;
    if (!main) return;
    const matched = highlight(main, query);
    if (matched?.length) {
      main.animate({ center: { eles: matched[0] } }, { duration: 300 });
    }
  }, [query]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div className="bg-grid" />
      <div className="bg-glow" />
      <div className="bg-scan" />
      <div
        ref={canvasBox}
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          cursor: 'grab',
        }}
        onPointerDown={(event) => {
          event.currentTarget.style.cursor = 'grabbing';
        }}
        onPointerUp={(event) => {
          event.currentTarget.style.cursor = 'grab';
        }}
      />

      <div
        style={{
          position: 'absolute',
          left: 16,
          bottom: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
      >
        <ZoomButton label="＋" onClick={() => zoomBy(cy.current, 1.4)} />
        <ZoomButton label="－" onClick={() => zoomBy(cy.current, 1 / 1.4)} />
        <ZoomButton label="⤢" onClick={() => cy.current?.animate({ fit: { eles: cy.current.elements(), padding: 40 } }, { duration: 250 })} />
      </div>

      <div
        style={{
          position: 'absolute',
          right: 16,
          bottom: 16,
          width: 200,
          height: 150,
          background: palette.panel,
          border: `1px solid ${palette.border}`,
          borderRadius: 6,
          overflow: 'hidden',
        }}
      >
        <div ref={minimapBox} style={{ width: '100%', height: '100%' }} />
        <div
          ref={viewportBox}
          style={{
            position: 'absolute',
            border: `1px solid ${palette.accent}`,
            background: `${palette.accent}18`,
            pointerEvents: 'none',
            left: 0,
            top: 0,
            width: 0,
            height: 0,
          }}
        />
      </div>
    </div>
  );
}

// 以畫面中心為支點縮放，跟滾輪的行為一致。
function zoomBy(main: cytoscape.Core | null, factor: number) {
  if (!main) return;
  main.animate(
    {
      zoom: {
        level: main.zoom() * factor,
        renderedPosition: { x: main.width() / 2, y: main.height() / 2 },
      },
    },
    { duration: 150 },
  );
}

function ZoomButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: 30,
        height: 30,
        background: palette.panel,
        border: `1px solid ${palette.border}`,
        borderRadius: 4,
        color: palette.text,
        cursor: 'pointer',
        fontSize: 13,
        lineHeight: 1,
        padding: 0,
      }}
    >
      {label}
    </button>
  );
}

function runLayout(
  main: cytoscape.Core,
  map: cytoscape.Core | null,
  viewport: HTMLDivElement | null,
  layout: LayoutId,
  spacingRef: { current: number },
) {
  const running = main.layout(layoutOptions(layout, true));
  running.one('layoutstop', () => {
    // 排版本身不管間距，跑完之後才把當前倍率套上去。
    rescale(main, spacingRef.current);
    frameGraph(main);
    if (!map) return;
    syncMinimap(main, map);
    drawViewport(main, map, viewport);
  });
  running.run();
}

// 全部塞進畫面常常小到看不清字。定一個起始的最小倍率，不夠大就改成從根節點
// 附近看起，其餘用拖曳或縮圖去找。
const INITIAL_MIN_ZOOM = 0.8;

function frameGraph(main: cytoscape.Core) {
  main.fit(undefined, 40);
  if (main.zoom() >= INITIAL_MIN_ZOOM) return;

  main.zoom(INITIAL_MIN_ZOOM);
  const root = main.nodes('[type = "repo"]');
  main.center(root.nonempty() ? root : main.elements());
}

// 以整張圖的中心為支點等比例拉開座標。用 Cytoscape 的 spacingFactor 只有部分層
// 次會動，自己算才能保證每一條線都等比例變長。
//
// **鏡頭刻意不動**：節點的大小是模型單位，鏡頭不變就代表螢幕上的節點大小不變，
// 而座標拉開了，所以間距真的變大。代價是整張圖會長出畫面外——那是必然的，節點
// 大小固定、間距變大，總範圍就一定變大。
//
// 曾經試過反向補償鏡頭讓整張圖佔的範圍不變，但那會讓節點跟著縮小，看起來就成
// 了「整張圖縮小」。三件事（節點大小不變／間距變大／總範圍不變）不可能同時成
// 立，這裡選擇固定節點大小。
function rescale(main: cytoscape.Core, factor: number) {
  if (factor === 1 || !Number.isFinite(factor)) return;

  const box = main.elements().boundingBox();
  const centerX = (box.x1 + box.x2) / 2;
  const centerY = (box.y1 + box.y2) / 2;

  main.nodes().positions((node) => {
    const position = node.position();
    return {
      x: centerX + (position.x - centerX) * factor,
      y: centerY + (position.y - centerY) * factor,
    };
  });
}

// 縮圖是第二個唯讀的實例，直接複製主畫布算好的座標。
function syncMinimap(main: cytoscape.Core, map: cytoscape.Core) {
  map.elements().remove();
  map.add(
    main.elements().map((element) =>
      element.isNode()
        ? {
            group: 'nodes' as const,
            data: { ...element.data() },
            position: { ...element.position() },
          }
        : { group: 'edges' as const, data: { ...element.data() } },
    ),
  );
  map.fit(undefined, 6);
}

// 把主畫布現在看得到的範圍，換算成縮圖上的一個框。
function drawViewport(
  main: cytoscape.Core,
  map: cytoscape.Core,
  viewport: HTMLDivElement | null,
) {
  if (!viewport) return;
  const extent = main.extent();
  const zoom = map.zoom();
  const pan = map.pan();

  viewport.style.left = `${extent.x1 * zoom + pan.x}px`;
  viewport.style.top = `${extent.y1 * zoom + pan.y}px`;
  viewport.style.width = `${(extent.x2 - extent.x1) * zoom}px`;
  viewport.style.height = `${(extent.y2 - extent.y1) * zoom}px`;
}

// 搜尋是「高亮」不是「篩選」：符合的發亮、其餘變暗，才看得出它在樹的哪裡。
function highlight(main: cytoscape.Core, query: string) {
  main.elements().removeClass('dim hl match');
  const needle = query.trim().toLowerCase();
  if (!needle) return undefined;

  const matched = main
    .nodes()
    .filter((node) => String(node.data('label')).toLowerCase().includes(needle));
  if (matched.empty()) return undefined;

  main.elements().addClass('dim');
  matched.removeClass('dim').addClass('match');
  return matched;
}
