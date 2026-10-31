# Ultima IX: Ascension 繁體中文化 Master Plan

> 文件名稱：`ULTIMA_IX_CHT_MASTER_PLAN.md`  
> 專案代號：`U9-CHT`  
> 狀態：Draft v1.0  
> 目標：建立可重現、可維護、可持續擴充的《Ultima IX: Ascension》繁體中文化工具鏈與執行流程。  
> 核心策略：**Original Ultima IX + TITAN-based tooling + Japanese Oracle + Traditional Chinese localization pipeline**

---

## 0. Executive Summary

本專案不以「重製 Ultima IX 引擎」作為起點，也不先進行大量全文翻譯。

第一階段的唯一核心目標是回答以下問題：

> **原版 Ultima IX 是否能在可控、可重現的方式下，正確載入、渲染與排版繁體中文字？**

目前已知條件對中文化相對有利：

1. Ultima IX 的主要文字資源包含 `text.flx`、`misctext.flx` 等 FLX 檔案。
2. 主要文字格式存在寬字元／UCS-2 類型資料，可望避免傳統 DOS 遊戲常見的單位元組字碼限制。
3. 官方曾存在完整日文版，代表原始引擎曾具備東亞語系顯示路徑。
4. GitHub 上 `theGreyWanderer-uc/tgwUltima` / TITAN 已開始支援 Ultima IX 多種資料格式，可作為現代化工具鏈的基底。
5. `Fenyx4/UltimaPatcher` 等現有工具可作為版本、語言包及執行環境研究參考。
6. 其他東亞語系社群版本可作為「已有人成功」的外部證據，但不得依賴未授權內容建立公開發行物。

因此本專案採用：

```text
English Ultima IX
        │
        ├──────────────┐
        ▼              ▼
   TITAN-based      Japanese U9
     Tooling          Oracle
        │              │
        └──────┬───────┘
               ▼
       Text / Font / Renderer
               │
               ▼
        Traditional Chinese PoC
               │
               ▼
       Localization Pipeline
               │
               ▼
        Full CHT Translation
```

---

# 1. Project Goals

## 1.1 Primary Goals

本專案最終希望達成：

- 《Ultima IX: Ascension》遊戲內主要文字繁體中文化。
- 中文字型可正常顯示。
- 中文對話、UI、物品、書籍、系統訊息等可正常換行與排版。
- 可由工具自動匯出／匯入文字，而不是人工 hex edit。
- 建立權威術語表與翻譯資料庫。
- 建立可重現 build pipeline。
- 盡可能避免修改原始遊戲執行檔；若必要，修改應最小化、文件化、可驗證。
- 最終公開內容應只包含合法可再散布的工具、patch、翻譯資料、差分或建置腳本。

## 1.2 Non-Goals

第一階段不做：

- 不重製 Ultima IX 引擎。
- 不做高清材質重製。
- 不做 3D model 重製。
- 不做大型 gameplay patch。
- 不做完整語音中文化。
- 不在尚未驗證中文字形顯示前進行大量全文翻譯。
- 不把官方英文／日文遊戲資料、執行檔、影片、音訊直接提交 Git。

---

# 2. Engineering Principles

## 2.1 Evidence Before Assumption

任何以下結論都必須有實驗或 binary/data evidence：

- 某 FLX 檔案使用何種字串編碼。
- 日文版是否使用不同 renderer。
- 日文版是否修改 `u9.exe`。
- 字型來自資源檔或執行檔。
- 中文字元是否可直接寫入 `text.flx`。
- 換行是否由引擎處理或資源內預先排版。
- 字型寬度是否固定。
- 可否替換成 TrueType／FreeType 類方案。

禁止因為「看起來像」就直接設計大型架構。

## 2.2 Round-Trip First

任何資源格式的 importer 必須先證明：

```text
Original
  ↓ export
Intermediate Representation
  ↓ import
Rebuilt
```

在未修改內容的情況下：

```text
Rebuilt == Original
```

若無法 byte-perfect，至少要達成：

- 引擎可正常載入。
- entry count 相同。
- entry offset／size 邏輯正確。
- 未修改項目內容完全一致。
- 差異可解釋並被測試覆蓋。

