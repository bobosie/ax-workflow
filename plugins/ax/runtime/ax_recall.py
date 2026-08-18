#!/usr/bin/env python3
"""ax_recall — 兩層並行 recall 客戶端（中央共享 KB + 本機私有）。

契約（兩層並行 recall 決策）：
  併行查兩邊、合併排名、逐項標來源：
    [TEAM]           中央 server（BM25 bigram，實證 R@5=57% 勝向量）＝全組織共享的 scrubbed KB
    [LOCAL-PRIVATE]  本機 ~/.ax-private（個人/機敏、刻意不上傳中央）—— 純 stdlib BM25，結果永不外流
  為何並行不 fallback：機敏知識結構性永遠不在中央→中央必 miss，且 BM25 無乾淨「查無」訊號，
    「中央查不到才查本機」判斷糊；並行查兩邊按正規化分數合併才乾淨、且私有資料從不離開本機。
  中央不可達 → 該層降級本機 mem 向量（可用性備援）；本機私有層照常查。
  單向：**永遠不把本機/私有結果回流 server**。每次只讀不寫。

用法：ax_recall "查詢字串" [--top-k 5] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ax_private_recall  # noqa: E402  同目錄，純 stdlib

SERVER = os.environ.get("AX_RECALL_SERVER", "http://127.0.0.1:7654")
TIMEOUT = 2.5


def from_server(query: str, k: int):
    url = f"{SERVER}/recall?q={urllib.parse.quote(query)}&k={k}&fmt=json"
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:  # 只 GET
        if resp.status != 200:
            raise RuntimeError(f"server status {resp.status}")
        return json.loads(resp.read().decode())


def from_local_mem(query: str, k: int):
    out = subprocess.run(["mem", "search", query, "--top-k", str(k), "--json-output"],
                         capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "mem search failed")
    return json.loads(out.stdout or "[]")


def _norm(results):
    """每側各自把分數正規化到 [0,1]（跨索引 IDF 尺度不同，不能比原始分）。"""
    m = max((r.get("score", 0) for r in results), default=0) or 1.0
    for r in results:
        r["_norm"] = r.get("score", 0) / m
    return results


def render(merged, central_tag, n_priv, as_json):
    if as_json:
        return json.dumps({"engines": [central_tag, "LOCAL-PRIVATE"],
                           "results": merged}, ensure_ascii=False)
    lines = [f"[PARALLEL recall: {central_tag} + LOCAL-PRIVATE({n_priv})]"]
    for i, r in enumerate(merged, 1):
        lines.append(f"--- Result {i} [{r.get('_engine')}] (score: {r.get('score', 0):.4f}) ---")
        lines.append(f"Source: {r.get('source', '')}")
        if r.get("heading"):
            lines.append(f"Heading: {r['heading']}")
        c = (r.get("content") or "").strip()
        snip = next((ln.strip() for ln in c.splitlines()
                     if ln.strip() and not ln.strip().startswith(("#", "<!--"))), c[:120])
        lines.append(snip[:120])
        lines.append("")
    return "\n".join(lines).rstrip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    central = {"results": [], "tag": "AX-SERVER bm25"}

    def do_central():
        try:
            central["results"] = from_server(args.query, args.top_k)
        except (urllib.error.URLError, OSError, RuntimeError, ValueError) as e:
            try:  # 中央不可達 → 降級本機 mem（可用性備援）
                central["results"] = from_local_mem(args.query, args.top_k)
                central["tag"] = f"LOCAL-FALLBACK mem/vector (server 不可達:{type(e).__name__})"
            except Exception:
                central["results"] = []
                central["tag"] = "AX-SERVER 不可達"

    # 併行：中央走 thread（HTTP 可能慢），本機私有 in-process（快）
    th = threading.Thread(target=do_central)
    th.start()
    try:
        priv = ax_private_recall.search(args.query, args.top_k)
    except Exception:
        priv = []
    th.join(timeout=TIMEOUT + 2)

    # local-override-team：同一 doc 兩層都有時，本機原始版覆蓋中央遮蔽版、不雙份顯示。
    # stem = 去 .md/尾端 -<hex>/前綴 memory-；用 substring 比對涵蓋中央 lessons-<proj>- 命名。
    def _stem(s):
        s = re.sub(r"\.md$", "", s or "")
        s = re.sub(r"-[0-9a-f]{6,}$", "", s)   # .ax-kb 的 -<hash>
        s = re.sub(r"^memory-", "", s)          # .memsearch 的 memory- 前綴
        return s
    priv_set = {_stem(p.get("source", "")) for p in priv if p.get("source")}
    # local-override：私有 stem 精確等於中央 stem、或為其 dash 分隔後綴（涵蓋中央 lessons-{proj}- 前綴，
    # 且比雙向 substring 安全——避免短 stem 誤刪。同 doc 兩層都有→留本機原始、丟中央遮蔽。
    def _overridden(cs):
        return any(ps and (cs == ps or cs.endswith("-" + ps)) for ps in priv_set)
    kept_central = [c for c in central["results"] if not _overridden(_stem(c.get("source", "")))]
    # RRF 融合（rank-based，不依賴跨索引分數尺度；解 per-side min-max 把弱私有頂到強中央之上的問題）
    RRF = 60
    fused = []
    for rank, r in enumerate(kept_central):
        r["_engine"] = "TEAM" if central["tag"].startswith("AX-SERVER bm25") else "TEAM(fallback)"
        r["_rrf"] = 1.0 / (RRF + rank); fused.append(r)
    for rank, r in enumerate(priv):
        r["_engine"] = "LOCAL-PRIVATE"
        r["_rrf"] = 1.0 / (RRF + rank); fused.append(r)
    merged = sorted(fused, key=lambda r: r.get("_rrf", 0), reverse=True)[:args.top_k]

    if not merged and not central["results"] and not priv:
        print(f"[RECALL-UNAVAILABLE] 中央與本機私有皆無結果", file=sys.stderr)
        print(json.dumps({"engines": [], "results": []}) if args.json else "", end="")
        sys.exit(0)
    print(render(merged, central["tag"], len(priv), args.json))


if __name__ == "__main__":
    main()
