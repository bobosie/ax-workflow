---
description: "AX Mission — 複雜開發任務的預設引擎（不確定用哪個開發型 skill 時的預設）。自動：載入知識庫 → 研究 → 實作 → 對抗審查＋實證驗過（加碼模式才啟用完整對抗）→ 收尾。適合：需要「研究+實作+審查」的開發任務、跨服務 bug 修復或重構、要謹慎驗證的複雜功能。快速操作／偵探排查／一句話能答的問題請直接在對話層做，不要開 mission。"
argument-hint: "任務描述"
---

# Mission — 任務導向多 Agent 協作

你收到了一個高層級任務。Mission 負責「大腦＋對話層」：載入你的記憶、判斷任務、直接執行、最後綜合報告。**實際的多 agent 執行交給 `Workflow` 工具當引擎**（平行、對抗式驗證、可恢復、token 預算），只有簡單或高互動任務才留在對話層自己做。

> **直接執行，不要事前確認**：使用者打 `/mission` 即視為授權。判斷完任務類型與拆解方案後，**直接呼叫 `Workflow` 開跑，不需進 plan mode、不需先問使用者**，跑完再用綜合報告呈現結果。唯一例外是動到 PROD / 不可逆操作（見「不要用 Workflow」與安全閥），那類留在對話層由安全閥把關。

> **opt-in 說明**：使用者打 `/mission` 並交付中等以上任務，**即視為授權呼叫 `Workflow`**（本 skill 明確指示要呼叫它）。不需要使用者額外喊 ultracode。

> **🚦 精簡優先（個人規模不需重型機制）**：預設走最省的「research → implement → 1 reviewer → lead 親驗」≈ 3 agent。**只有**使用者明說「徹底 / 全面 / 對抗 / 仔細審」或任務屬複雜/跨服務/PROD 相鄰，才加碼成「意圖守門人 + 2-3 對抗角色 + 逐 CRITICAL 實證」。別讓小改也燒 5+ agent（dogfood 實證：一個 trivial 任務跑全套會燒 ~300k token）。

## 先問這個：你需要 /mission 嗎？

`/mission` 適合「**開發實作型**」任務。任務若屬下列情況，用更輕量的方式更好（退出 mission 不是失敗，是對的選擇）：

| 情況 | 更好的做法 |
|------|----------|
| 快速操作（查狀態 / 改一行 / 轉貼 / 行事曆） | 直接在對話執行，不開 /mission |
| PROD 排查（bug / 異常 / SLS / log 交叉比對） | 直接對話，自己並行 grep，**不切多 agent**（偵探工作要 context 連貫） |
| 有現成 Playbook SOP（部署 / 建站 / 遷移等） | 用對應團隊約定的 playbook（如 `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/prompts/` 或專案 `docs/playbooks/`） |
| 只需要一個問題的答案 | 直接問，不需要 researcher agent |

真正適合 /mission：需要「研究 → 實作 → 審查」三個獨立視角的開發任務、跨 2+ 服務的 bug 修復或重構、需要對抗式驗證的複雜功能。

## Step 0: 載入經驗與記憶

在分析任務之前，**必須**先載入本地知識庫，避免重複踩坑：

1. **讀取 auto-memory 索引**：讀取 auto-memory 目錄下的 `MEMORY.md`，掃描所有 feedback 類型記憶
   - feedback 記憶是**最高優先**：包含使用者過去的修正指示、偏好、踩過的坑
   - 與任務相關的 project / reference 記憶也要讀取

2. **搜尋 memsearch 語意記憶庫**：用 `/memory-recall` 或 `memsearch search` 搜尋與任務相關的過去經驗
   - 搜尋關鍵字：任務涉及的**服務名、功能名、錯誤現象**
   - 取 top 5 結果，快速掃描是否有相關的 lessons-learned

3. **讀取專案 lessons-learned**：如果當前專案有 `doc/lessons-learned/` 目錄，掃描檔案清單，相關的讀內容（注意「根本原因」「解決方案」段落）

4. **整理為經驗上下文**：將收集到的經驗整理成一段精簡摘要：
   ```
   ## 經驗上下文
   ### 必須遵守的規則（來自 feedback memories）
   - {規則 1} / {規則 2}
   ### 相關過去經驗（來自 memsearch / lessons-learned）
   - {經驗：問題 → 解法}
   ### 相關參考資訊（來自 reference memories）
   - {參考}
   ```

> **這段「經驗上下文」必須傳遞給後續所有 subagents。** 用 Workflow 引擎時，把它整段當成 `args.experienceContext` 傳入，腳本再接在每個 `agent()` prompt 開頭。**同時保留使用者原始任務字串 `$ARGUMENTS`** 當 `args.rawRequest`，與你詮釋過的 `args.task` 並列——意圖守門人要用原話比對，避免「你一開始就誤解需求，全團在錯前提打轉」。

### ⚠️ 持續 Recall 原則（貫穿整個任務週期，不只 Step 0）

Step 0 是「任務啟動時的一次性載入」。但**任務執行到一半冒出來的子問題，才是最常漏查記憶的盲區**。以下情境在任務**任何階段**（lead 主對話 或 subagent）出現時，**第一動作是 recall，不是憑直覺試解或斷言**：

