# codegraph

把一份專案原始碼建成**程式碼知識圖譜**，並在網站上互動式探索。

重點不是「把檔案畫出來」，而是**能回答關係問題** — 這個東西被誰用到、改這裡會波及哪些地方、哪些模組互相循環依賴、某個外部套件滲透到專案的哪些角落。

全專案只有**一張圖**，節點與邊都帶型別：

```json
{ "nodes": [{ "id": "…", "type": "…", "label": "…", "properties": {} }],
  "edges": [{ "source": "…", "target": "…", "type": "…", "properties": {} }],
  "meta":  {} }
```

`type` 是**資料**而不是結構 —— 多一種節點或邊不會讓這份 schema 多一個 key。「依賴圖」與「目錄樹」也不是兩張圖，而是同一張圖篩 `imports` 或篩 `contains` 的兩種視圖。完整的圖模型與型別清單見 [`CLAUDE.md`](CLAUDE.md)。

---

## 現在能做到什麼

輸入一個**本機路徑**，回一張圖，畫在 3D 畫布上：

```
本機路徑 → ingest → scan → parse → resolve → facts → build → 收合／篩邊 → serialize
        → POST /api/analyze → 3D（three.js）或 2D（Cytoscape）畫布
```

| 能力 | 狀態 |
|---|---|
| 目錄結構（`repo` / `directory` / `file` ＋ `contains`） | 可用 |
| Python 的 import 依賴（`imports` ＋ `external_package`） | 可用 |
| Python 的宣告（`class` / `function` ＋ `defines`） | 可用 |
| 收合層級、外部套件三種模式（`full` / `grouped` / `hidden`） | 可用 |
| 點聚合過的 import 邊看它由哪幾筆組成 | 可用 |
| 函式呼叫（`calls`）、類別繼承（`inherits`） | **未進主線** |
| zip 上傳 | **未實作**，目前只有本機路徑 |
| 其他語言 | **未實作**，非 Python 檔案有節點但不 parse |

**分析對象只支援 Python**（與後端本身用 Python 實作是兩回事）。逐項進度與待辦見 [`docs/plan.md`](docs/plan.md)。

---

## 安裝

**Python 3.11+**、**Node 18+**。`conda` 只負責環境與 Python 版本。

```bash
conda create -n codegraph python=3.11
conda activate codegraph
pip install fastapi uvicorn pydantic networkx pytest ruff mypy
```

> **`backend/requirements.txt` 還不存在。** 要收哪些套件、釘什麼版本尚未拍板（`docs/plan.md` 的 0.4），所以上面是手動安裝。建立之後改成 `pip install -r backend/requirements.txt`。

前端：

```bash
cd frontend
npm install --legacy-peer-deps
```

`--legacy-peer-deps` 是為了繞過 npm 9.2.0 的 `edgesOut` bug。**Vite 釘在 6.x**，因為 Vite 7 要求 Node `^20.19` 或 `>=22.12`。

---

## 啟動

前後端各自獨立，開兩個終端機。

**後端**（`:8000`）：

```bash
cd backend
conda activate codegraph
CODEGRAPH_ALLOWED_ROOTS=/path/to/your/projects uvicorn app.main:app --port 8000 --reload
```

**前端**（`:5173`）：

```bash
cd frontend
npm run dev
```

開 http://localhost:5173 ，在輸入框填一個**落在 allowlist 內**的路徑。vite 的 proxy 把 `/api` 轉到 `:8000`。

| 症狀 | 原因 |
|---|---|
| 所有路徑都回 `400 路徑不被允許` | 沒帶 `CODEGRAPH_ALLOWED_ROOTS`。**未設定＝全部拒絕** |
| 前端連得上、後端沒反應 | proxy 目標寫死 `:8000`，後端換 port 要同步改 `frontend/vite.config.ts` |
| `ModuleNotFoundError: app` | uvicorn 必須在 `backend/` 底下跑 |

uvicorn 改程式碼要自己重啟（或加 `--reload`）；vite 存檔即時生效。

**`CODEGRAPH_ALLOWED_ROOTS` 不是可選的。** 本機路徑模式僅限開發用，沒有這道閘門就等於把整個檔案系統的讀取權開放給任何打得到 API 的人。

---

## 專案結構

```
codegraph/
├── backend/     FastAPI 服務與整條分析管線
├── frontend/    Vite + React + TS 的網站
├── docs/        設計與規劃文件
├── CLAUDE.md
└── README.md
```

後端是一條**單向管線**，每一階段只吃前一階段的輸出：`ingest` → `scan` → `parse` → `facts` → `build` → `serialize`，其中 `facts` 會呼叫 `resolve` 把名字接成邊。每一段都能餵假輸入單獨測試。

逐層放什麼檔案、為什麼放在那裡，見 [`docs/System_arch.md`](docs/System_arch.md)；各階段的職責與資料流見 [`CLAUDE.md`](CLAUDE.md) › 架構。

---

## 文件

程式碼是實作，**文件是規格**。動一個組件之前先讀它對應的那一份。

| 文件 | 講什麼 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | 互動守則、專案目標、圖模型、架構原則 |
| [`docs/plan.md`](docs/plan.md) | 範圍、階段切分、逐項進度與待辦 |
| [`docs/System_arch.md`](docs/System_arch.md) | 目錄架構：哪一層放什麼 |
| [`docs/Backend.md`](docs/Backend.md) | 後端全體：規格書格式、跨元件的決定 |
| [`docs/Frontend.md`](docs/Frontend.md) | 前端全體：資料流、視覺編碼、畫布、互動、硬性規則 |
| [`docs/backend/ingest.md`](docs/backend/ingest.md) | 取得目錄、allowlist、找出真正的根 |
| [`docs/backend/scan.md`](docs/backend/scan.md) | 走訪、忽略規則、`contains` 邊 |
| [`docs/backend/parse.md`](docs/backend/parse.md) | 每語言的 parser、`Fact` 型別、為什麼 Python 用標準庫 `ast` |
| [`docs/backend/resolve.md`](docs/backend/resolve.md) | 名字 → 節點，整條管線準確度的瓶頸 |
| [`docs/backend/facts.md`](docs/backend/facts.md) | 型別 → 產生器的表 |
| [`docs/backend/graph.md`](docs/backend/graph.md) | build、查詢層、收合、存檔 |
| [`docs/backend/graph_schema.md`](docs/backend/graph_schema.md) | schema 與 `id` 規則 —— **前後端唯一契約** |
| [`docs/backend/api.md`](docs/backend/api.md) | API 與管線編排 |

改 schema（加欄位、改欄位名、改 `id` 規則）就必須同步改 `frontend/src/api/types.ts`，否則前端會靜默拿到 `undefined`。

---

## 開發

**後端**（cwd 在 `backend/`，先 `conda activate codegraph`）：

```bash
pytest          # 171 passed
ruff check .
mypy app
```

> **`mypy` 要指定 `app`。** `mypy .` 會多報一個既存錯誤 —— `tests/test_models_graph.py` 故意傳一個非法的 `type` 去測 `ValidationError`，那不是壞掉。

**前端**（cwd 在 `frontend/`）：

```bash
npm test        # 12 passed
npx tsc -b
npm run build
```

所有查詢都必須經過查詢層介面（`app/graph/query.py`），API 與前端**不直接操作 networkx 物件** —— 這層隔離是為了日後換成圖資料庫（Neo4j / Kuzu）時不必動上層。