## 2.3 Small PoC Before Full Localization

第一個成功條件不是「翻譯 1,000 句」。

而是：

> 把一段明確可見的英文，替換成 2～6 個繁體中文字，啟動遊戲並正確顯示。

例如：

```text
Honesty
```

→

```text
誠實
```

或選擇一段不影響存檔／邏輯的 UI 字串。

## 2.4 Preserve Original Data

任何工具不得直接覆蓋唯一原始檔。

必須採：

```text
original/
working/
output/
reports/
```

至少保留：

- 原始 hash。
- 修改前備份。
- 修改後 hash。
- build log。
- patch manifest。

---

# 3. Legal / Repository Boundary

## 3.1 May Be Committed

可提交 Git：

- 自製原始碼。
- 測試。
- 解析器。
- importer / exporter。
- build scripts。
- JSON schema。
- metadata。
- hash list。
- binary diff 工具。
- patch manifest。
- 自己撰寫的研究報告。
- 自己建立的翻譯。
- 不含受版權保護內容的測試 fixture。
- 人工建立的 minimal synthetic FLX fixture。

## 3.2 Must Not Be Committed

除非具有明確合法再散布權：

- `u9.exe`
- 原版 FLX
- 官方日文版 FLX
- 官方語音
- 官方影片
- 官方材質
- 官方字型
- 完整遊戲安裝目錄
- 從官方資源大量抽出的原始文字 dump

本機研究資料可放在：

```text
.local/
research-private/
oracle/
game/
```

並加入 `.gitignore`。

## 3.3 Recommended Repository Structure

```text
U9-CHT/
├─ README.md
├─ AGENTS.md
├─ ULTIMA_IX_CHT_MASTER_PLAN.md
├─ docs/
│  ├─ architecture/
│  ├─ research/
│  ├─ formats/
│  └─ reports/
├─ src/
│  ├─ U9Cht.Cli/
│  ├─ U9Cht.Core/
│  ├─ U9Cht.Flx/
│  ├─ U9Cht.Text/
│  └─ U9Cht.Patching/
├─ tests/
│  ├─ unit/
│  ├─ fixtures/
│  └─ integration/
├─ tools/
├─ schemas/
├─ translation/
│  ├─ glossary/
│  ├─ source/
│  └─ build/
├─ scripts/
├─ reports/
├─ output/
└─ .local/              # ignored
```

---

# 4. Reference Projects

## 4.1 Primary Tooling Reference

### `theGreyWanderer-uc/tgwUltima`

Role:

- Ultima format research base.
- TITAN tooling reference.
- FLX extraction／rebuild implementation reference.
- Existing Ultima IX format support source.
- Candidate upstream or fork base.

本專案開始時應：

1. 記錄 upstream URL。
2. 記錄使用的 commit SHA。
3. 建立乾淨 fork 或 vendor strategy。
4. 不直接魔改 upstream 而沒有 commit boundary。

## 4.2 Runtime / Language-Pack Reference

### `Fenyx4/UltimaPatcher`

Role:

- Ultima IX language pack 研究。
- 版本相容性研究。
- 日文版啟動方式參考。
- Patch sequencing 參考。

不假設它能直接解決中文字型。

## 4.3 Japanese Version as Oracle

官方日文 Ultima IX 是本專案最重要的研究 Oracle。

研究目的不是散布其內容，而是回答：

- 日本版與英文版 `u9.exe` 是否不同。
- 哪些 FLX 不同。
- 字型放在哪裡。
- 是否存在額外 CJK glyph resource。
- 日本版 string encoding。
- glyph lookup mapping。
- text width calculation。
- word wrap 行為。
- UI clipping 差異。
- 日本版是否使用不同 DirectDraw／GDI text path。
- 是否存在 locale-dependent branch。

---

# 5. Version Baseline

正式進行前，Agent 必須建立版本基準。

至少記錄：

```text
Game edition:
Language:
Installed patch:
u9.exe SHA-256:
text.flx SHA-256:
misctext.flx SHA-256:
typename.flx SHA-256:
books-*.flx SHA-256:
OS:
Compatibility settings:
Graphics wrapper:
```

建議研究基準：

```text
English Ultima IX
+ official / community accepted patch baseline
```

