# ax-workflow — 一鍵初始化（skills + runtime + 自動歸檔）

技能(commands/) 是提示層；完整工作流還需 runtime（recall client / vault / autoscan）。
`initialize.sh` 一次裝好全部，**可重複執行**（已裝則檢查更新、不重裝、不重生金鑰）。

## 一次跑到完（一般使用者只敲這個，最多輸入一次密碼）
```bash
git clone <this-repo> ~/.ax-marketplace \
  && bash ~/.ax-marketplace/plugins/ax/initialize.sh
```
做完：runtime→`~/.ax-workflow/bin`、config→`~/.config/ax-workflow/env`、shim(`vault`/`ax_recall`)→`~/.local/bin`、
**本人 age keypair**（私鑰永不外流）、每日 09:15 自動歸檔（mac=launchd / linux=cron）、既有機密 baseline 入庫。
最後印出你的公鑰 → 貼給管理員即可（公鑰可公開、非密碼）。

## 套件不含任何組織設定
工作流模式對所有組織相同。中央 recall server 是**執行時參數**、非內建：
```bash
bash initialize.sh --server http://127.0.0.1:7654   # 有中央 KB 才帶；不帶＝本機獨立模式
```
其他旗標：`--no-schedule`（不排程）｜`--no-plugin`（不動 claude plugin）｜`--no-deps`（deps 已備妥）。

## 三種同步邊界
- **共用·同步**：skills + runtime → git pull / plugin update（全員一致）
- **中央·共讀寫**：（若有）團隊 recall/ingest KB —— 由 `--server` 指定，不寫死
- **私有·永不同步**：`~/.ax-vault` age 私鑰、憑證、seen-ledger、私有索引 → 各人本機

## 重複執行＝更新
再跑一次 `initialize.sh`：git pull 最新版 → 刷新 runtime → 保留金鑰 → 重載排程。安全冪等。
