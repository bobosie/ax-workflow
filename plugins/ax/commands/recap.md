---
description: "AX Recap — 把本次工作的經驗教訓收進知識庫（memory + lessons-learned，符合條件時自動產出 playbook），讓下次用 Recall 就查得到。觸發語：「收工」「收尾」「記下來」「整理一下」「經驗教訓」「避免再犯」「以後記得」「下次不要再」「這個以後還會用到」「覆盤」。適合：完成一段開發／修完 bug／踩到新坑後的收尾覆盤。"
argument-hint: "[可選：聚焦主題，如 'Meegle 搜尋' 或 'K8s 部署']"
---

# /收 — Session 經驗收割

## 🔍 Step 0 — 先 Recall（AX 全技能通則，最高優先）
動手前、或過程中一遇到**不確定／錯誤／卡關／要做技術決策**：**第一步先 `ax:recall "<關鍵字>"`**——查團隊知識庫（過往經驗／解法）＋ reference／playbook／SOP。命中就沿用或以它為基礎調整。
> ⚠️ recall 命中率約 60%@5：**「查無」≠「沒做過」**（知識庫本身可能就漏），recall 是**輔助參考、不是判斷有無先例的依據**。**「查遍」的定義＝memsearch top-5 ＋（涉本專案時）掃一次 `doc/lessons-learned/` ＋ 最多換 1 次關鍵字**；到此仍無就自己想，別無限 retry、也別因查無就斷定「首次遇到」。

你需要從本次對話中收割所有值得保留的經驗，轉化為未來可複用的知識資產。

**核心原則**：「記錄經驗教訓」= **memory + lessons-learned**；跨裝置/多環境同步為個人選配。

**自主收割（不等使用者確認）**：直接把本次 session 的經驗收割完、寫入、同步——包含**自動命名並產出 skill / playbook**。經驗與教訓的**累積**優先於逐項確認；靠查重（Phase 2.1）避免記錯 / 記重，而不是靠使用者把關。摘要表格是「事後記錄」不是「確認閘門」——輸出後直接往下做，不停下等回覆。

---

## Phase 1：回顧掃描

回顧整段對話，提取以下四類素材。如使用者給了 `$ARGUMENTS` 主題，聚焦在那個主題；否則全面掃描。

<!-- HARVEST-SHARED v1 -->
收割分析框架（互動 /收 與背景收割路徑必須一致；改一邊要同步另一邊，兩邊 drift 應以可觀測方式偵測）：
- 四類素材：Pitfalls（走錯路再修正：錯誤做法→正確做法→為什麼錯）、Patterns（3 步以上、未來會重複的工作流）、References（新發現的關鍵參數/路徑/ID/對照表）、Feedback（使用者明確糾正或確認的偏好）。只留真正可複用的，純日常操作不記。
- 品質分級路由：只有 verified（親眼看它做對事——跑過測試/打過 endpoint/看過畫面/DB 查證）才寫 feedback；runs/推論/未驗證一律寫 reference 並在 provenance 標實、不得升級為 feedback；一次性狀態（pod 重啟中、DB 剛 migration）不是可複用經驗、不記。
<!-- /HARVEST-SHARED v1 -->

> 上面 `HARVEST-SHARED` 區塊是兩條收割路徑的**權威共用定義**，兩邊逐字一致。下方 1.0~1.4 是互動情境的細節與範例；改動「四類定義／品質分級」時**必須同步改背景收割路徑（若你的環境有 headless 收割 agent / processor）內同名區塊**，並以可觀測方式偵測 drift。

### 1.0 先掃當天異動的 stash（最先做，重要）
本次對話可能只是 `/resume` 或某任務的延續——當天真正的工作量，常在「先前 Session 離開前 `/stash` 的檔案」裡，不在當前對話。**Phase 1 一開始就先掃當天異動的 stash 目錄（`${AX_STASH_DIR:-$HOME/.ax/stash}`，未設 env 用預設，用前 `mkdir -p`），把它的內容也當成收割素材**，不要只看當前 session 對話：

```bash
STASH_DIR="${AX_STASH_DIR:-$HOME/.ax/stash}"
find "$STASH_DIR" -maxdepth 1 -name '*.md' -newermt "$(date +%Y-%m-%d) 00:00:00" ! -name README.md -print
```

- 逐一讀取當天異動的 stash，把其中的踩坑/模式/參數/修正一併納入下面 1.1~1.4。
- **務必查重**：stash 可能在先前 Session 已部分 `/收` 過，只補「還沒進 memory」的缺口（仍走 Phase 2.1 比對既有 memory，找真正未記錄的部分，別重覆記）。

### 1.1 踩過的坑（Pitfalls）
找出對話中**走錯路再修正**的地方：
- 用了錯誤的參數/欄位名/API → 後來改對了
- 時間算錯、路徑寫錯、邏輯搞反
- 試了 A 方案失敗 → 改 B 方案成功
- 使用者糾正了你的做法