若使用 `1.19f` / `1.19h`：

必須先確認實際檔案來源與 patch dependency，
不得僅根據網路描述自動套用不明 patch。

---

# 6. Phase Overview

```text
P0  Preflight & Repository Bootstrap
P1  Game Asset Inventory
P2  FLX Text Round-Trip
P3  First Traditional Chinese Injection
P4  Japanese Oracle Differential Research
P5   High-Resolution Unicode Rendering PoC
P5.1 Persistent High-Resolution Unicode Renderer Integration
P6   Chinese Layout / Word-Wrap / Typography
P7  Localization Data Pipeline
P8  Coverage Expansion
P9  Translation QA
P10 Packaging & Release Engineering
```

每一 Phase 都有 Gate。

**Gate 未通過，不可擅自進入下一 Phase。**

---

# 7. P0 — Preflight & Repository Bootstrap

## Goal

建立乾淨且可重現的工程環境。

## Tasks

建立：

```text
README.md
AGENTS.md
.gitignore
docs/research/
docs/formats/
reports/
scripts/
tests/
```

紀錄：

- host OS
- compiler/runtime
- Python / .NET / Rust 等工具版本
- tgwUltima upstream commit
- UltimaPatcher reference commit
- game binary hashes

如果 fork TITAN：

```text
upstream = original tgwUltima
origin   = user fork
```

## Deliverables

```text
reports/P0_PRECHECK.md
reports/P0_HASHES.json
docs/research/reference-projects.md
```

## Gate P0

PASS 條件：

- Repo 可乾淨 clone。
- 不含任何官方遊戲檔。
- upstream commit 已固定。
- 本機遊戲路徑未硬編碼進 tracked source。
- 所有 private path 使用 config / env var。

---

# 8. P1 — Game Asset Inventory

## Goal

建立 Ultima IX 文字與字型資源全貌。

## Tasks

列出：

```text
static/
save/
sound/
speech/
video/
```

特別鎖定：

```text
text.flx
misctext.flx
typename.flx
books-*.flx
fonts / bitmap-like resources
UI-related FLX
language-specific files
```

對每個候選資源收集：

```text
filename
size
SHA-256
entry count
entry size distribution
encoding hypothesis
sample bytes
known consumer
```

不得把完整版權內容寫入 report。

最多只保存：

- 少量 hex header。
- entry metadata。
- hash。
- 自製摘要。

## Deliverables

```text
reports/P1_ASSET_INVENTORY.md
reports/P1_ASSET_INDEX.json
docs/formats/U9-FLX-NOTES.md
```

## Gate P1

必須明確回答：

- 哪些 FLX 含對話。
- 哪些含 UI。
- 哪些含書籍。
- 哪些含物件名稱。
- 哪些可能含字型。
- 哪些資源為 locale-specific。

---

# 9. P2 — FLX Text Round-Trip

## Goal

建立第一個可靠的 U9 text exporter / importer。

## Priority

第一優先：

```text
text.flx
misctext.flx
```

第二優先：

```text
typename.flx
books-*.flx
```

## CLI Design

建議：

```bash
u9cht inspect text.flx

u9cht text export text.flx \
  --output text.json

u9cht text import text.flx \
  --input text.json \
  --output text.rebuilt.flx

u9cht verify-roundtrip \
  text.flx \
  text.rebuilt.flx
```

JSON 可先使用：

```json
{
  "format": "u9-text-v1",
  "source_sha256": "...",
  "entries": [
    {
      "id": 0,
      "offset": 0,
      "raw_size": 0,
      "encoding": "ucs-2le",
      "text": "..."
    }
  ]
}
```

不要一開始加入過度複雜 schema。

## Tests

必須包含：

- empty string
- ASCII
- extended character
- null terminator
- odd byte count rejection
- malformed entry
- duplicate offsets
- zero-length entry
- rebuild alignment
- FLX entry table integrity

## Round-Trip Requirement

若：

```text
SHA256(original) == SHA256(rebuilt)
```

則標記：

```text
BYTE-PERFECT PASS
```

若不相同：

產生：

```text
reports/P2_ROUNDTRIP_DIFF.md
```

列出所有 binary differences 與原因。