| 觸發情境 | recall 動作 | 查無相符才 |
|---------|-----------|-----------|
| 遇到錯誤訊息 / 工具行為詭異 / API 回非預期 | `memsearch search "<錯誤摘要或現象>" --top-k 5` | 自行排查 |
| 要說「我做不到 X」/「沒掛 Y」/「沒有 Z」 | `grep -rl "<關鍵字>" ${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/*/memory/feedback_*.md` + 掃你環境放工具/設定的目錄 | 才說沒有 |
| 找不到工具 / 路徑 / credentials | 查已知安裝位置（工具目錄、設定目錄）+ memsearch | 才說未安裝 |
| 「之前能做、現在不行」 | 先 recall 既有流程鏈（部署/操作 map），別被次要錯誤誤導成「管道壞了」 | 才當新問題查 |
| 要對某服務 / DB schema 做假設、要自創方案、**或要改 skill/工具** | memsearch + 讀相關 reference（如改 mission 必讀 `reference_mission-workflow-integration`） | 才算「首次遇到」 |

**決策樹（找到即停）：** 完全相符 → 直接沿用並說明出處；部分相符 → 以過去解法為基礎調整；查無相符 → 才自創，並標注「**首次遇到：<問題摘要>**」（供 Step 5 補 lessons）。

> 成本 3 秒，省掉的是 4–30 分鐘的長路。**「改 skill / 工具前沒先讀對應 reference 記憶」是最諷刺的反模式**（2026-06-26 改 mission 自己時就因沒讀 `workflow-schema-agent-no-output-check-disk` 而對所有 reviewer 掛了 schema，被對抗隊友+dogfood 雙重打臉）。
> **recall 不阻塞**：若 memsearch 不可用或查無，不要卡住任務，改用空上下文繼續，並在報告「注意事項」標記「本次無歷史記憶上下文」。

## Step 1: 任務分析

分析使用者給的任務描述：`$ARGUMENTS`

結合 Step 0 收集的經驗上下文：

1. **判斷任務類型**：調查 / 實作 / 修 bug / 重構 / 測試 / 部署

2. **任務形狀前置判準（先於複雜度評估）**：

   | 形狀 | 訊號 | 正確策略 | 絕對不要 |
   |------|------|---------|---------|
   | **快速操作** | 行事曆、轉發、查版本、改一行、查狀態 | 對話層直接做，30 秒內完成 | 開 Workflow / 建任何 subagent |
   | **偵探排查** | 排查、查一下、為什麼、錯誤、異常、bug、無法、報錯、SLS、log | 單一 agent 連貫推理（你自己或一個 researcher），並行 grep DB/code/log，交叉比對後結論 | 切多 agent！每個都要重建上下文，反而更慢更不準 |
   | **偵探+實作混合** | 同時含「排查…」和「修好/實作…」 | **先偵探**（單 agent 連貫排查到根因）→ 得根因後**才**進開發實作評估 | 一開始就 fan-out 對抗團把偵探工作切碎 |
   | **開發實作** | 開發、實作、建一個、寫一個、新功能、設計、重構（且訊息 >50 字） | 進入下方分級評估，依規模開 Workflow | — |
   | **多批次達標型（長跑）** | **≥3 個可獨立驗收的並列子項**（清單/checklist）＋各項可寫出可驗證 done 判準——**不論使用者有無說「整晚跑/直到達標」等字眼**，只要滿足此結構就主動評估走長跑 | 進 **Step 1.5 長跑模式**：建 PROGRESS.md → 外層 driver 迭代，每輪乾淨 context 啃一項走 Step 2 Workflow → 驗綠→打勾 | 在單一 context 硬啃全部（必塞爆 context→壓縮掉細節→「趕、亂、假裝做完」） |

   > **偵探黃金法則**：所有線索（DB、code、deploy history、pod log）必須在同一個推理鏈裡交叉比對才能得正確根因。切 agent = 把同一個偵探的筆記本剪成三段。
   > **長跑黃金法則**：長任務跑不完的真因是「單輪 turn 上限」＋「context 會滿」兩者疊加。解法不是「一輪跑很久」，而是「跨很多輪、每輪 fresh context、靠檔案接力」（見 Step 1.5）。
   > **優先序（自行分配的關鍵）**：任務同時像「開發實作」又像「多批次達標型」時，先驗長跑三結構條件（≥3 可獨立驗收子項＋各有 done 判準＋不需一次性 context 完成），滿足就走 Step 1.5——**不必等使用者說長跑詞，這才是真正的「自行分配」**。

3. **評估複雜度與審查強度（精簡優先，按需加碼）**：

   | 層級 | 判準 | 執行方式（agent 數） |
   |------|------|---------|
   | **簡單** | 單一檔案、明確修改、純字串/設定/文案 | **對話層自己做**，不開 Workflow、不召任何 agent（0） |
   | **預設（中等）** | 跨檔案含業務邏輯、需調查 | Workflow：research → implement → **1 個 reviewer（混合 lens）** → lead 親驗實證（≈3） |
   | **加碼（複雜/徹底）** | 跨服務、多步驟、**或**使用者明說「徹底/全面/對抗/仔細審」、**或** PROD 相鄰 | Workflow：research → implement → **意圖守門人 + 2-3 對抗角色** → 逐 CRITICAL 實證（verifier 上限 3）（≈5-7） |

   > 「跨檔案」單獨不算中等——要**跨檔案 且 含業務邏輯/安全/外部 API** 才算。純字串/config/test file 改動維持簡單。
   > **判斷「變更類型」（可複數）**：產出涉及 **ui** / **backend** / **plan** / **data(財務/對帳/結算數值)** 哪幾類，存成 `changeTypes` 陣列（如新功能常是 `['ui','backend']`），開 Workflow 時傳入；對抗角色團依此**聯集**取 lens（見 Step 2 矩陣）。漏填 = 靜默跳過對抗審查，務必填。

4. **對照 Step 0 的 recall 結果，明確三選一**：完全相符 → 直接沿用（寫明「沿用 {來源}」）；部分相符 → 以過去解法為起點調整（寫明不同點）；查無 → 才自創，Step 5 補 lessons。

