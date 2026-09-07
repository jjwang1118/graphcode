# plan.md

專案的範圍、進度與待辦。

---

## Scope

**分析對象**語言第一階段只支援 Python（與後端本身用 Python 實作是兩回事）。非 Python 檔案仍會產生 `file` 節點與 `contains` 邊，只是不送進 parse —— **語言限制作用在 parse / resolve，不作用在 scan**。

以下是**階段切分**。

---

## Action list

### 階段 0 — 前置

打通開發環境，讓後續每一步都有回頭路。

| # | 項目 | 完成條件 | 對應文件 | 狀態 | 最後修改 | 備註 |
|---|---|---|---|---|---|---|
| 0.1 | 定義 CLAUDE.md | 設計內容定稿：範圍、圖模型、架構各段之間無互相矛盾，且沒有指向已刪除小節的引用 | CLAUDE.md | 完成 | 2026-09-04 | |
| 0.2 | 定義目錄架構 | 每個資料夾寫明放什麼，前後端各自成一個獨立子專案 | docs/System_arch.md | 完成 | 2026-09-04 | |
| 0.3 | `git init`、加 `.gitignore` | 能提交一次 commit，暫存/快取檔不進版控 | | 完成 | 2026-09-06 | 第一個 commit `cef238b`，83 個檔案。**時機是使用者要求的**：準備把「視圖切換」改成「縮放換層級」，需要一個回得去的點。`.gitignore` 擋掉 `__pycache__`／各種 cache／`node_modules`／`dist`／`.claude/settings.local.json`（本機設定）。分析結果的存放位置仍未定，所以沒有預留規則 |
| 0.4 | 建立 conda 環境 | `conda create -n codegraph python=3.11` 後 `python -V` 為 3.11 | | 待辦 | | 環境已存在（Python 3.11.16），fastapi / networkx / pydantic / pytest / ruff / mypy 均已安裝。尚未結案的原因：① `requirements.txt` 要收哪些套件待確認 ② 環境內有一個 `codegraph 0.1.0` 的 editable 安裝指向空目錄，來源不明，未處理 |
| 0.5 | backend 骨架 | `backend/app/` 九個套件目錄與 `backend/tests/` 建立完成，`pytest` 跑得起來 | docs/System_arch.md | 完成 | 2026-09-04 | 原完成條件含 `requirements.txt` 與 ruff / mypy 設定，兩者都移除：前者內容待確認，後者在零程式碼時定不出有根據的值，改為需要時再開檔。`main.py` 只有 FastAPI app 實例，`/api/ping` 留給 0.7 |
| 0.6 | frontend 骨架 | Vite + React + TS 建起，vite proxy 把 `/api` 轉到 `:8000`，`npm run build` 通過 | docs/System_arch.md | 完成 | 2026-09-04 | **Vite 釘在 6.x**，因為本機 Node 為 v18.19.1，而 Vite 7 要求 Node `^20.19` 或 `>=22.12`。Node 升級後可單獨升 Vite。尚未安裝 Cytoscape.js（屬 1.10） |
| 0.7 | 前後端各跑一個 hello world | 從前端打 `/api/ping` 拿得到後端回應，證明 proxy 通 | docs/backend/api.md | 完成 | 2026-09-05 | 實測 `localhost:8000/api/ping` 與經 proxy 的 `localhost:5173/api/ping` 都回 `{"status":"ok"}`。路由定義放 `app/api/health.py`、註冊放 `main.py`，該決定已補寫進 `docs/backend/api.md`。前端 `App.tsx` 仍是 create-vite 預設內容，未串接此端點 |

---

### 階段 1 — 本機路徑 → 目錄樹

```
本機路徑 → scan → build → serialize → API → 前端畫出目錄樹
```

**刻意跳過 parse 與 resolve。** `contains` 那一半在 scan 跑完時就完整了，所以不碰最難的兩層也能打通完整路徑。

