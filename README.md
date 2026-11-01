# U9-CHT — Ultima IX 繁體中文化

執行依據為 [AGENTS.md](AGENTS.md) 與 [Master Plan](ULTIMA_IX_CHT_MASTER_PLAN.md)。
初始批次為 P0、P1、P2（限 `text.flx`）；後續已明確授權 P3、P4 診斷及
P5-0 日文執行檔重建／靜態差異研究，以及 P5 高解析度 Unicode PoC。
2026-10-31 已明確授權 **P5.1 — Persistent High-Resolution Unicode Renderer
Integration**；**P6 仍未授權**，各階段須通過 Gate。

目前狀態：**P5-0 PASS（靜態 CJK 機制確認；原報告為 PASS WITH LIMITATIONS）**，
**P5 HIGH-RES UNICODE POC PASS（受控單幀）**。P5 已驗證保留 UTF-16 身分、
原生英文與高解析度中文字形混排，並完成 800×600／1600×1200 比較；它仍是
debugger-driven、有界單幀實驗，**不是持續執行的可遊玩 renderer**。
P5.1 的工作是將既有成果整合為正常啟動、持續運作、可還原的 x86 runtime，
不重做 P0～P5 研究，也不展開中文換行、排版或翻譯覆蓋。
詳見 [P5 報告](reports/P5_HIGHRES_UNICODE_POC.md) 與
[P5.1 Gate](ULTIMA_IX_CHT_MASTER_PLAN.md#121-p51--persistent-high-resolution-unicode-renderer-integration)。

2026-11-01 P5.1 checkpoint：持續 renderer 已實作，Python72/72、native5/5
通過；六筆字幕、兩種解析度與超過15分鐘的實際合成活動已有證據。
依使用者指示暫緩其餘長測、完整啟閉輪次及全螢幕驗證，狀態為
**PASS WITH LIMITATIONS；Gate 尚未完整通過，P6 未授權**。
詳見 [P5.1 實作及驗證報告](reports/P5_1_PERSISTENT_RENDERER.md)。

後續已重新授權 event-driven validation，取代時間型 soak：兩次短啟閉覆蓋
800×600／1600×1200，另加必要 lifecycle／fullscreen smoke。重判正在進行；
目前 final-build 800×600 正常退出通過，Python78/78、native5/5 通過。
完整事件矩陣通過前，仍不將 P5.1 列為完整 PASS，也不執行 P6。

初始批次狀態（2026-10-29）：P0～P2 **PASS WITH LIMITATIONS**。
英文 `text.flx` 未修改往返為 **BYTE-PERFECT PASS**，獨立遊戲副本的開場
runtime 冒煙測試通過。後續 P3 已完成單筆 ASCII／BMP 診斷：ASCII `TEST!!`
正常顯示；U+4E2D「中」顯示錯誤符號，分類為 **ENCODING / MAPPING FAILURE**。
該 P3 批次依停止條件未執行 changed-length runtime 測試，也未進入 P4。
私人副本已還原。
詳見 [P0](reports/P0_PRECHECK.md)、[P1](reports/P1_ASSET_INVENTORY.md)、
[P2](reports/P2_ROUNDTRIP_DIFF.md)、[P3 報告](reports/P3_FIRST_CHT_POC.md)。

P4-C2 已於 2026-10-30 完成：`WideCharToMultiByte(CP_ACP)` 的容量不足問題，
以及後續將 `A4 A4` 分別做 byte-width／bitmap lookup 的路徑均已確認。
詳見 [P4 報告](reports/P4_RENDER_PATH.md)。私人資源副本已還原，追蹤工具
會檢查已驗證的視窗模式設定。

P5-0 已完成 **JP CJK PATH CONFIRMED（靜態）**：固定版 Octodiff 在保留
hash validation 下接受現有英文 basis，於忽略目錄重建日文執行檔。已定位
容量查詢、Shift-JIS 配對、GDI 字形快取及原生 bitmap 分流；分類為 J2，
不能只改 CP932→CP950。該批次未啟動日文執行檔、下載語言包或實作 renderer。
詳見 [重建報告](reports/P5_JP_PATCH_RECONSTRUCTION.md)、
[差異報告](reports/P5_JP_BINARY_DIFF.md)、
[CJK 機制](docs/research/U9_JP_CJK_IMPLEMENTATION.md)。

需要 Python 3.12 以上與 Git。工具使用 Python 標準函式庫及一份附 MIT 授權的
TITAN reader 原始碼，不需安裝 TITAN 的其他套件。

```powershell
python -m unittest discover -s tests -v
# 先在目前終端設定 U9_GAME_DIR 為合法安裝資料夾，再執行：
python scripts/preflight.py --baseline reports/P0_HASHES.json --output .local/preflight-new.json
python -m u9cht inspect "$env:U9_GAME_DIR/static/text.flx"
python -m u9cht text export "$env:U9_GAME_DIR/static/text.flx" --output .local/working/text-new.json
python -m u9cht text import "$env:U9_GAME_DIR/static/text.flx" --input .local/working/text-new.json --output .local/output/text-new.flx
python -m u9cht verify-roundtrip "$env:U9_GAME_DIR/static/text.flx" .local/output/text-new.flx
```

也可使用 `--game-dir` 指定路徑。預設輸出 `.local/preflight.json`；重跑請以
`--output .local/preflight-next.json` 指定新檔，工具拒絕覆寫既有檔案。
輸出僅包含相對檔名、大小、SHA-256 與狀態，不匯出遊戲文字。
未設定路徑、未提供基準或雜湊不同時，preflight 回傳碼為 **2（BLOCKED）**。
指定的本機基準匹配時回傳 0；這只證明檔案與本批次相同，不認證官方修補版本。
實際 patch 名稱目前 UNKNOWN；請勿直接推定為 1.19f／1.19h。
未設定 `U9_GAME_DIR` 時，測試套件會明確略過本機素材整合測試。

遊戲與研究素材留在外部安裝路徑或 `.local/`、`game/`、`oracle/`、
`research-private/`、`private-data/`。以上目錄及本機設定均已忽略。
`config.example.json` 只示範欄位，檢查工具目前只讀取 CLI／環境變數。
請勿提交官方資源、完整抽取文字或含本機絕對路徑的設定。

上游採 **固定 commit 的本機參考 clone**，只 vendor 一份 MIT container reader，
保留原文授權。writer 另加保留原始佈局的實作與測試，不安裝整套依賴。
版本與重現方式見 [上游參考](docs/research/reference-projects.md)。