5. **中等以上**：判斷完拆解就**直接呼叫 `Workflow`**，不需 plan mode、不需先問。Workflow 背景跑，跑完通知你回 Step 3。（PROD/不可逆除外，留對話層）

### 何時「不要」用 Workflow（留在對話層自己做）

- **高互動任務**：需要邊做邊跟使用者討論、頻繁確認方向
- **動到 PROD / 不可逆操作**：保持在對話層，安全閥才攔得住
- **UI 視覺/互動實證**：background agent 跑不了互動瀏覽器（無 MCP、headed/CF/讀圖需 lead），UI 截圖/操作驗證**一律由 lead 在對話層做——用 Playwright（腳本 `npx tsx` 或 MCP，擇一可用；MCP 常不在 session，腳本即可）**，不可委派給 Workflow subagent
- **使用者明確要求逐步看過程**
- **無人值守 agent（headless，如 chat-bot 情境）**：使用者期望 1–3 分鐘回覆，Workflow 是背景黑箱、啟動後沉默到跑完。這類 agent 90% 任務是「快速操作」或「偵探排查」。退化策略：① 快速操作→直接做 30 秒回；② 偵探排查→單一連貫推理鏈不切 agent，5 分鐘內出根因；③ 真正開發型（>50 字、明確「寫/建/實作」）才考慮 Workflow，且**先發一條「開始了，預計 X 分鐘」**回覆使用者不要沉默
- 這幾種改用本檔末「附錄：純對話 fallback」的手動 Agent 流程

<!-- 個人 dogfood（無人值守 agent，headless）專用，org 分發可忽略：
若你的環境有一道「無人值守 agent → 自動判斷是否觸發 /mission」的前置閘（例如某個 gateway 依關鍵字注入「請用 /mission」或「並行調查」指引），那道閘的邏輯與本檔的形狀判準必須同步——改任一邊（本檔形狀判準／閘門關鍵字／字數門檻）都要一起改，避免兩邊判斷分歧。單裝置互動使用者不需要這道閘，直接打 /mission 即可。 -->
> 在對話直接打 `/mission ...` 即繞過任何前置判斷直接執行。

## Step 1.5: 長跑模式（多批次達標型，Loop-Until-Done）

> **命中 Step 1 形狀判準「多批次達標型」才走這節**（別讓一般 mission 都變 loop——無差別強指令會製造新鬼打牆）。核心：不是「一輪跑很久」，是「跨很多輪、每輪 fresh context、靠檔案接力」——單 context 硬啃多項必塞爆→壓縮掉細節→假裝做完。
> **成本意識**：每輪各跑一次 Step 2 Workflow（≈3-7 agent）；N 項 ≈ N×單項成本，粗估 N×100-300k token。啟動前估總量、確認額度、設 max-iterations 上限。
> **無人值守 agent（headless）路徑不走長跑**（期望 1-3 分鐘回覆）：headless agent 遇多批次應降回互動或分批，故前置觸發閘（若有）**刻意不加長跑關鍵字**（此非遺漏——長跑靠對話層 lead 主動識別，不靠 headless 第一道閘）。

**三步驟：**

1. **建 PROGRESS.md（跨輪記憶＝single source of truth）**：寫到 stash 目錄（`${AX_STASH_DIR:-$HOME/.ax/stash}`，未設 env 用預設，用前 `mkdir -p`）`{date}-{任務}-PROGRESS.md`，每項一行，含：
   - 狀態標記：`[ ]` todo／`[~]` in-progress／`[x]` done／`[!]` blocked／`[H]` needs-human
   - **可機器驗證的 done 判準**（不是「修好 X」，而是「`go test ./...` 綠 且 對應 E2E spec 通過 且 REL pod image=新版」）＋ 驗證指令
   - 已完成的項目直接標 `[x]` + 一句證據
   - 寫不出可驗證 done 判準的項目 = 還沒夠格自主跑，先在對話層釘死再入列

2. **選 driver（用既有的，不重造輪子）**：
   - 互動同 session → `/loop`（自我配速）或本 skill 每輪重入
   - 跑到達標無人值守 → `/goal "PROGRESS.md 全部 [x]，或超過 N 輪停"`（**內建指令、專為此設計**、Haiku 每輪評估、可 --resume；前提：需 **trusted workspace**（接受 trust dialog）且 **hooks 未被限制**（非 disableAllHooks/allowManagedHooksOnly））或 `/ralph-loop --completion-promise "..."`（plugin）或 `/loop`
   - 整晚無頭 → `while :; do claude -p --max-turns 40 --model <明確model> "$(cat prompt.md)"; done`（**帳號路由陷阱**：若你用非預設帳號/設定跑，`CLAUDE_CONFIG_DIR` 和 `CLAUDE_CODE_OAUTH_TOKEN` 必須**兩個一起 export**，否則額度記到預設帳號；headless 必帶 `--model` 防漂移）

3. **每輪迭代（乾淨 context）**：讀 PROGRESS.md → 挑下一個 `[ ]` → 走 **Step 2 Workflow**（research→implement→對抗審查→實證）把這一項做對 → 驗綠 → 該項 **commit＋push**（需要時含測試環境部署＋實證；依安全閥唯 PROD 等使用者）→ **立即**更新 PROGRESS.md 打勾 → 結束這輪。
   > 子項依複雜度**獨立判層級**：簡單項（單一檔案/純字串）對話層直接做完驗綠即打勾、不強開 Workflow；中等以上才進 Step 2 Workflow。

