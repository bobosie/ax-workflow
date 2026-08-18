#!/usr/bin/env python3
"""ax_private_recall — 本機私有 recall 層（索引「既有本機檔」，純 stdlib BM25 bigram，可攜免 venv）。

2026-07-20 對抗評估定案（lessons 20260720-private-tier-design-adversarial-verdict）：不複製、不建機敏 map、
不還原——直接索引成員本機既有 curated 檔（PII 留原檔、已 git 保護、零新增攻擊面）。org 版：中央只有遮蔽版
[TEAM]、本機這層是原始全貌[LOCAL-PRIVATE]，recall 併行合併。

索引來源（預設）：~/Projects/*/doc/lessons-learned/*.md + 各 Claude config-dir 的 projects/*/memory/*.md
（要換來源就設 AX_INDEX_GLOBS，冒號分隔的 glob 清單）
- **內容雜湊去重**：三個 config-dir memory 是各自實體目錄（非 symlink），常有同名同內容檔 → 內容 hash 去重
  收斂，避免同一則被索引多次、灌爆 doc-freq。內容不同者保留。
- **BM25Okapi 逐字對齊中央**：idf=log(N-n+0.5)-log(n+0.5) + 負值 epsilon floor（0.25*avg_idf），k1=1.5,b=0.75，
  tk_bigram 同 server.py。故 private 與中央可比、無高頻詞系統性偏差。
- **持久快取**：倒排索引+預算 idf 存 JSON ~/.ax-private/.bm25-cache.json；sig=每檔「路徑:size」（不用 mtime，
  sync cp -r 會刷 mtime）；**+ TTL 30min 兜底**（抓等長內容編輯這類 size 不變的 stale）。**原子寫**(tmp+os.replace)
  防並發寫壞。top-k 內容 lazy 讀原檔。
followup（未做）：上萬檔時 JSON 載入(~21MB)慢 → 改 sqlite/常駐；倒排分片。
"""
import glob
import hashlib
import json
import math
import os
import re
import time

HOME = os.path.expanduser("~")
CACHE = os.path.join(HOME, ".ax-private", ".bm25-cache.json")
_K1, _B, _EPS_FRAC = 1.5, 0.75, 0.25
_TTL = 1800  # 快取最長存活（秒）；size-sig 抓不到等長編輯，TTL 兜底

# 可用 AX_INDEX_GLOBS(冒號分隔) 覆蓋；預設掃本機所有 Claude config-dir 的 per-project memory
_dflt = os.path.join(HOME, "Projects/*/doc/lessons-learned/*.md")
for cfg in sorted(glob.glob(os.path.join(HOME, ".claude*"))):
    _dflt += ":" + os.path.join(cfg, "projects/*/memory/*.md")
SOURCE_GLOBS = (os.environ.get("AX_INDEX_GLOBS") or _dflt).split(":")
# ax-vault 憑證庫「零祕密逐筆摘要」(F4：明確 append，不用 symlink——symlink 會被 memsearch-sync 推上中央；
# 且 ~/.ax-vault 不在任何 sync glob，故摘要只進本機 [LOCAL-PRIVATE]、永不上中央)。祕密值只在 *.age 密文。
SOURCE_GLOBS.append(os.path.join(HOME, ".ax-vault/index/*.md"))


def tk_bigram(s: str):  # 與 server.py 逐字一致
    cjk = re.findall(r"[一-鿿]", s)
    bigrams = [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    unigrams = re.findall(r"[A-Za-z0-9]{2,}", s.lower())
    return bigrams + unigrams + cjk


def _files():
    fs = []
    for g in SOURCE_GLOBS:
        fs.extend(glob.glob(g))
    return sorted(set(fs))


def _sig(files):
    # 路徑+size（不用 mtime：sync cp -r 常刷 mtime 但內容不變→避免每次失效重建）
    parts = []
    for f in files:
        try:
            parts.append(f"{f}:{os.stat(f).st_size}")
        except OSError:
            continue
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _build(files):
    """倒排索引 + 預算 Okapi idf。內容雜湊去重（同內容只索引一次）。不存全文（top-k lazy 讀）。"""
    postings, dls, sources, seen = {}, [], [], set()
    for f in files:
        try:
            c = open(f, encoding="utf-8").read()
        except Exception:
            continue
        if not c.strip():
            continue
        ch = hashlib.sha256(c.encode()).hexdigest()
        if ch in seen:      # 跨帳號同內容 → 只索引一次（避免 doc-freq 灌水）
            continue
        seen.add(ch)
        toks = tk_bigram(c)
        idx = len(sources)
        sources.append(f)
        dls.append(len(toks))
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        for t, n in tf.items():
            postings.setdefault(t, []).append([idx, n])
    N = len(sources)
    avgdl = (sum(dls) / N) if N else 1
    # Okapi idf + epsilon floor（與 rank_bm25 BM25Okapi 一致）
    idf, idf_sum, negs = {}, 0.0, []
    for t, pl in postings.items():
        n = len(pl)
        v = math.log(N - n + 0.5) - math.log(n + 0.5)
        idf[t] = v; idf_sum += v
        if v < 0:
            negs.append(t)
    eps = _EPS_FRAC * (idf_sum / len(idf)) if idf else 0
    for t in negs:
        idf[t] = eps
    return {"postings": postings, "idf": idf, "dls": dls, "sources": sources, "N": N, "avgdl": avgdl}


def _load_or_build():
    files = _files()
    sig = _sig(files)
    if os.path.exists(CACHE):
        try:
            fresh = (time.time() - os.stat(CACHE).st_mtime) < _TTL
            cached = json.load(open(CACHE))
            if fresh and cached.get("sig") == sig:
                return cached["idx"]
        except Exception:
            pass
    idx = _build(files)
    try:  # 原子寫：tmp + os.replace（POSIX 同 fs 原子），防並發寫壞
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + f".tmp.{os.getpid()}"
        json.dump({"sig": sig, "idx": idx}, open(tmp, "w"))
        os.chmod(tmp, 0o600)  # F3：倒排 cache 含被索引檔的所有 token，收成 600（原為 0644 world-readable）
        os.replace(tmp, CACHE)
    except Exception:
        pass
    return idx


def search(query, k=5):
    idx = _load_or_build()
    N, avgdl = idx["N"], idx["avgdl"]
    if not N:
        return []
    postings, idfm, dls, sources = idx["postings"], idx["idf"], idx["dls"], idx["sources"]
    scores = {}
    for term in set(tk_bigram(query)):
        pl = postings.get(term)
        if not pl:
            continue
        w = idfm.get(term, 0)
        for di, f in pl:
            scores[di] = scores.get(di, 0.0) + w * (f * (_K1 + 1)) / (f + _K1 * (1 - _B + _B * dls[di] / avgdl))
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
    out = []
    for di, sc in top:
        if sc <= 0:
            continue
        src = sources[di]
        try:
            content = open(src, encoding="utf-8").read()
        except Exception:
            content = ""
        out.append({"source": os.path.basename(src), "path": src, "score": sc, "content": content})
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--top-k", type=int, default=5)
    a = ap.parse_args()
    print(json.dumps([{k: v for k, v in r.items() if k != "content"} for r in search(a.query, a.top_k)], ensure_ascii=False))