| # | 項目 | 完成條件 | 對應文件 | 狀態 | 最後修改 | 備註 |
|---|---|---|---|---|---|---|
| 1.1 | `app/models/`：serialize schema | pydantic 定義 `{ nodes, edges, meta }`，`id` 前綴規則寫死並有測試 | docs/backend/graph_schema.md | 完成 | 2026-09-05 | `types.py`（兩個 `StrEnum`）、`ids.py`（`PREFIX` 對照表 ＋ `make_id` / `owner_file`）、`graph.py`（`Node` / `Edge` / `Meta` / `GraphDocument`）。`meta` 五個欄位寫死；邊兩端存在與否不在這層驗證，留給 1.5。23 個測試通過，ruff / mypy 乾淨。兩處實作時自行決定、無上位依據的判斷（絕對路徑丟 `ValueError`、`module:` 的 `owner_file()` 回 `None`）記在該文件的「自行決定的部分」 |
| 1.2 | `frontend/src/api/types.ts` | 與 1.1 逐欄對應，改一邊就知道要改另一邊 | docs/backend/graph_schema.md | 完成（後半條件未達成） | 2026-09-05 | 手抄 `NodeType` / `EdgeType`（字串 union）與 `Node` / `Edge` / `Meta` / `GraphDocument`，`npm run build` 通過。**「改一邊就知道要改另一邊」目前靠人工紀律**，沒有機械保證；`analyzed_at` 對應成 `string \| null`（JSON 無 datetime）。考慮過現在就從 pydantic 的 JSON Schema 生成，選擇不做——不新增依賴、`types.ts` 不變成產物，較好反悔 |
| 1.3 | `app/ingest/`：本機路徑 | allowlist 之外的路徑被擋掉，且有測試涵蓋 | docs/backend/ingest.md | 完成 | 2026-09-05 | `local.py`（`from_local_path()` ＋ `allowed_roots_from_env()`）、`errors.py`（`IngestError`）。清單以參數傳入，環境變數 `CODEGRAPH_ALLOWED_ROOTS`；未設定＝全部拒絕。15 個測試涵蓋 `..` 逃逸、symlink 逃逸、同前綴的兄弟目錄、空清單。實作時自行加的一條：**先查清單再查存在**，否則錯誤訊息會變成探測路徑是否存在的工具 |
| 1.4 | `app/scan/`：走訪 + 忽略規則 | 吐出檔案清單、`file`/`directory` 節點、`contains` 邊 | docs/backend/scan.md | 完成 | 2026-09-05 | `walk.py`（`from_root()` → `ScanResult{nodes, edges, files}`）、`ignore.py`（`DEFAULT_IGNORE` 九項，以參數傳入）。**symlink 一律跳過、連節點都不產**，補掉 1.3 只檢查入口路徑留下的洞。每層 `sorted()` 確保跑兩次結果相同。`properties` 留空。11 個測試，含「篩 `contains` 剛好是一棵樹」 |
| 1.5 | `app/graph/build.py` | 組圖、驗證每條邊兩端節點都存在、算出 `meta` | docs/backend/graph.md | 完成 | 2026-09-05 | `build()` 回 `CodeGraph`（`query.py`，networkx 藏在裡面），圖用 **`MultiDiGraph`**（`calls`／重複 import 需要平行邊）。驗證擋壞邊與重複 id，一次列出全部。`cycles` 只看 `imports` 子圖並旋轉成從最小 id 起算以確保可重現；`isolated_nodes` 階段 1 保持空。11 個測試，含「networkx 沒有外露」。**mypy 對 networkx 沒有 stub**，兩處 import 加了 `# type: ignore[import-untyped]`，見下方 0.4 |
| 1.6 | 查詢層介面 | 至少有「篩邊型別 → 子圖」，且 API 不直接碰 networkx 物件 | docs/backend/graph.md | 完成 | 2026-09-05 | `CodeGraph.document()` 與 `view(*edge_types)`，都回 `GraphDocument`。篩邊後節點全部保留；`view()` 的 `meta` 只重算數量，`cycles` / `analyzed_at` 沿用全圖。`neighbors()` / `path()` 先不做，沒有呼叫端。8 個測試 |
| 1.7 | API endpoint | 可觸發分析並取回圖（形狀同 1.1） | docs/backend/api.md | 完成 | 2026-09-05 | `POST /api/analyze`，body `{path, edge_types?}`，同步回 `GraphDocument`。`IngestError` → 400、`BuildError` → 500，兩者都只回固定訊息，詳細原因進日誌。已用 `app.openapi()` 與手抄的 `types.ts` **逐欄核對過**，欄位名、兩個 enum 的值、`analyzed_at` 的 `string \| null` 全部一致，`response_model` 確實有宣告。httpx 未安裝，`TestClient` 用不了，改為直接呼叫 handler ＋ 檢查 `app.openapi()`。6 個測試 |
| 1.8 | JSON 存檔 → 讀回建圖 | 讀取路徑與分析路徑共用同一個 build，有測試證明 | docs/backend/graph.md | 完成 | 2026-09-05 | `app/graph/store.py` 的 `save()` / `load()`。檔案位置由呼叫端決定，避開 `data/` 那個未定之處。`load()` 走同一個 `build()`，測試用一份「邊指向不存在節點」的檔案證明驗證確實有跑。`build()` 多一個 `analyzed_at` 參數，否則讀檔會被記成一次新分析。3 個測試 |
| 1.9 | `frontend/src/graph/transform.ts` | API 形狀 → Cytoscape elements，元件不直接碰 API 型別 | | 完成 | 2026-09-05 | `toElements()` 純函式，**刻意不 import cytoscape**，所以能單獨測。邊 id 由前端自己編（後端不給），格式 `type:source->target`，平行邊補 `#n`。裝了 **vitest 5.0.0**（`npm test`），6 個測試。安裝時撞到 npm 9.2.0 的 `edgesOut` bug，要加 `--legacy-peer-deps` 才裝得起來 |
| 1.10 | Cytoscape 畫布元件 | 實例放 ref；重新渲染不會失去 pan / zoom 與選取 | | 完成 | 2026-09-05 | `GraphCanvas.tsx`（實例放 ref，建立一次，換資料只 remove/add 再重跑 layout）、`client.ts`、`App.tsx` 改寫成輸入框＋按鈕＋畫布。**接線（`client.ts`、`App.tsx`）原本不在 plan 的任何一項裡**，併進這一項做掉。layout 用內建 `breadthfirst` 且不指定 roots——`contains` 是樹，沒有入邊的只有 repo。裝了 `cytoscape ^3.34.2` 與 `@types/cytoscape`。UI 只做驗收需要的最小樣子，樣式與互動規格刻意不定，等看過真實畫面再說 |
| 1.11 | 拿本專案自己跑一次 | 畫得出 codegraph 自己的目錄樹 | | 完成 | 2026-09-05 | 已目視確認畫得出來，但**美觀不足**（87 節點時的排版與標籤），屬階段 4。實測 `POST /api/analyze`：**87 節點、86 邊**（86 = 87 − 1，是一棵樹），型別分佈 file 65 / directory 21 / repo 1；`node_modules`、`dist`、`__pycache__`、`.git` 都沒漏進去。經 vite proxy 打 `edge_types: ["imports"]` 回 87 節點 0 邊（階段 1 正確行為）。`/etc` 回 400 `{"detail":"路徑不被允許"}`，訊息不含路徑。**畫面本身尚未目視確認** |