**四條護欄（缺一就變 quota 黑洞或假成功）：**
- **上限 + 卡住偵測**：設 max-iterations 上限；**同一項連續 2 輪無實質進展 → 標 `[!]` blocked、停下報告**，不無限燒（bounded-retry：無 cap 的 retry 在永久故障下游是黑洞）。
- **需人工項標記**：需錄影判讀 / 需 PROD 授權 / 需外部資料、**或含 UI 視覺/互動實證的子項**（background Workflow 無 MCP、跑不了 Playwright），一律標 `[H]` needs-human，driver **跳過不卡死**，並在該輪明列「這幾項要你介入」，**不可假裝已過**。
- **狀態即時落檔**：進度只信 PROGRESS.md + `git log`，**不信 agent 最後那段 text**（long-running agent 常在結尾掉回報；SIGTERM 也會吞掉只在結尾印的摘要）。每完成一項就寫檔，不累到最後。
- **達標定義嚴格**：`[x]` 必須附「測試綠／實際操作成功」證據；「無法重現」≠done。全部 `[x]` 才算達標，收尾出一次總報告。

> **PROD/不可逆項永遠留對話層人工把關**（見安全閥）——loop 可跑 REL 實作與唯讀調查，但「推 PROD」那格一律標 `[H]`，不進無人值守迴圈（commit/push/測試環境部署可進迴圈）。

## Step 2: 用 Workflow 引擎執行

中等以上、且不屬於「不要用 Workflow」時，**呼叫 `Workflow` 工具**，把經驗上下文當 `args.experienceContext`、原始需求當 `args.rawRequest`、`args.changeTypes` 傳入。

> **由 `/resume` 重入時的階段接手（對側契約）**：若本次 mission 是被 `/resume` 帶著「既有 Workflow 執行進度」啟動的（args 或交付訊息含「research 完成 / implement 做到哪 / review 未做」等狀態），**沿用已完成階段的產出、不從頭重跑**：research 已完成 → 直接把 stash 記錄的調查結論當 `research` 結果進 implement；implement 中斷 → 先 `git status`/`grep` 盤點磁碟已落地的部分再續，不重寫。只重跑「未做 / 中斷」的階段。沒有帶進度（一般 /mission）時照常從 Step 0 全跑。

### 角色對應（⚠️ 全部不掛 schema）

| Mission 角色 | Workflow 寫法 |
|-------------|--------------|
| researcher（唯讀調查） | `agent(prompt, {agentType:'researcher'})` → 回純文字 |
| implementer（寫程式） | `agent(prompt, {agentType:'implementer'})` → 回純文字，**lead 查磁碟驗收** |
| 預設 reviewer（混合 lens） | `agent(prompt, {agentType:'reviewer', label:'reviewer'})` |
| 意圖守門人（對齊規格，**不對抗**） | `agent(prompt, {agentType:'reviewer', label:'intent-guardian'})` |
| 對抗角色團（每位**不同 lens**） | `parallel(LENSES.map(L => () => agent(..., {agentType:'reviewer', label:'adversary:'+L.role})))` |
| 實證 verifier（重現 CRITICAL，上限 3） | `agent(prompt, {agentType:'reviewer', label:'verify:...'})` |
| **UI 視覺/互動實證** | **不進 Workflow**——lead 在對話層用 Playwright（腳本 `npx tsx` 或 MCP） |

> **🚫 絕對不要對任何 agent 掛 `schema`。** 實測教訓（`feedback_workflow-schema-agent-no-output-check-disk`、`feedback_subagent-may-skip-partial-tasks`，2026-06-26 dogfood 再證）：① implementer+schema 沒回 StructuredOutput 會**拋錯中止整條鏈**（檔案已落地卻判 failed）；② **reviewer+schema 大量失敗**（dogfood 3 個對抗 reviewer 死 2 個）。一律用**純文字輸出**，lead 自己 parse。**空回傳（`len=0`）是常態不是失敗**：agent 常在工具迴圈中途被切、沒走到最終文字回合（非 context 爆——見 RECALL 的「輸出保命規則」，該規則已注入每個 agent prompt 要求「結論先行、增量更新」預防之）。事後補救：agent 仍活著時 `SendMessage(agentId, "停止調查，立刻給最終裁決，不要再呼叫工具")` 逼出結論（它 context 已載入）；已結束則查磁碟驗收（見 Step 3.1）。implementer failed 訊息含 "without calling StructuredOutput" → 先 `git status` 看磁碟，別重跑。

### 鐵則（寫進每個 agent 的 prompt）

> 1. **開頭附上 `args.experienceContext`**——讓每個 agent 知道要遵守哪些 feedback 規則、避開哪些坑。
> 2. **必帶 `RECALL`**（下方常數）——background agent 不會自己想到查記憶，必須明文叫它查。
> 3. **implementer 鐵則**：① **絕不** `git commit` / 不 push / 不部署 / 不動 PROD（驗收與審查要在 commit 前——由 lead 驗收全綠後統一 commit/push/部署測試環境；**PROD 一律使用者把關**）；② **不掛 schema**，回純文字並列出改了哪些檔（lead 用 `git status`/`grep` 逐檔驗收，agent 可能只做一半就回報完成）；③ **補測試三定義（使用者「補對抗、補測試、補實證測試」的「補測試」，2026-07-10 訂，缺一不算交付）**：(a) 新功能先寫失敗測試（TDD 紅燈）再實作到綠燈；(b) 新行為的 unit ＋ E2E 測項**與程式碼同 repo 落檔**——手動實證（Playwright/curl 驗過）≠ 補了測項，手動驗的每一步都要沉澱成可重跑 spec；(c) 本次踩到的坑/修掉的錯，用回歸測試案例釘死——下次再犯要在測試層**當場紅**，當場偵測當場修；④ **changeType 含 ui 時所有功能驗證走 UI 操作、禁止以 API 代替；bug fix 必補對應 E2E spec**；⑤ 結果末列完整 build+deploy 交棒清單（commit ≠ 上線）＋**本次新增測項清單（unit/E2E 各列檔名與覆蓋的行為/坑）**。
> 4. **researcher 窮舉不抽樣**：任務含「全部/所有/每個/整個/稽核」時必須窮舉，不可抽樣代替；需縮範圍則明標未涵蓋範圍與理由。
> 5. **意圖守門人**只比對規格符合度（每項 met/partial/missed + 證據），**不對抗**；prompt 必帶 **`args.rawRequest` 原話**（不只你詮釋的 task），並比對「原話 vs 詮釋版」有無落差。
> 6. **對抗角色**每位帶**不同 lens**（依 `changeTypes` 聯集選），prompt 明確要求「**別背書、用證據推翻**」，每個問題**必附可重現 repro 指令 + 實際觀察**，沒實跑過的標「未實證」。
> 7. **實證閘門（核心——「不是隊友說要改就改」）**：見下節。

