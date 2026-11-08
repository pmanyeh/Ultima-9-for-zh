# U9-CHT 翻譯資料管線（P7）

本目錄說明 P7 起的正式翻譯流程。**唯一可編輯的翻譯主檔是
`translation/zh-TW/*.jsonl`。** `translation/showcase/` 是凍結的 P6 歷史快照，
不可再編輯（測試會以雜湊檢查）。

## 檔案

| 路徑 | 用途 | 可提交 |
| --- | --- | --- |
| `translation/zh-TW/text.jsonl` | `text.flx` 字幕、NPC 對話、玩家回答 | 是（只有譯文、鍵、來源雜湊） |
| `translation/zh-TW/typename.jsonl` | `TYPENAME.FLX` 物品名稱 | 是 |
| `translation/zh-TW/books.jsonl` | `BOOKS-EN.FLX` 書本（目前 Unicode 執行期未支援） | 是 |
| `translation/schema/translation.schema.json` | 單筆紀錄的 JSON Schema | 是 |
| `translation/glossary/U9_TERMS.csv` | 譯名權威檔（欄位與狀態見 `translation/TRANSLATION_GUIDE.md`） | 是（只有詞、次數、位置） |
| `translation/TRANSLATION_GUIDE.md` | 翻譯規範 | 是 |
| `.local/p8a/U9_TERMS_REVIEW.tsv` | 權威檔審閱表，**含英文原句** | **否，僅限本機** |
| `translation/resource-capabilities.json` | 各資源家族能力表與證據 | 是 |
| `translation/sources.json` | 英文原始資源的預期 SHA-256 | 是（只有雜湊） |
| `.local/translation-work/` | 譯者工作集，**含英文原文** | **否，僅限本機** |
| `.local/qa/`、`.local/build/` | 驗證報告、建置輸出 | 否 |

## 紀錄格式

每行一筆 JSON，依（資源、entry ID）排序，欄位順序固定、UTF-8、LF。
主鍵為 `資源:entry_id`，例如 `text.flx:4041`、`TYPENAME.FLX:5290`。
不用顯示文字當主鍵，也不靠檔案行序。原文只以 `source_sha256` 及
`source_units` 識別；**英文原文永不進入 Git**。

- 換行是刻意、可見的 `\n`（書本為 `\r\n`）。管線**不會自動插入換行**；
  排版檢查只量測與回報。
- `status`：`untranslated`、`draft`、`review`、`approved`、`blocked`。
  `showcase-draft` 只用於遷移過來的 P6-S／P6-S2 草稿，等同 draft。
  狀態不會被自動提升。
- `terms`：本句應呈現的術語（術語表 `source` 欄），供術語檢查使用。
- `runtime_supported: false`：保留譯文，但永遠不進入執行期建置。

## 指令

以下指令需要合法持有的本機遊戲副本。請用環境變數或參數指定路徑，
不要把本機路徑寫進任何提交的檔案。

```powershell
$env:U9_GAME_DIR = "<合法遊戲安裝資料夾>"
$env:U9_CJK_FONT = "<NotoSansCJKtc-Regular.otf 2.004 的本機路徑>"

# 1. 匯出譯者工作集（僅限本機；含英文原文）
python scripts/export_translation_workset.py --output .local/translation-work `
  --only text.flx:4000-4300 --only TYPENAME.FLX:5290

# 2. 譯者編輯 .local/translation-work/*.work.jsonl 的 target / status / notes 等欄位

# 3. 匯回主檔（先 dry-run）
python scripts/import_translation_workset.py .local/translation-work/text.flx.work.jsonl --dry-run
python scripts/import_translation_workset.py .local/translation-work/text.flx.work.jsonl

# 4. 統一驗證（結構、來源、語言、術語、字型、執行期能力、排版）
python scripts/validate_translation.py

# 5. 確定性建置（純函式：輸入 → 輸出資料夾；不安裝）
python scripts/build_localization.py --profile development --output .local/build/zh-TW
```

匯入規則（任何衝突都會整批中止，主檔不變）：

- 工作集內重複的鍵 → 失敗。
- 來源雜湊與主檔或本機原文不符（SOURCE DRIFT）→ 失敗。
- 主檔在匯出後已被修改（`base_revision` 不符）→ 失敗，不覆蓋較新資料。
- 主檔沒有的鍵 → 需 `--create`。
- 狀態倒退 → 需 `--allow-status-regression`。
- 以非 approved 譯文覆蓋 approved 紀錄 → 需 `--force`。

## 驗證項目

| 類別 | 檢查 |
| --- | --- |
| 結構 | schema、重複鍵、無效資源／entry ID／狀態、非 untranslated 卻空白、UTF-8／Unicode、禁止的控制字元、確定性序列化 |
| 來源 | 資源雜湊、每筆來源雜湊與長度、缺少的 entry、鎖定 entry、別名 entry、佔位符、書本控制符號序列 |
| 語言 | U+FFFD、私用區字元、控制字元；簡體字形**僅作診斷**，不自動轉換 |
| 術語 | 同一來源多個 approved／keep 譯名、同一譯名對應多個來源、blocked 詞出現、標記術語未使用核准譯名、keep 的譯名不等於英文 |
| 字型 | 每個自訂字元都必須存在於固定雜湊的字型，否則列出 `U+XXXX`、字元、紀錄鍵 |
| 執行期能力 | 原生 pack 無法攜帶的字元、容量（16384 plans／8192 字元／16384 cache）、相同譯文共用同一 plan（僅提示）、資源家族不支援 Unicode |
| 排版 | 已量測幾何的表面計算行寬；結果為 PASS／WARNING／OVERFLOW／UNKNOWN-LAYOUT；最小禁則 |

建置設定檔：

| 設定檔 | 允許狀態 | 額外限制 |
| --- | --- | --- |
| `development` | draft、showcase-draft、review、approved | OVERFLOW 失敗；WARNING 僅警告 |
| `approved` | approved | WARNING 與 UNKNOWN-LAYOUT 也會失敗 |

`blocked` 與 `untranslated` 永不套用。

## 建置輸出（`--output` 資料夾，全部留在本機）

```text
static/text.flx, static/TYPENAME.FLX   # 只輸出有修改的資源
runtime/allowlist.u9ct                 # 由主檔產生的 U9CTP51 v2/v3 pack
glyph-manifest.json                    # 字元清單、分類、cache 需求、pack 雜湊
mutation-audit.json                    # 每個資源的變更 entry、未變更數量、意外差異
qa/qa-report.json, qa/layout-report.json
build-manifest.json                    # 所有輸入／輸出雜湊、計數、git commit
```

相同輸入會產生逐位元組相同的輸出。安裝到私人執行副本是另一個明確步驟，
不屬於建置指令。
