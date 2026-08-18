---
description: "AX Resume — 恢復先前 Stash 的工作進度（類似 git stash pop），重建上下文接著做，並自動判斷待完成項是否要重啟 mission 方法論。觸發語：「resume」「繼續剛才的」「接回來做」「上次做到哪」「撿回來做」「看一下有哪些暫存」。適合切換任務後回來、想無縫接續之前暫停的工作。"
---

## 🔍 Recall（僅在遇到技術問題時）
本技能是輕量進度操作，一般**不需** recall。**只有**過程中冒出技術決策或不確定點時，才 `ax:recall "<關鍵字>"`（此時 recall 為輔助：查無≠沒做過）。

從 stash 目錄（`${AX_STASH_DIR:-$HOME/.ax/stash}`，未設 env 用預設，用前 mkdir -p）讀取暫存的工作進度，恢復上下文繼續工作。

**核心觀念**：恢復不是「照著 todo 清單硬做」，而是要**重新啟用 stash 當下的 mission 模式**。slash command 是一次性注入、沒有持久狀態，若 resume 只是續作，就會丟掉 mission 的做法（記憶載入、對抗審查、實證閘門、收尾 lessons）。因此 resume 對「待完成」的開發實作項，必須主動重入 mission——**具體機制**：用 `Skill` 工具 invoke `mission`（把上下文當 args 傳入）；若 Skill 工具不可用，再讀本機的 mission 指令檔並照它的 Step 0→5 執行。**不可只寫一句「我要呼叫 /mission」就跳過，也不可把球踢回叫使用者自己打 /mission**。

## 執行步驟

1. **掃描 stash 目錄**：讀取 stash 目錄下所有 `.md` 檔案（排除 README.md）
2. **篩選未完成項目**：只列出 status 不是 `done` 的項目
3. **列出摘要讓使用者選擇**：

   格式範例：
   ```
   目前有以下未完成的工作：

   1. [blocked] 20260312-trivy-cve-remediation — Trivy CVE 修復（等待 DevOps 重新掃描）
   2. [in-progress] 20260315-some-feature — 某功能開發（做到 Step 3）

   要恢復哪一個？（輸入編號）
   ```

4. **使用者選擇後，先重建正確前提（不要拿過期快照直接做）**：
   - 讀取完整的 stash 檔案
   - 讀取相關檔案（stash 中列出的相關檔案）確認當前狀態
   - **執行 stash「恢復指引」裡的驗證步驟**：若 stash 曾動過 DB / K8s / 部署，先跑驗證 SELECT / `kubectl get` / `curl health` 確認共享狀態沒被 cron 或他人改回
   - **查是否已被完成**：`git log --oneline -- <相關檔案>` 看 stash 期間是否已合入 main；`ls "${AX_STASH_DIR:-$HOME/.ax/stash}"/*<主題關鍵字>*` 掃同主題的兄弟 stash（尤其標 `done` 的後繼檔）。已完成 → 轉為驗證，別重工
   - **stash 內的預估數字一律重算**（stash 是進度上下文，不是答案快取）
   - 向使用者簡報：上次做到哪裡、接下來要做什麼
   - 將 status 更新為 `in-progress`（如果原本是 `blocked`）

5. **對「待完成」清單套用 Mission 方法論（關鍵步驟，避免恢復後遺失 /mission 做法）**：

   a. **讀回 Mission 上下文**：若 stash 檔含「## Mission 上下文」段，先讀回其中的 **args.rawRequest 原話、經驗上下文摘要、changeTypes、執行方式、Workflow 執行進度、對抗審查計畫與進度、pending CRITICAL、TDD 狀態**，作為續作前提（尤其 rawRequest 原話 → 重入 mission 後意圖守門人要用它比對；Workflow 執行進度 → 知道 research/implement/review 各做到哪，別從頭重跑）。若**沒有此段**（舊 stash / 非 mission）：先看待完成清單有沒有開發實作型 todo——**有才**視同重啟 mission、補做 Step 0 記憶載入；若全是快速操作/偵探排查，就不套 mission（避免小改硬套燒 token）。

   b. **逐一分類每個待完成 todo（用 `/mission` Step 1「任務形狀前置判準」，五分法對齊 mission.md），決定套用強度——不是全部無腦套**：

      | todo 形狀 | 處理方式 |
      |----------|---------|
      | 快速操作（改一行 / 查狀態 / 轉貼 / 行事曆） | 對話層直接做，不套 mission |
      | 偵探排查（查原因 / bug / 異常 / log 交叉比對） | 單一連貫推理鏈，不切多 agent |
      | 偵探+實作混合（先查原因、再修好） | **先偵探**連貫排查到根因 → 得根因後**才**升級成開發實作型走 mission |
      | 開發實作（寫 / 建 / 實作 / 重構，跨檔含業務邏輯） | **走 mission**：載記憶(Step 0) → 研究 → 實作 → 對抗審查 + 實證閘門 → 收尾 lessons |
      | 多批次達標型（≥3 可獨立驗收子項、各有 done 判準） | 走 mission **Step 1.5 長跑模式**（PROGRESS.md 迭代），不要單一 context 硬啃 |

   c. **凡清單中有「開發實作型 / 混合型升級後 / 長跑型」todo → 依核心觀念的機制實際重入 mission**（用 `Skill` 工具 invoke `mission`，args 帶入「Mission 上下文摘要 + 該 todo 描述 + rawRequest 原話」；Skill 不可用則 Read mission.md 照 Step 0→5 做）。這樣 mission 的 Step 0 記憶載入、實證閘門（「不是隊友說要改就改」）、TDD 紅綠、收尾 lessons、三環境同步都不會被漏掉。**注意 mission.md 本身不會再呼叫 /resume，無遞迴風險**。

   d. **純快速操作 / 偵探排查的 stash** 不必套 mission，直接續作即可（強行套只會讓小改燒掉大量 token，違反 mission 的精簡優先原則）。

6. **如果只有一個未完成項目**：直接詢問「要恢復 {標題} 嗎？」不用列清單（確認後仍走上方 Step 4 重建前提 + Step 5 Mission 路由）

7. **如果沒有未完成項目**：告知「目前沒有暫存的工作進度。」

## 使用者也可以直接指定

如果使用者說 `/resume trivy` 或 `/resume cve`，直接用關鍵字模糊匹配檔名或標題，不用列清單（仍走上方 Step 4 重建前提 + Step 5 Mission 路由）。

## 完成工作後

當恢復的工作全部完成時：
1. 將 stash 檔案的 status 改為 `done`
2. 更新 updated 日期
3. 告知使用者此項目已完成歸檔