每個坑記錄：**錯誤做法 → 正確做法 → 為什麼會錯**（品質分級路由見上方 `HARVEST-SHARED` 區塊：verified 才寫 feedback）。

### 1.2 發現的模式（Patterns）
找出**最終成功的工作流程**：
- 完整的操作步驟（先做什麼、再做什麼）
- 必要的前置檢查
- 關鍵的判斷點和分支

### 1.3 關鍵參數（References）
收集對話中出現的：
- ID、Key、URL、帳號對照表
- 欄位名稱對照
- 環境配置、指令模板

### 1.4 使用者修正指示（Feedback）
找出使用者**明確糾正或確認**的行為偏好：
- 「不要這樣做」「你誤會了」→ 記錄為 feedback
- 「對，就是這樣」「OK」→ 如果做法非直覺，也記錄

### 輸出：經驗摘要（事後記錄，不等確認）

整理完後，輸出摘要表格作為**執行記錄**（讓使用者事後看得到收了什麼），然後**直接進 Phase 2 產出，不停下等確認**：

```
## 本次 Session 經驗摘要

| # | 類型 | 內容 | 產出 |
|---|------|------|---------|
| 1 | 坑 | {簡述} | feedback memory |
| 2 | 模式 | {簡述} | reference memory + proto-skill |
| 3 | 參數 | {簡述} | reference memory |
| 4 | 修正 | {簡述} | feedback memory |

（以上為本次收割清單，已直接寫入）
```

輸出摘要後**立即**進入 Phase 2，不等使用者回覆。

---

## Phase 2：分類產出

### 2.1 查重

產出前**必須**先檢查是否已有相關記憶：

```bash
# 掃描現有 memory 檔名（Claude Code 標準 auto-memory 位置）
MEM_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(pwd | sed 's#/#-#g')/memory"
ls "$MEM_DIR"/feedback_*.md
ls "$MEM_DIR"/reference_*.md
```

- 已有相關記憶 → **更新**，不建新檔
- 沒有 → 新建

### 2.2 寫 feedback memory

每個「坑」和「修正指示」寫成 feedback memory（**僅限 1.5 判定為 verified 的結論**；未驗證的降級寫 reference 並標 `未驗證`）：

```markdown
---
name: {簡短標題}
description: {一行描述，具體到未來能判斷相關性}
type: feedback
source: 收
---

{規則本身}

**Why:** {為什麼會犯這個錯 / 使用者為什麼這樣要求}

**How to apply:** {什麼情境下要套用這個規則}
```

### 2.3 寫 reference memory

每個「關鍵參數」和「對照表」寫成 reference memory：

```markdown
---
name: {簡短標題}
description: {一行描述}
type: reference
source: 收
---

{對照表、參數、連結、指令模板}
```

### 2.4 寫 lessons-learned

如果本次 session 涉及**具體的程式碼修改或問題排查**，寫入對應專案的 `doc/lessons-learned/`。

**品質標準（四段必備）**：

1. **問題描述**：現象 + 錯誤訊息（可複製貼上的）
2. **根本原因**：不只「改了什麼」，而是「為什麼會出錯」
3. **解決方案**：具體改了哪些檔案、哪些行、改了什麼
4. **驗證方式**：怎麼確認修好了（含指令或測試步驟）

缺任何一項 → **自己從對話中補齊**，不丟給使用者補。

### 2.5 判斷是否升級成 proto-skill

符合以下**任一條件**即應升級：

- [ ] 工作流有 **3 步以上**的明確步驟
- [ ] 涉及**特定工具/環境**的操作知識（MCP、K8s、Jenkins 等）
- [ ] 未來**很可能會重複**做類似的事
- [ ] 對話中出現過「這個流程蠻複雜的」「以後還會用到」等語句
- [ ] 已有相關的 feedback/reference 散落在多個 memory 裡，可以整合

符合 → 進 Phase 3
不符合 → 跳到 Phase 4

---

## Phase 3：提示詞產出

### 3.1 自動命名（依既有命名慣例，不問使用者）

先掃既有 prompts 檔名學慣例，然後**自己訂一個別名，直接產出，不停下來問**：

```bash
ls "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/prompts/"*.md   # 學既有命名慣例（領域前綴 + kebab-case）
```

**命名規則**：
- 領域前綴 + 動作 / 主題，如 `web-debug`、`k8s-deploy`、`db-migrate`、`<服務名>-*`
- 全小寫、連字號分隔、精簡可辨識
- 名稱能讓未來的自己一眼判斷「這在講什麼、什麼時候該讀」
- **排除業務實體命名**：若別名會成為「人類識別某業務實體的唯一代號」（版型別名如綜合版6、廳名、站台代號、品牌名）——這類是**業務端決定、非技術命名**，不自己編，改在最終報告標「別名待確認」用暫定名先寫入（原則：業務實體別名須由業務端確認，技術端不自行編造）。只有**技術 playbook 檔名（操作流程）**才自動命名。
- **同名碰撞判斷**：撞到既有 playbook 名時先確認「是否真的同一主題」——判準：既有 playbook 第一行描述能否完整涵蓋新素材的使用情境。能 → 更新補充；不能（相同領域但不同面向）→ 改用更精確的新別名建新檔，**不硬塞進舊 playbook 污染其焦點**。