這一刀真正要驗證的是**「單一圖 + 視圖」這個模型在真實程式碼裡站得住腳**。

---

### 階段 2 — parse + resolve（只做 Python）

```
+ parse（Python）→ resolve → imports 邊 → 依賴圖視圖
```

| # | 項目 | 完成條件 | 對應文件 | 狀態 | 最後修改 | 備註 |
|---|---|---|---|---|---|---|
| 2.1 | 決定 Python 的解析方式 | 從 `ast` / tree-sitter / 正規掃描擇一並寫下理由 | docs/backend/parse.md | 完成 | 2026-09-05 | 選 **標準庫 `ast`**。實測比較過三案：正規掃描對括號跨行會漏抓、對註解與字串會誤抓（誤抓更糟，會造出不存在的 `ext:` 節點），直接淘汰；tree-sitter 的兩個優勢（容錯、多語言）現在都用不到，且要付兩個依賴。`ast` 給的 `level` 欄位讓相對 import 直接可解。**代價**：語法錯誤或比後端新的語法（實測 3.11 解析不了 3.12 的 `type` 別名與 `def f[T]()`）會讓整份檔案歸零，所以配套要求失敗顯性化——標在節點 `properties["parse_error"]` ＋ `meta.parse_failures` 計數。換 tree-sitter 的觸發條件已寫進文件 |
| 2.2 | `Fact` 型別與 parser 介面 | parser 可用「餵一段程式碼字串、斷言 fact 清單」單獨測試 | docs/backend/parse.md | 完成 | 2026-09-05 | `facts.py`（`Import` / `Fact` / `ParseResult` / `Parser` protocol）、`python.py`（`PythonParser`）。**12 個測試**：括號跨行、`level=1` / `level=2`、別名、註解與字串不誤抓、`if TYPE_CHECKING` 與函式內（所以用 `ast.walk` 不只看頂層）、語法錯誤、二進位內容、無 import 但成功。實作時比文件多定兩件事：① 整包 `import x` 時 `name=None`（不重複填 `module`）② 二進位檔 `ast.parse` 拋的是 `ValueError` 不是 `SyntaxError`，一併當解析失敗接住，否則一個假 `.py` 會讓整次分析崩掉。四個設計決定：① `@dataclass(frozen=True)`，不用 pydantic——**用不用 pydantic 標示這個型別會不會跨邊界** ② 每種 Fact 各自一個 class ＋ union 別名，不用單一 class 加 `kind`（欄位會退化成一堆 `Optional`） ③ 失敗回 `ParseResult(facts, error)` 不拋例外，因為 `error` 要一路流到節點的 `properties` ④ **Fact 先不宣告自己產生什麼邊**，等第三種 Fact 出現再評估。介面 `parse(source: str) -> ParseResult` 吃字串不吃路徑，parser 不碰檔案系統 |
| 2.3 | 語言 registry | 以副檔名為 key，一筆同時掛 parser 與 resolver | docs/System_arch.md › `app/languages/` | 完成 | 2026-09-06 | `app/languages/registry.py`：`Language(parser, resolver)` frozen dataclass ＋ `LANGUAGES` 字典 ＋ `for_path()`。**刻意排在 2.5 之後做**，因為 resolver 到 2.5 才存在，先做會留一個「暫時是 None」的欄位——CLAUDE.md 說「不可能只加一半」正是這個顧慮 |
| 2.4 | Python parser | 抽得出 `Import`，且不做任何路徑解析 | docs/backend/parse.md | 完成 | 2026-09-05 | 併在 2.2 一起做（`app/parsers/python.py`）——介面沒有具體實作沒辦法驗證，分開做是空的 |
| 2.5 | resolve：全域索引 + Python 規則 | 對得到的接 `file` 節點，對不到的造 `external_package` | docs/backend/resolve.md | 完成 | 2026-09-05 | `index.py`（`ModuleIndex` / `from_files`）、`python.py`（`PythonResolver`）、`edges.py`（`to_edges` → `ResolveResult`）。**設計中途推翻過一次**：原本用「往上爬到沒有 `__init__.py` 的目錄」判斷 source root，實測使用者自己的專案（`poison-fru-sok-h100` 18 個 py 檔、`__init__.py` 0 個）會把 `import utils.fflow` 這種內部依賴誤判成 `ext:utils`，且無聲無息。改成**一個檔案登記所有可能的模組名**（每層祖先各當一次 root），誰對得上算誰。五個決定：① 外部套件節點取最頂層，完整路徑進邊的 `properties` ② 一筆 fact 一條平行邊 ③ 只連指名的模組，不連沿路 package ④ 撞號取路徑上最近的、平手取排序第一 ⑤ 撞號標 `ambiguous`＋計數，不中斷分析。相對 import 走路徑不走模組名；爬出專案外不產生邊，另計 `unresolved` |
| 2.6 | resolve 測試 | 相對 import、`__init__.py`、`import *`、對不到的外部套件都涵蓋 | docs/backend/resolve.md | 完成 | 2026-09-05 | 27 個測試（`test_resolve_index.py` 9 ＋ `test_resolve_python.py` 18），與 2.5 一起做——resolve 是準確度瓶頸，測試不該是另一個項目。**端對端實測**：`codegraph` 自己 41 個 py 檔 → 200 條 imports 邊（內部 143 / 外部 57）、15 個外部套件節點；`poison-fru-sok-h100` 18 個 py 檔 → 144 條邊（內部 22 / 外部 122）。兩者 `ambiguous` 與 `unresolved` 皆為 0 |
| 2.8 | 接管線 | `POST /api/analyze` 回得出 `imports` 邊，且 API 層不編排管線 | docs/backend/api.md › 管線編排 | 完成 | 2026-09-06 | **原本不在 plan 裡**，跟 1.10 的接線一樣是漏掉的項目，補列於此。新增 `app/pipeline.py`（`analyze(root) -> CodeGraph`），`api/analyze.py` 只剩換路徑與換狀態碼。`Meta` 加三個計數欄位（`parse_failures` / `ambiguous_imports` / `unresolved_imports`），由 `Diagnostics` frozen dataclass 傳給 `build()` **照抄不計算**——build 不該認識 parse 與 resolve；`store.load()` 也要把數字帶回去否則讀檔歸零。`parse_error` 由 pipeline 貼回 file 節點（不是 build，理由同上）。`frontend/src/api/types.ts` 的 `Meta` 已同步。8 個測試。**實測本專案：119 節點（file 82 / dir 21 / ext 15 / repo 1）、334 條邊（contains 103 / imports 231）、三個計數皆 0、循環依賴 0 個** |
| 2.7 | 前端依賴圖視圖 | **只加篩選條件，不新增元件** | docs/Frontend.md › 視圖 | 完成 | 2026-09-06 | **驗收通過：沒有新增任何元件**，只多一個 `graph/views.ts`（三種視圖 → `edge_types` ＋ 預設排版）與 sidebar 的一個 `<select>`。切視圖＝重打一次 API 換 `edge_types`，前端不自己篩邊。另外做了四件事：① `transform.ts` **聚合平行邊**（231 → 135 條，42% 是重疊的），細節收進 `data.detail` 不丟 ② 兩種邊靠亮度分（`contains` 暗細、`imports` 亮粗），不再多一種色相 ③ `ext:` 節點橘色菱形 ④ `parse_error` 紅色虛線邊框，**只改邊框**不動形狀顏色。前端 9 個測試（新增 3）。**沒做**：藏孤點（使用者選擇先不做，依賴圖裡仍有 63 個無邊節點）、hover 展開聚合細節 |