## Gate P2

至少 `text.flx` 必須達到：

- exporter PASS
- importer PASS
- round-trip PASS
- game loads rebuilt file PASS

---

# 10. P3 — First Traditional Chinese Injection

## Goal

第一次讓原版 Ultima IX 顯示繁體中文。

## Important Rule

**只修改一筆。**

不要一次翻數百筆。

## Candidate Text

選擇：

- 主選單。
- 可立即觸發的 NPC 對話。
- 不影響 script branching 的純顯示文字。

例如：

```text
Honesty → 誠實
```

實際 entry 需由 inventory 決定。

## Experiment Matrix

測試：

```text
A. ASCII replacement
B. Latin extended character
C. Japanese character
D. Traditional Chinese BMP character
```

目的：

分離：

```text
archive問題
encoding問題
renderer問題
font問題
```

## Capture

每次執行保存：

```text
input resource hash
output resource hash
modified entry id
before text
after text
screenshot
game log
crash/no-crash
visual result
```

## Expected Outcomes

### Case A

繁中直接正常顯示。

→ 進 P6。

### Case B

繁中碼位被讀入，但顯示 □。

→ 字型缺 glyph。

### Case C

顯示錯誤 glyph。

→ glyph mapping / encoding 問題。

### Case D

crash。

→ string length / memory / parser / encoding 問題。

## Deliverable

```text
reports/P3_FIRST_CHT_POC.md
```

## Gate P3

至少確認以下之一：

```text
CHT rendering works
```

或：

```text
CHT encoding reaches renderer, glyph missing
```

必須能把問題定位到下一層。

---

# 11. P4 — Japanese Oracle Differential Research

## Goal

找出官方日文版的 CJK 顯示機制。

這是整個專案的核心研究 Phase。

## Inputs

本機合法持有：

```text
English installation
Japanese installation / language pack
```

禁止 commit。

## Static Differential

比較：

```text
u9.exe
text.flx
misctext.flx
typename.flx
books-*.flx
all language-specific assets
font-like assets
```

工具：

```text
SHA-256
file size
FLX entry diff
strings
PE import table
resource table
binary diff
Ghidra / IDA / Binary Ninja
```

## High-Value Questions

優先回答：

### Q1
日文 `u9.exe` 是否與英文版不同？

### Q2
若不同：

- import table 是否增加 GDI font API？
- 是否有 `CreateFont*` / `TextOut*` / `GetTextExtent*` 類 API？
- 是否有日本 codepage / locale function？
- 是否新增大量 glyph table？

### Q3
若相同：

表示 CJK 支援可能：

- 原本就在 engine。
- 由 language resource 驅動。
- 由 font file 驅動。

### Q4
日文文字實際 encoding 是：

```text
UCS-2LE
Shift-JIS
custom index
mixed
```

### Q5
日文字型從哪裡來？

### Q6
引擎如何量測字串寬度？

### Q7
英文與日文版換行算法是否不同？

## Binary Trace Strategy

只有 static diff 無法回答時才動態 trace。

目標：

```text
text FLX read
     ↓
string decode
     ↓
layout
     ↓
glyph lookup
     ↓
draw
```

可在 Windows debugger 中：

- breakpoint file access
- breakpoint memory read
- breakpoint GDI / DirectDraw functions
- watch selected text buffer
- trace call stack

禁止一開始全域亂 trace。

## Deliverables

```text
reports/P4_JP_ORACLE_DIFF.md
docs/research/U9_TEXT_RENDER_PIPELINE.md
docs/research/U9_FONT_PIPELINE.md
```

## Gate P4

必須至少定位：

```text
string decoding function
```

以及下列其中之一：

```text
font resource
glyph lookup
text drawing function
```

---

# 12. P5 — Font / Glyph Rendering Solution

## Goal

選出最小侵入的繁中字型方案。

## Strategy Priority

依優先順序：

### Strategy A — Reuse Native CJK Path

若日本版 renderer 可直接：

- 換 glyph 資源。
- 擴 glyph table。
- 使用繁中字型。

則優先使用。

### Strategy B — Extend Existing Bitmap Font

若 U9 使用 bitmap font：

建立：