```js
const RECALL = `
## 執行中 Recall 規則（強制）
遇到任何不確定或子問題（錯誤訊息、工具行為不符預期、要做技術決策、找不到資源、要對某系統做假設）——
第一動作是 recall 不是盲試：memsearch search "<問題關鍵字>" --top-k 5
完全相符過去解法→直接沿用並引用來源；部分相符→調整後沿用；查無→才自創，並在回傳結果標注「首次遇到：<問題摘要>」。

## 防謊報 audit（強制，三階梯）
對變更/執行結果的狀態宣稱只能用所在的階：written（碼寫了）→runs（跑過沒報錯）→verified（親眼看它做對事）。「修好了」=verified；沒跑過就說「已寫完、尚未執行」。重讀自己的 code≠驗證；錯誤訊息變了或消失≠修好。宣告前逐項對照本 session 工具結果，未驗證項集中列出並點名具體沒查什麼；測試失敗說失敗並附輸出，部分完成就說部分完成。

## 思考鏈方向（強制）
遇到不確定：先列假設→選最小驗證路徑（讀檔/查 schema/最小 repro）→實證→才宣稱。斷言以實際系統狀態為準，非文件或記憶。交付前先試著反駁自己的結論一次。

## 輸出保命規則（強制，防空回傳）
Workflow 只回收你「最後一則文字訊息」當回傳值。你可能在跑工具的中途就被切斷（撞回合／步數／時間預算，**非 context 爆**——實測空回傳 agent token 僅 84k–129k、遠低於上限），來不及寫總結 → 回傳變空字串、前功盡棄。實測空回傳率：implementer≈50%、reviewer≈40%、researcher≈17%（14 workflow 統計），工具越密集越容易中招。因此：
1. **結論先行**：一拿到足夠形成初判的資訊，立刻輸出一則文字訊息寫下當前結論／發現骨架（標「初步」，即使還沒查完）。
2. **增量更新**：之後每完成一段查證，再輸出一則文字訊息「覆蓋更新」結論，把 repro 證據補進去。
3. **絕不**「連跑十幾個工具、最後才一次寫總結」——那是空回傳的頭號主因。
4. 若發現自己已跑很多工具卻還沒輸出過任何結論文字，立刻停下先寫目前結論再繼續。`
```

### 對抗審查矩陣（角色化 + 意圖守門人 + 實證閘門）

**① 意圖守門人（加碼時才召，獨立角色，只對齊不對抗）**——逐項比對「**使用者原話**（`args.rawRequest`）+ 詮釋版需求 vs 實際產出」met/partial/missed，附證據。抓「做歪、做漏、超出範圍、誤解原意」。

**② 對抗角色團（依 `changeTypes` 聯集選，每位「別背書、用證據推翻」）**

| changeType | 對抗角色（lens） | 各角色重點 |
|-----------|----------------|-----------|
| `ui` | 設計師 / 實作者 / QA | 設計師：截斷·溢出·RWD·對比·空狀態·i18n撐版·暗色；實作者：複用·狀態·效能·邊界；QA：操作路徑·跨瀏覽器·互動edge case（**視覺/互動的實證回 lead 跑 Playwright**） |
| `backend` | QA / 安全（+選 PM/效能並發） | QA：edge case·輸入驗證·回歸；安全：authz/authn·注入·機密外洩·回呼驗證per-endpoint；PM：correctness≠effectiveness（**注意與意圖守門人重疊，預設併入守門人，加碼才獨立**）；效能並發：env×並發 |
| `data`（財務/對帳/結算數值） | 數值複核（盲算） | **只給口徑條件、不給預期數值、各走不同 SQL/計算路徑、最後逐欄比對**，全一致才算過（`feedback_blind-recompute-financial-deliverables`） |
| `plan` | 成本 / 難易度 / 其他 | 成本：開發+維運·**是否過度工程**；難易度：技術風險·依賴·未知數；其他：可維護·遷移風險·替代方案 |

**③ 實證閘門**
1. 對抗角色提 CRITICAL/WARNING → **必須附可重現 repro + 實際觀察**。只有口頭斷言 → 降級「待查疑慮」，不修。
2. **加碼時逐 CRITICAL 派 verifier 實際重現（上限 3，超出列報告由 lead 親驗）**；verifier **必須回傳真實證據**（實跑指令的 stdout/截圖/log），空泛的「confirmed」不採信（防 agent 自我背書）。
3. **無測試框架時**：verifier 必須寫最小 repro 腳本（`node -e`/`python -c`）實跑；連 repro 都跑不了 → 明說「環境受限未實證」，**不可假裝通過**。
4. **UI 實證一律 lead 對話層跑 Playwright**（background 無 MCP）；後端模擬真實 runtime（非互動/locale/並發）；計畫本機實測 + WebSearch 查 failure mode。
5. **lead 親驗**：最關鍵 CRITICAL，lead 自己下 code/DB/Playwright 驗一次是否真實存在，確認屬實才修。
6. 修正後 → 必須有「測試通過/實際操作成功」證據才算 OK。「無法重現」≠「沒問題」也≠「找到根因」。
7. **headless（無人值守／`claude -p`）分支**：沒有人類 lead 在場 → 親驗改為「自動跑可驗證指令（DB query/grep/repro 腳本）把輸出附進報告 + 列出哪些 CRITICAL 未經人類確認」，並**不假裝親驗已完成**。

