# System_arch.md

專案的目錄架構：**哪一層放什麼、為什麼放在那裡**。

各階段的職責與資料流定義在 **CLAUDE.md › 架構**，此處不重複；這份文件只談檔案擺放。

---

## 頂層

前後端各自是一個獨立子專案，能分別安裝依賴、分別啟動。

```
codegraph/
├── backend/
├── frontend/
├── docs/
├── CLAUDE.md
└── .gitignore
```

| 路徑 | 放什麼 |
|---|---|
| `backend/` | FastAPI 服務與整條分析管線 |
| `frontend/` | Vite + React + TS 的網站 |
| `docs/` | 設計與規劃文件 |
| `CLAUDE.md` | 互動守則、專案目標、圖模型、架構原則 |

**為什麼不把後端攤在根目錄** — 根目錄若直接放 `app/`、`tests/`、`requirements.txt`，後端的內部結構會跟 `docs/`、`frontend/` 混在同一層，且 `tests/` 是誰的測試變得不明確。分成兩個子目錄後，「前後端分離、各自獨立啟動」這件事從目錄結構就看得出來。

---

## 後端 · `backend/`

```
backend/
├── app/
│   ├── main.py
│   ├── api/
│   ├── ingest/
│   ├── scan/
│   ├── parsers/
│   ├── resolve/
│   ├── languages/
│   ├── graph/
│   └── models/
├── tests/
├── data/
└── requirements.txt
```

| 路徑 | 放什麼 | 對應 CLAUDE.md |
|---|---|---|
| `app/main.py` | FastAPI 進入點 | — |
| `app/pipeline.py` | 把 scan / parse / resolve / build 串成一次分析 | docs/backend/api.md › 管線編排 |
| `app/api/` | HTTP 層：路由、request / response | docs/backend/api.md |
| `app/ingest/` | zip 解壓、本機路徑 allowlist、找出真正的根 | 架構 › ingest |
| `app/scan/` | 走訪、忽略規則、產出 `file`/`directory` 節點與 `contains` 邊 | 架構 › scan |
| `app/parsers/` | 每語言一個模組，吐出帶型別的 `Fact` | 架構 › parse |
| `app/resolve/` | 每語言一個模組，把名字接到節點上 | 架構 › resolve |
| `app/languages/` | `LANGUAGES` registry，以副檔名為 key 把 parser 與 resolver 配成一筆 | 架構 › 語言 registry |
| `app/graph/` | `build.py`（組圖＋驗證）、`query.py`（查詢層介面） | 架構 › build、專案目標 › 儲存與查詢 |
| `app/models/` | pydantic 的 `{ nodes, edges, meta }` | 架構 › serialize |
| `tests/` | 結構對應 `app/`，一個模組一個測試檔 | — |
| `data/` | 分析結果 JSON。**進 `.gitignore`** | 尚無依據，見「未定之處」 |

### 為什麼 `app/languages/` 要獨立一層

registry 需要同時 import parser 與 resolver。若把它放進 `parsers/`，`resolve` 就得反過來依賴 `parsers`，兩層綁死。

獨立成一層後，接線的責任集中在這裡：

| 模組 | 認得誰 |
|---|---|
| `app/parsers/` | 只認得 `Fact` 型別 |
| `app/resolve/` | 只認得 `Fact` 與全域檔案索引 |
| `app/languages/` | 認得上面兩者，負責把它們配對 |

新增一種語言時，在 `parsers/` 與 `resolve/` 各加一個模組，再到 `languages/` 加一筆——三處都是新增，沒有任何既有檔案要改。

---

## 前端 · `frontend/`

```
frontend/
└── src/
    ├── api/
    │   ├── types.ts
    │   └── client.ts
    ├── graph/
    │   └── transform.ts
    └── components/
```

| 路徑 | 放什麼 | 約束 |
|---|---|---|
| `src/api/types.ts` | 對應後端 pydantic 的 TS 型別 | **前後端唯一契約**，改後端 schema 就必須同步改這裡 |
| `src/api/client.ts` | fetch 封裝 | |
| `src/graph/transform.ts` | API 形狀 → Cytoscape elements | 轉換集中在這裡，元件不直接碰 API 型別 |
| `src/components/` | React 元件 | 畫布元件的 Cytoscape 實例放 **ref**，不放 React state |

---

## 未定之處

| 位置 | 缺什麼 |
|---|---|
| `data/` | 「分析結果以 JSON 持久化」有寫，但沒規定存放位置、檔名規則與保留策略。`store.save()` / `load()` 目前把路徑當參數收，所以還不必決定 |