```text
Unicode code point
→ internal glyph ID
→ glyph bitmap
```

並擴充：

```text
glyph atlas
glyph metadata
width table
```

### Strategy C — Runtime Font Hook

只有 A/B 不可行時考慮。

可能方案：

```text
hook U9 text renderer
→ intercept UCS-2
→ render via FreeType / DirectWrite / GDI
→ composite into original surface
```

這會增加：

- compatibility risk
- graphics wrapper risk
- anti-aliasing mismatch
- fullscreen risk
- clipping complexity

因此不是第一選擇。

## Font Scope

PoC 不需要完整 CJK。

先建立：

```text
100～500 glyph subset
```

來源由實際測試文字決定。

後續 build pipeline 再依翻譯 corpus 自動：

```text
collect unique code points
→ build subset
→ pack glyph atlas
```

## Gate P5

畫面必須能顯示至少：

```text
天地玄黃
不列顛尼亞
誠實
慈悲
英勇
正義
犧牲
榮譽
靈性
謙遜
```

實際詞彙可調整。

---

## 12.1 P5.1 — Persistent High-Resolution Unicode Renderer Integration

2026-10-31 明確授權。既有 P5 已完成 **HIGH-RES UNICODE POC PASS**，但其
debugger-driven 單幀結果不是持續可遊玩 runtime。P0～P5 報告及本章原始
P5／P6 目標保留為歷史證據，不重新解讀或重做。

P5.1 僅整合已證實的 `text.flx` 字幕路徑：Win32/x86 launcher 在 suspended
game 中載入 runtime，收到 READY 後才正常執行；以經驗證、可還原的最小
runtime hooks 保留 UTF-16 身分、原生 Latin、字形快取及最終 backbuffer 合成。
正常執行不得依賴 debugger、debug registers、breakpoints、手動 EIP 操作、
外部逐幀記憶體存取或擷取暫停；不得在磁碟修改 `u9.exe`。

### Gate P5.1

必須驗證：正常 launcher／READY-FAIL handshake、自動安裝與初始化失敗還原、
多個字幕身分及世代失效、兩條一致的字寬路徑、持續中文與原生英文分流、
800×600／1600×1200 直接對應輸出尺寸的灰階字形快取、逐次 Lock 的安全合成、
surface／device 變化處理、focus／fullscreen 行為、正常退出與重複啟動、
至少五個受控字幕案例、15 分鐘持續測試及約 60 分鐘長時間測試。
原有 65 個測試及新增 native／synthetic 測試必須全數通過。

遊戲資產、字型、截圖、產生的 runtime binaries 與本機路徑均不得提交。
若生命週期或穩定性尚未通過，標記 PASS WITH LIMITATIONS／BLOCKED 並保留
未驗證項目。**P6 不在本次授權範圍；不得自動進入換行、禁則、排版或資源擴張。**

2026-11-01 checkpoint：依使用者指示暫緩剩餘 runtime 驗證。
P5.1 為 **PASS WITH LIMITATIONS，Gate 尚未完整通過**；保留上述通過標準，
不將未完成的約60分鐘長測、完整啟閉輪次或全螢幕測試列為 PASS。
證據與限制見 `reports/P5_1_PERSISTENT_RENDERER.md`。P6 仍未授權。

---

# 13. P6 — Chinese Layout & Word-Wrap

## Goal

解決「能顯示中文」之後最常見的真正難題。

## Problems

中文沒有英文空白 word boundary。

因此需要確認 U9 原始 layout 行為：

```text
wrap at space
wrap at glyph
hardcoded line breaks
pixel width
character count
```

## Required Behaviors

繁中至少要：

- 任意漢字間可換行。
- 標點避免錯誤置於行首。
- 開括號避免孤立於行尾。
- 英數單字盡量不拆。
- 不超出 UI clipping rectangle。
- dialog box 高度不足時行為可控。

## Minimum Kinsoku Rules

至少處理：

禁止行首：

```text
，。、！？；：）》」』】〕〉
```

禁止行尾：

```text
（《「『【〔〈
```

先做 minimal rules，不必一開始實作完整 Unicode line breaking。

## Test Corpus

建立 synthetic cases：