### 預設範本（精簡，≈3 agent，無 schema）

```js
export const meta = {
  name: 'mission-default',
  description: 'Mission 預設：研究 → 實作 → 1 reviewer（混合 lens）',
  phases: [{title:'Research'},{title:'Implement'},{title:'Review'}],
}
const CTX = args.experienceContext, RAW = args.rawRequest
// RECALL 同上；LENSES 見加碼範本
const research = await agent(`${CTX}\n${RECALL}\n\n# 調查\n${args.task}\n回傳程式碼路徑、現有 pattern、根本原因（純文字）。`,
  { agentType:'researcher', phase:'Research' })
const impl = await agent(`${CTX}\n${RECALL}\n\n# 實作（禁止 commit/部署；新功能先 TDD 紅燈；ui 走 UI 驗證）。\n${args.task}\n調查：${research}\n回純文字並列出改了哪些檔。`,
  { agentType:'implementer', phase:'Implement' })
const review = await agent(`${CTX}\n${RECALL}\n\n# 混合 lens 審查（規格符合度 + 依 changeTypes 取最高風險角度），用證據推翻不要背書，每個問題附 repro 指令+實際觀察。\n變更：${impl}`,
  { agentType:'reviewer', phase:'Review' })
return { research, impl, review }   // lead 讀 review 文字，親驗 CRITICAL（含 UI Playwright）
```

### 加碼範本（複雜/徹底，意圖守門人 + 對抗團 + 實證，無 schema）

```js
const CTX = args.experienceContext, RAW = args.rawRequest
const LENSES = ({
  ui:      [{role:'設計師',focus:'截斷·溢出·RWD·對比·空狀態·i18n撐版·暗色'},{role:'實作者',focus:'複用·狀態·效能·邊界'},{role:'QA',focus:'操作路徑·跨瀏覽器·互動edge case'}],
  backend: [{role:'QA',focus:'edge case·輸入驗證·回歸'},{role:'安全',focus:'authz·注入·機密·回呼驗證per-endpoint'}],
  data:    [{role:'數值複核',focus:'盲算：只給口徑不給預期值、走不同SQL路徑、逐欄比對'}],
  plan:    [{role:'成本',focus:'開發+維運·是否過度工程'},{role:'難易度',focus:'技術風險·依賴·未知數'},{role:'其他',focus:'可維護·遷移·替代方案'}],
})
const lenses = [...new Set(args.changeTypes||[])].flatMap(t => LENSES[t]||[])
if (!lenses.length) log('[WARN] changeTypes 無對應 lens，對抗審查將跳過——請確認有傳 changeTypes')

const research = await agent(`${CTX}\n${RECALL}\n\n# 調查\n${args.task}`, { agentType:'researcher', phase:'Research' })
const impl = await agent(`${CTX}\n${RECALL}\n\n# 實作（禁止 commit/部署；TDD 紅燈先行；ui 走 UI 驗證）\n${args.task}\n調查：${research}\n列出改了哪些檔。`, { agentType:'implementer', phase:'Implement' })

// 意圖守門人（帶原話）
const intent = await agent(`${CTX}\n${RECALL}\n\n# 意圖守門人：逐項比對「使用者原話 + 詮釋需求 vs 實際產出」met/partial/missed + 證據，並指出原話與詮釋的落差。\n原話：${RAW}\n詮釋需求：${args.task}\n變更：${impl}`,
  { agentType:'reviewer', phase:'Review', label:'intent-guardian' })
// 對抗角色團（平行，純文字）
const reviews = (await parallel(lenses.map(L => () => agent(
  `${CTX}\n${RECALL}\n\n# 你是【${L.role}】，對抗審查【用證據推翻不要背書】。重點:${L.focus}\n變更:${impl}\n每個問題附可重現 repro 指令+實際觀察，沒實跑標「未實證」。`,
  { agentType:'reviewer', phase:'Review', label:'adversary:'+L.role })))).filter(Boolean)