**自己訂名、直接產出，不問使用者。**（唯一例外：真的無法從內容判斷主題時，才在最終報告裡標「別名待確認」並用暫定名，仍先寫入。）

### 3.2 提示詞結構

寫入 `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/prompts/{別名}.md`，結構：

```markdown
# {標題} Playbook

> {一句話描述使用情境}

---

## 前置條件
（需要什麼環境、權限、工具）

## 架構認知（重要）
（必須先理解的背景知識，如服務關係、欄位差異等）

## 操作流程

### Step 1: {步驟名}
{具體操作、指令、MQL 模板等}

### Step 2: {步驟名}
...

## 陷阱警告

| # | 陷阱 | 正確做法 |
|---|------|---------|
| 1 | {錯誤做法} | {正確做法} |

## 速查表
（參數、ID、對照表、常用指令）

## 驗證清單
- [ ] {確認項目 1}
- [ ] {確認項目 2}
```

### 3.3 寫入 prompts 目錄

```bash
# 寫入當前帳號的 prompts 目錄
"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/prompts/{別名}.md"
```

> 跨裝置/跨環境同步由你環境的 hook（若有）處理。

---

## Phase 4：索引更新 + 同步

### 4.1 更新索引（hot 只留 User，其餘進 cold topic 檔）

**hot/cold 分層（2026-07-15 定案）**：always-load 的 MEMORY.md 只放 `## User`（個人習慣/偏好）+ 各類別一行指標。其餘索引一律進對應 **cold topic 檔**、**不進 MEMORY.md**（memsearch + UserPromptSubmit hook 會召回）：

| 類型 | 索引寫到 |
|------|---------|
| User（個人習慣/偏好） | `MEMORY.md` 的 `## User`（**唯一進 hot 的**） |
| feedback | `MEMORY-feedback-index.md` |
| reference | `MEMORY-reference-index.md` |
| project | `MEMORY-project-index.md` |
| proto-skill | `MEMORY-proto-index.md` |

- 格式同樣 `- [標題](檔名.md) — 描述`，寫進 cold topic 檔（memory 目錄下），先查重再加。
- **絕不**把 feedback/reference/project 加進 MEMORY.md——hot 要保持乾淨（會被 audit HOTGROWTH 偵測）。
- 記憶「檔案」照常寫在 memory 目錄（memsearch 吃內容），只是「索引行」分流到 cold。


### 4.2 更新專案 CLAUDE.md（如適用）

如果有寫 lessons-learned → 確保對應專案的 CLAUDE.md 中：
- `doc/lessons-learned/` 目錄列表是最新的
- 快速問題對照表有對應條目

### 4.3 最終報告

輸出最終清單：

```
## /收 完成

| 產出類型 | 數量 | 檔案 |
|---------|------|------|
| feedback memory | N | {檔名列表} |
| reference memory | N | {檔名列表} |
| lessons-learned | N | {專案/檔名} |
| proto-skill prompt | N | {別名} |

### 索引更新
- [x] MEMORY.md 已更新
- [x] {專案}/CLAUDE.md 已更新

### 跨裝置/跨環境同步（個人選配）
若你的環境有設定多裝置/多環境同步 hook 才需要；一般單裝置可略。跨裝置/跨環境同步由你環境的 hook（若有）處理。
```

---

## 安全閥

- **自主收割、不等確認** — 直接收完、寫入、同步；輸出摘要是事後記錄不是確認閘門。**經驗累積優先**
- **靠查重防記錯 / 記重（取代「等確認」）** — 先查重（Phase 2.1），有就更新、沒有才新建
- **不覆蓋既有記憶** — 有就更新、沒有才新建；只補不刪無關內容
- **自動命名 proto-skill** — 依既有命名慣例自己訂別名，不問使用者；同名視為更新
- **不刪除任何既有檔案** — 只新增或更新
- **lessons-learned 四段必備** — 缺項自己補，不丟給使用者

---

## 附錄：記憶檔案路徑速查

| 類型 | 路徑 |
|------|------|
| feedback/reference memory | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(pwd \| sed 's#/#-#g')/memory/` |
| memory 索引 | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(pwd \| sed 's#/#-#g')/memory/MEMORY.md` |
| lessons-learned | `<專案根目錄>/doc/lessons-learned/` |
| proto-skill prompt | `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/prompts/` |
| 專案 CLAUDE.md | `<專案根目錄>/CLAUDE.md` |
| 跨裝置/跨環境同步 | 個人選配，由你環境的 hook（若有）處理 |