```text
純中文
中英混排
中文+數字
中文+人名
中文+符號
超長句
單字超長
多行書籍
選單
NPC dialogue
```

## Gate P6

至少：

- NPC 對話無明顯 clipping。
- UI label 可接受。
- 長句自動換行。
- 中英混排可正常。
- 遊戲不因字串長度 crash。

---

# 14. P7 — Localization Data Pipeline

## Goal

讓翻譯流程與遊戲格式解耦。

## Canonical Translation Store

不要直接把 FLX dump 當翻譯主檔。

建議：

```json
{
  "key": "text.flx:00123",
  "source": "Honesty",
  "target": "誠實",
  "status": "approved",
  "context": "...",
  "speaker": null,
  "notes": null
}
```

## Status

建議：

```text
untranslated
draft
review
approved
blocked
```

## Glossary

建立：

```text
translation/glossary/U9_TERMS.csv
```

欄位：

```text
source
target
category
status
reference
notes
```

Category：

```text
person
place
virtue
item
spell
organization
monster
UI
system
```

## Authority Priority

建議：

```text
1. 台灣官方譯名／舊版合法中文資料
2. Ultima 系列既有台灣慣用譯名
3. 專案權威術語表
4. 英文原文語義
5. 社群翻譯參考
```

如果存在使用者持有的官方中文手冊：

- 可本機整理。
- 不 commit 完整掃描內容。
- Git 只保存專案整理出的必要詞彙及引用位置資訊。

## Build

```text
canonical translations
        ↓
validation
        ↓
per-resource build
        ↓
FLX importer
        ↓
output resources
```

---

# 15. P8 — Coverage Expansion

順序建議：

```text
1. UI / system
2. virtues / terms
3. NPC dialogue
4. item names
5. books
6. journals
7. miscellaneous messages
8. optional speech subtitle alignment
```

每增加一個新 resource type：

必須先：

```text
inspect
round-trip
single-entry edit
runtime verification
```

禁止因為格式「看起來很像」就共用 parser。

---

# 16. P9 — Translation QA

## Automated QA

檢查：

```text
missing target
duplicate key
invalid Unicode
control character mismatch
placeholder mismatch
format token mismatch
unexpected newline
oversized string
unmapped glyph
```

如果原文有：

```text
%d
%s
\n
special marker
script token
```

必須保持語義一致。

## Runtime QA

建立場景清單：

```text
new game
main menu
conversation
choice menu
inventory
journal
book
save/load
combat message
shop
quest state
ending-critical dialogue
```

每次 release candidate 至少跑 smoke suite。

---

# 17. P10 — Packaging & Release Engineering

## Goal

最終使用者不需要研究 FLX。

理想流程：

```text
Installer / patcher
      ↓
detect supported U9 version
      ↓
verify hashes
      ↓
backup
      ↓
apply resources / binary patches
      ↓
verify output
      ↓
launch
```

## Distribution

優先：

```text
translation data
+ generated patch
+ installer
```

而不是完整修改後 FLX。

若 binary patch 可行：

```text
xdelta
bsdiff
custom patch manifest
```

需考慮不同合法發行版 hash。

## Uninstall

一定要：

```text
restore backup
```

或支援：

```text
verify → revert
```

---

# 18. Testing Architecture

## Unit Tests

FLX parser：

```text
entry table
offset
length
alignment
encoding
termination
bounds
```

## Integration Tests

```text
fixture
→ export
→ import
→ verify
```

## Golden Tests

可以使用自製 synthetic FLX。

不得把原版資源作為公開 fixture。

## Runtime Tests

可以透過：

- human checklist
- screenshot evidence
- automated launcher
- log capture

初期不要求遊戲自動化。

---

# 19. Agent Rules

## Agent MUST

- 先讀 `ULTIMA_IX_CHT_MASTER_PLAN.md`。
- 先讀 `AGENTS.md`。
- 每個 Phase 只做授權範圍。
- 完成後產生 report。
- 發現格式假設錯誤立即停止擴張。
- 所有 binary 結論附 evidence。
- 保留 hashes。
- 不提交 copyrighted assets。
- 不用「大概」取代測試。
- 不在 Gate 未通過時自動進下一 Phase。

## Agent MUST NOT

