// 後端呼叫的唯一入口。元件不直接 fetch。

import type { AnalyzeRequest, GraphDocument, ImpactRequest } from './types';

export class ApiError extends Error {}

export function analyze(request: AnalyzeRequest): Promise<GraphDocument> {
  return post('/api/analyze', request, '分析失敗');
}

/** 改這個節點會波及誰。回來的是畫面那一層的節點，帶 `impact_depth`。 */
export function impact(request: ImpactRequest): Promise<GraphDocument> {
  return post('/api/impact', request, '查不到影響範圍');
}

async function post(url: string, body: unknown, failure: string): Promise<GraphDocument> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    // 後端刻意只回一句模糊的話（詳細原因在伺服器日誌裡），照原樣顯示即可。
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    throw new ApiError(detail ?? `${failure}（HTTP ${response.status}）`);
  }

  return (await response.json()) as GraphDocument;
}