2.7 是這個階段的驗收點：**如果為了畫依賴圖得改動前端結構，就是模型設計有問題**，要在這裡發現。

---

### 階段 3 — zip 上傳

未開始。內容：zip 上傳，連同 zip-slip / zip bomb 防護。展開成 action list 等開工前再做。

---

### 階段 4 — 大圖可讀性

**已提前開工** —— 階段 2 收尾後跳過階段 3 先做了 4.1。

「1.11 只有 87 個節點就已經覺得不好看」，所以這階段不只是「大圖」問題，layout 與樣式本身也要重做。

| # | 項目 | 完成條件 | 對應文件 | 狀態 | 最後修改 | 備註 |
|---|---|---|---|---|---|---|
| 4.1 | 收合層級 | 「看多細」是查詢條件，不是新管線；前端不自己聚合 | docs/backend/graph.md › 收合 | 完成 | 2026-09-06 | `app/graph/views.py` 的 `collapse()` 與 `only_edges()`，寫成 `GraphDocument → GraphDocument` 純函式**不碰 networkx**（只要 `{nodes, edges}` 就算得出來，查詢層不必為它長胖）。**順序固定先收合再篩邊**——收合要靠 `contains` 算層級，先篩成 imports 視圖那些邊就沒了。API 加 `level` 與 `externals`（`full` / `grouped` / `hidden`；收到目錄層時 ext 會變成節點的大宗，所以需要自己的開關）。收進同一節點的 imports 記在 `properties.internal_imports`，不當自環丟掉；合成一個的外部套件名單留在 `properties.packages`。前端只多 `graph/levels.ts`（層級選項 ＋ 層級決定排版），**視圖切換停用**（`SHOW_VIEWS` 旗標，程式碼留著）——層級（看多細）與視圖（看哪種關係）是兩個軸，同時開太複雜。14 個測試。**實測本專案**：檔案層 98 節點，`app/models/__init__.py` 一個就吃掉 59 條入邊（畫面是蜘蛛網中心）；收到第 3 層剩 71 節點、63 條 imports，最忙的只剩 7 條入邊——「所有檔案都 import models」在目錄層本來就該是**一條**邊。**文件已同步**：`docs/backend/graph.md` 於 `38b086b` 補上收合規格；`docs/Frontend.md` 於 2026-09-06 補上「層級」小節，並一併改掉因收合而過時的敘述（視圖切換已停用、排版改跟著層級走、兩種邊改靠色相分且同寬、粗細門檻照收合後量級重訂、節點尺寸、測試數） |
| 4.2 | 畫布選型與 code splitting | 2D / 3D 定案；bundle 不因此爆掉 | docs/Frontend.md | 完成（後半條件未達成） | 2026-09-06 | **暫定採用 3D**（`App.tsx` 的 `renderer` 預設 `'3d'`）——目視驗收後認為沒問題，之後要優化再回來動。**2D 同時保留**，兩個畫布常駐、只切 `visibility`：3D 最大的收穫是驗證了「換掉的只有畫布那一層」，兩個實作並存就是那件事的活證據，用不到時再刪。**後半條件未達成**：bundle 2 MB（cytoscape 與 three.js 都在裡面），code splitting 未做，列為後續優化。規格已於 2026-09-06 寫進 `docs/Frontend.md` ›「畫布」：兩個畫布的逐項對照、型別編碼怎麼共用、兩個坑、空白畫面的診斷列 |
| 4.3 | hover 展開聚合的細節 | 聚合掉的東西在畫面上看得到 | docs/Frontend.md › 未定之處 | 待辦 | | 資料都已經在了，只差顯示的地方：`transform.ts` 的 `data.detail`（每一筆的名字與行號）、收合節點的 `properties.packages` 與 `properties.internal_imports`。**3D 的缺口更大**：餵進場景的 link 原本只帶 `source` / `target` / `type`。2026-09-07 補上 `count` 與線中點的數字精靈（門檻同 2D 的 `count > 1`，預設層級下 132 條邊有 45 條會標數字，最大 16），但 `detail` 仍沒傳進場景，hover 展開細節在兩個畫布上都還沒有 |
| 4.4 | 換層級不重打整條分析 | 切層級／視圖不重跑 ingest → scan → parse → resolve | docs/backend/api.md | 待辦 | | 現況：`App.tsx` 的 `useEffect` 監看 `[view, level, externals]`，任一個變就重打 `POST /api/analyze`，而收合是管線的**最後一步**，前面全部白跑。**實測本專案 125 節點 16–33 ms，所以現在感覺不到——這是規模問題，不是現在的問題**。做法：`store.py` 的 `save()` / `load()` 已現成（`load()` 走同一個 `build()`），分析回一個 id、另開端點只跑 `collapse()`；「前端一次拿全圖自己收合」**否決**，聚合是圖的運算。**需先定「分析結果存哪」**——1.8 當初刻意讓呼叫端決定以避開 `data/`，這一項會逼它定案 |
| 4.5 | layout 與樣式重做 | 在真實專案的圖上不糊成一團 | docs/Frontend.md | 部分完成 | 2026-09-06 | 優先度往後——**3D 表示法已經降低混亂程度**。已進 main（`dbd76b4`）：`contains` 換灰綠與 imports 的藍靠色相分開（不只靠明暗）、邊的 weight 併進 count 後粗細分三段、圖例改成畫出線條樣本、間距滑桿確定為「節點大小不變、間距變大」。**另一批卡在 `experiment/3d`**（節點與線一律縮小、線寬門檻照收合後的量級重訂、自動對焦加上限），`7553ae3` 自己註明「本來該進 main，之後再歸位」 |
| 4.6 | 目錄分群（compound node） | 用巢狀方框取代 `contains` 線；`transform.ts` 多產 `parent` 欄位，**元件不改** | docs/Frontend.md › 未定之處 | 待辦 | | 優先度往後，且**只能做在 2D 那個畫布上**——three.js 沒有巢狀方框的概念。4.2 暫定以 3D 為主但 2D 保留，所以這項仍然成立，只是價值降成「2D 這個對照組的可讀性」；2D 若哪天刪掉，這項一起作廢。要換來的是：`contains` 不再是線，畫面上剩下的線全部是 `imports`（真正的關係），「誰在誰底下」改用位置表達。另兩個代價：`breadthfirst` 不處理 compound，要換 `fcose` / `cose-bilkent`（**新依賴**）；與收合層級的軸重疊，會不會互相干擾要看過畫面才知道 |
| 4.7 | 孤點處理 | 無邊節點不佔版面，且數量在 sidebar 看得到 | docs/Frontend.md › 未定之處 | 待辦 | | 往後。依賴圖裡有 63 個節點一條邊都沒有；2.7 時已選擇先不做 |