- 自動下載盜版遊戲。
- 自動把官方日文版放進 repo。
- commit user's local paths。
- 大量修改 `u9.exe` 後才測。
- 一開始實作完整 FreeType overlay。
- 一開始翻完整 text corpus。
- 把未知 binary bytes 當 harmless padding。
- 為了 byte-perfect 而忽略 runtime correctness。

---

# 20. Stop Conditions

出現以下情況 Agent 應停止並回報：

```text
1. Game version / hash 不符合目前支援基準。
2. text.flx 解析結果與文件假設衝突。
3. Round-trip 破壞 entry table。
4. 修改單一字串即造成 crash。
5. Japanese / English binary 無法建立可信 diff。
6. 需要提交或散布 copyrighted assets 才能繼續。
7. 需要大幅 patch u9.exe 才能完成尚未驗證的假設。
8. 字型來源尚未定位卻準備實作新 renderer。
```

---

# 21. Recommended First Execution Batch

第一批只執行：

```text
P0
+
P1
+
P2 的 text.flx
```

**不要執行 P3 以後。**

目標是得到：

```text
reports/P0_PRECHECK.md
reports/P1_ASSET_INVENTORY.md
reports/P2_ROUNDTRIP_DIFF.md
```

如果 P2 byte-perfect：

再由人類批准：

```text
Proceed to P3
```

---

# 22. First Agent Instruction

可直接交給 Agent：

```text
Read in order:

1. AGENTS.md
2. ULTIMA_IX_CHT_MASTER_PLAN.md

Execute ONLY:

- P0 — Preflight & Repository Bootstrap
- P1 — Game Asset Inventory
- P2 — FLX Text Round-Trip, limited to text.flx

Do NOT begin P3.

Important constraints:

- Never commit copyrighted Ultima IX game assets.
- Never commit local absolute paths.
- Record SHA-256 hashes for all locally inspected binaries/resources.
- Pin the exact upstream tgwUltima/TITAN commit used.
- Prefer extending or reusing proven TITAN FLX code instead of rewriting formats without evidence.
- For text.flx, establish the encoding empirically.
- Build export/import support and attempt an unchanged round-trip.
- If rebuilt bytes differ, produce a structured binary-difference report instead of hiding or normalizing the differences.
- If the rebuilt FLX can be runtime-tested safely, record whether Ultima IX accepts it.
- Stop after producing the P0/P1/P2 reports.

Required final response:

1. Overall PASS / BLOCKED.
2. Files created or changed.
3. Tests executed and exact results.
4. text.flx round-trip result.
5. Any format discoveries that differ from the Master Plan assumptions.
6. Blockers.
7. Recommendation for whether P3 should be authorized.

Do not proceed to P3 without explicit human approval.
```

---

# 23. Success Definition

本專案的第一個真正 milestone 不是完成翻譯。

而是：

```text
Original Ultima IX
       ↓
controlled text export/import
       ↓
one Traditional Chinese string
       ↓
correct glyph rendering
       ↓
correct Chinese wrapping
       ↓
reproducible build
```

一旦這條 pipeline 成立，後面的工作就從：

> 「逆向工程是否可行？」

轉變為：

> 「翻譯內容與 QA 的規模化工程。」

這才是進入完整中文化的正確時間點。

---

# 24. Proposed Milestones

```text
M0  Repository clean baseline
M1  text.flx round-trip
M2  first CHT code point reaches renderer
M3  first visible Traditional Chinese glyph
M4  usable Chinese dialogue wrapping
M5  canonical translation database
M6  dialogue/UI coverage
M7  books/items/system coverage
M8  full-game QA candidate
M9  reproducible public patch
```

---

# 25. Current Recommended Decision

目前最推薦的工程路線：

```text
DO:
Original U9
+ TITAN-based toolchain
+ Japanese-version Oracle
+ minimal binary intervention
+ canonical translation database

DO NOT:
Full engine rewrite
Full renderer rewrite before evidence
Mass translation before PoC
Manual hex-edit driven workflow
```

第一個真正要完成的工作是：

> **讓 `text.flx` 可以可信地 export → import → round-trip。**

完成之後，才授權：

> **P3：第一筆繁體中文注入。**