return { research, impl, intent, reviews }
// 回對話層後：lead 從 reviews 文字挑 CRITICAL → 逐個（上限3）派 verifier 實證 / 或 lead 親驗；UI 一律 lead 跑 Playwright
```

> 規模對齊任務：簡單一句帶過就別開大艦隊；「徹底/全面盤點」才上全套。reviewer 文字被截斷 → `SendMessage` 逼結論。

## Step 3: 處理 Workflow 結果

Workflow 跑完以 `<task-notification>` 通知並回傳結果（純文字欄位）。**先過實證閘門再行動**：

1. **agent 回傳空字串（`len=0`）≠ 失敗、≠ 沒做**（**任何 agentType 都會發生**，含 researcher≈17%、implementer≈50%、reviewer≈40%）。成因是 agent 在工具迴圈中途被切、沒走到最終文字回合（非 context 爆、非 API error、非被 barrier 砍——2026-07-10 三隊友對抗實證）。**處理**：先查磁碟（`git status`/`grep` 看實作是否落地）＋讀後續 agent 有無引用具體程式碼細節（有＝已落地）；reviewer 空回傳＝調查多半已做只是沒總結，別重跑整條鏈。若 agent 仍活著且輸出被截在中段 → `SendMessage(agentId, "停止調查，立刻給最終裁決，不要再呼叫工具")` 逼出結論。**整個 workflow 全部 agent 皆空**才是另一種真失敗（wf 崩潰），此時才重跑。
2. **若 status=failed 且含 "without calling StructuredOutput"** → 先 `git status` 看磁碟（檔案多半已落地），別重跑 implementer；缺的後段（review）在對話層補。
3. **implementer 產出逐檔驗收**：`git status`/`grep` 確認每個預期檔真的被改（agent 可能只做一半）。
4. **意圖守門人優先**：missed/partial 的需求**一定要補**（最高優先，先於風險意見）；原話與詮釋有落差 → 回頭跟使用者對齊，別在誤解上繼續。
5. **對抗 finding 過實證閘門**：只對有 repro+實際觀察、且經 verifier 重現（或 lead 親驗）確認的才行動；只有斷言 → 「待查疑慮」記錄不修。CRITICAL → 先 `memsearch` recall 有無過去解法再修。
6. **lead 親驗**：最關鍵 CRITICAL 自己下 code/DB/Playwright 驗（**UI 一律 lead 跑 Playwright**）。headless 無人 → 自動跑可驗證指令附報告 + 標未經人類確認項，不假裝。
6.5. **實證程序目錄（有可驗證產出的改動、實作後必跑；A 優先 B fallback）**：若本次變更**有可驗證產出**（UI 入口／API 契約／DB 值／數值——**排除**純文案/設定/註解、無行為變更的純重構、純 test-file、純唯讀調查），驗收通過後跑 `ax:verify`（用 `Skill` 工具 invoke `ax:verify`；不可用則讀 ax plugin 的 `commands/verify.md` 照做——plugin 目錄見 `$CLAUDE_PLUGIN_ROOT`，未設時查 `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/known_marketplaces.json` 裡 `ax-workflow` 的 `installLocation`）。它查 vox-trace `spec-schema/specs/`＋`CATALOG.md` 有無**相關**驗證程序（相關性＝程序 assertions 觸及本次改動的 endpoint/畫面/欄位，非關鍵字命中；直接相關 >5 取最貼近 top-3~5、其餘列報告交 lead）：命中就**A＝playwright 腳本驅動真瀏覽器（不需 MCP）＋截圖判定 為首選；A 被擋（CF/503 冷載/captcha/純後端）才 fallback B＝打 UI 同一支 live API 等效並寫明原因**。UI/視覺類只能走 A；headless 無瀏覽器的 UI 類 → 標「未實證(需人走 A)」不阻塞。查無相關程序 → 提示補錄。**這是 lead 親驗的具體化，非額外選項；手動驗過的斷言仍要照 Step 10 落成測項。**
7. **修正後再實證**：要有「測試通過/實際操作成功」證據才算 OK。
8. **修正上限 2 輪**：第 2 輪仍有已實證 CRITICAL → 整理報告給使用者決定（headless：寫到 stash 目錄（`${AX_STASH_DIR:-$HOME/.ax/stash}`，未設 env 用預設，用前 `mkdir -p`）`mission-unresolved.md` + 以可觀測方式記錄告警（寫檔/送通知）+ 回傳 BLOCKED 狀態，不靜默成功）。
9. **對照經驗上下文**：親自確認變更沒違反 feedback 規則（lead 最終把關，不全推給 agent）。
10. **測項落庫閘門（與意圖守門人 missed 同級，缺 = 必補）**：逐項檢查 (a) 本次新行為的 unit＋E2E 測項是否已落檔（`git status` 看得到 spec 檔，不是只有實作）；(b) 本次踩的坑/修的 bug 是否有對應回歸測項釘死；(c) lead 親驗過的每個斷言（API 契約/403 對測/UI 文字）是否已轉成可重跑 spec——**手動驗過但沒落成測項 = 沒補**（2026-07-10 vestpkg 權限重編排：lead 手動 Playwright/curl 全驗完就交付，被使用者抓「該補的 E2E test 都要補上去」）。

## Step 4: 綜合報告

```
## Mission 報告
### 任務
{原始任務描述}
### 執行方式
{對話層自己做 / Workflow（預設或加碼範本、changeTypes、幾個 agent、對抗角色名單）/ **Step 1.5 長跑模式**（PROGRESS.md 路徑、跑幾輪、幾個 [H] 待人工、最終 PROGRESS 狀態）}
### 結果
{一句話總結}
### 變更清單
| 檔案 | 變更類型 | 說明 |
### Review 結果
{意圖守門人：規格符合度 met/partial/missed（加碼才有）}
{對抗角色：各 lens 結論}
{實證閘門：哪些 CRITICAL 已實證確認並修+通過測試、哪些降級待查疑慮、哪些**未實證(標紅)**}
{lead 親驗結論（含 UI Playwright）+ 三層驗證 gaps}
### 測試守門
{本次新增/更新的 unit 與 E2E 測項（檔名 × 覆蓋的行為/坑）；踩過的坑對應哪個回歸測項釘死；全套 unit＋E2E 最終數字（x passed / 0 failed）——沒補測項不得出報告}
### 注意事項
{未實證項明確標紅，不假裝已驗}
{K8s 服務修改 → push → Jenkins build → 更新 dt-k8s-rel-deploy newTag → push → 確認 pod image。commit ≠ 上線。}
```

> **Step 4 後主動判斷是否 `/收`**：有程式碼修改 → 一定；踩到新坑 → 呼叫；純調查/報告 → 報告即收尾。

## Step 5: 收尾

1. **程式碼修改** → 驗收＋測試守門全綠後**直接 commit＋push**（程式碼＋lessons＋CLAUDE.md 三件套同 commit，不必詢問），需要驗證的接著**部署測試環境（REL/STAGE/DEV）**並實證（pod image＋全套 E2E 歸零）；**唯 PROD 部署先報備等同意**
2. **有意義修改 / bug fix** → 三件套：`doc/lessons-learned/` ＋ `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/prompts/` playbook（值得沉澱時）＋ 更新記憶索引（若有安裝 memsearch）。或直接 `/收`
3. **agent 回傳「首次遇到」** → 整理成 lessons 草稿補 `doc/lessons-learned/`
4. **產生可重用腳本/yaml/wrapper** → 建議抽 toolkit（一次性→stash 目錄 / 可複用→你環境的工具目錄 / 跨裝置→git private repo）
5. **改到 `commands/`/`prompts/` 下 skill/playbook（含 mission.md 自己）** → 更新來源檔即可；**若你有多環境/多裝置設定**（多個 `CLAUDE_CONFIG_DIR` 或跨裝置 sync hook），才需確保各環境內容一致並更新同步來源（否則可能被 sync 還原——改 live 檔無效，要改同步來源）
6. **尾巴待辦** → 自動 append 到 `/收不乾淨` 的 followups.md
7. 標記所有 tasks 完成

## 安全閥

- **commit / push / 測試環境部署全開放，唯 PROD 把關**（2026-07-10 二次放寬）— lead 驗收＋測試守門全綠後，`git commit`、`git push`、部署到 **REL/STAGE/DEV 測試環境**（含 build image、bump newTag、套測試環境 DB migration）都**直接做不必詢問**——目的：自動化測試更完整、迭代更快。**唯一要使用者把關的是 PROD**（部署到 PROD、對 PROD DB 寫入、改 PROD 設定——先報備等同意）。測試環境部署仍遵守「本地驗到好再佈單一好版本」＋部署後實證（pod image/E2E 歸零）。Workflow implementer 仍禁止 commit/push/部署（驗收與審查要在 commit 之前，由 lead 統一執行）
- **全部 agent 無 schema** — 純文字 + SendMessage 收尾（schema 會讓 implementer/reviewer 大量 failed）
- **UI 實證回 lead** — background agent 跑不了互動瀏覽器，Playwright 截圖/操作一律 lead 對話層做（腳本 `npx tsx` 或 MCP，擇一可用）
- **實證閘門** — 沒有可重現證據（且 verifier 重現確認或 lead 親驗）不觸發修正；verifier 要回真實證據非空泛 confirmed；修正後要測試通過證據才算 OK。**「不是隊友說要改就改」**
- **補測試閘門** — 交付門檻 = 新行為測項（unit＋E2E）已落檔同 commit ＋ 踩過的坑有回歸測項 ＋ 全套測試 0 failed。**「跑綠既有測試」≠「補了新測項」**；手動實證過的斷言必須沉澱成可重跑 spec 才算補
- **精簡優先** — 預設 ≈3 agent，只有「徹底/全面/對抗」或複雜/PROD 相鄰才加碼；verifier 上限 3
- **修正 loop ≤ 2 輪** — 超過報告使用者（headless：寫 stash 目錄 + 以可觀測方式記錄告警（寫檔/送通知）+ BLOCKED 狀態）
- **Workflow 直接啟動不必事前確認** — 打 /mission 即授權（PROD/不可逆除外）
- **PROD / 不可逆操作不進 Workflow** — 留對話層。**不可逆定義（任一成立）**：對 PROD INSERT/UPDATE/DELETE、`kubectl apply`/`rollout restart` 到 PROD、改 Vault/密鑰/ConfigMap 立即生效、無法 `git revert` 一鍵復原。**混合型拆分**：PROD 唯讀調查（可 Workflow）→ REL 實作（可 Workflow）→ 推 PROD（留對話層把關）
- **headless / 非互動模式** — 等使用者確認的步驟不阻塞 → commit/push/測試環境部署照做並附實證；**PROD 部署只列指令不執行**；lead 親驗降級為自動驗證指令+標未確認項；未解 CRITICAL 以可觀測方式記錄告警（寫檔/送通知）
- **多環境 skill 同步意識** — 改 skill/playbook 收尾時，若你有多環境/多裝置設定才需同步各環境並更新同步來源（單裝置可略）
- **rate limit 意識** — 遇 rate limit 建議切帳號（cc-team / cc-max / claude）

---

## 附錄：純對話 fallback（不用 Workflow 時）

僅適用 Step 1 判定「不要用 Workflow」（高互動 / PROD / UI 實證 / 使用者要求逐步 / 無人值守 agent）。改用主對話直接序列啟動 subagents：

1. 用 `TaskCreate` 建子任務追蹤清單（角色、依賴、預期產出）
2. 用 `Agent` tool 啟動，每個 prompt 開頭附經驗上下文 + `RECALL`（**都不掛 schema**）：
   - **researcher** → 回 findings
   - **implementer** → 傳 findings，回變更摘要（禁止 commit/部署；TDD 紅燈；ui 走 UI 驗證）；**lead 用 git status 逐檔驗收**
   - **預設只開 1 個混合 lens reviewer**；**加碼**才開意圖守門人（帶原話）+ 對抗角色團（依 changeTypes，每位不同 lens、明確「別背書用證據推翻」、附 repro）
3. 獨立調查方向 / 多個對抗角色可同時平行啟動；輸出被截斷 → `SendMessage` 逼結論
4. **實證閘門**：CRITICAL 要實際重現（**UI 由 lead 跑 Playwright**、後端跑測試/repro 腳本）才修；只有斷言→待查疑慮；lead 親驗最關鍵；修正後要測試通過證據
5. 安全閥：修正 loop ≤ 2 輪，超過報告使用者