這一階段的驗收點與 2.7 同一種：**可讀性靠查詢條件（層級、篩選、聚合）解決，不靠改前端結構**。如果為了畫得清楚必須動 `transform.ts` 與 `style.ts` 以外的地方，就是模型設計有問題。

**已知的驗收限制**：「大 repo 基準」在 2026-09-06 移到「之後」（原列為 4.2），所以 4.4 的效能與 4.5 的樣式目前只能在 119 個節點上判斷好壞——驗收時要知道基準是小圖。

---

### 實驗

開工時不是階段項目——沒有完成條件、也還沒決定採用，所以不進上面的表。

**3D 球體畫布** — `experiment/3d`、commit `7553ae3`、2026-09-06

**2026-09-06 目視驗收後暫定採用**，見 4.2。以下記錄保留：兩個坑與 bundle 的數字之後還會用到。

| 面向 | 內容 |
|---|---|
| 做了什麼 | 拿 `3d-force-graph` 1.80 / three.js 畫同一張圖，評估 3D 能不能解決「擠在一起」。`frontend/src/components/Graph3D.tsx` |
| **驗證了架構** | 換掉的只有畫布那一層。`transform.ts` 刻意不 import cytoscape，所以同一份 elements 兩種畫布都吃得下；`api/`、`Sidebar`、`App` 的查詢邏輯與整個後端**一行都沒改** |
| 有 | 球體依型別上色、面向鏡頭的文字精靈標籤、兩種邊分色、hover／點擊高亮鄰居、與 2D 同一組動態背景、間距滑桿改力導向的理想邊長 |
| 沒有 | 搜尋高亮、縮圖 |
| 代價 | bundle 656 kB → 2 MB，要採用得做 code splitting（4.2） |
| 踩到的坑 | ① 沒有資料時呼叫 `d3ReheatSimulation()` 會丟 `reading 'tick'`，那個例外**打斷 render loop**，之後放什麼資料都畫不出來且毫無線索 ② 條件渲染切換 2D／3D 會把畫布卸載重建，3D 重建一次就起不來——改成兩個都常駐、只切 `visibility`（不是 `display:none`，那會讓畫布尺寸歸零） |
| 未歸位 | 同一個 commit 夾帶了一批本該進 main 的 2D 調整，見 4.5 |

---

### 之後

| 項目 | 內容 |
|---|---|
| 大 repo 基準 | 找一個上千節點的真實專案跑通，記下節點／邊數與各層級的數字，當作可讀性的驗收基準。**2026-09-06 原列為 4.2，裁決移到這裡** |
| 語意縮放 | 放大才出現檔名、縮小只剩資料夾。會動到 `transform.ts` 與 `style.ts` |
| 圖模型第二階段 | `class` / `function` 層與 `calls` / `inherits` 邊 |
| 多語言 | TS |

