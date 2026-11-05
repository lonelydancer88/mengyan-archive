# -*- coding: utf-8 -*-
"""按清单逐篇抓取孟岩公众号文章，正文逐字转 Markdown 落盘。

用法：
    python3 fetch.py --limit 3        先抓前 3 篇做样本
    python3 fetch.py --all            全量（自动跳过已抓）
    python3 fetch.py --seq 1,5,9      指定编号
"""
import argparse
import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from common import parse_article

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARTICLES = ROOT / "articles"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://mp.weixin.qq.com/",
           "Accept-Language": "zh-CN,zh;q=0.9"}

lock = threading.Lock()
media_all = {}
failed = []
done_count = 0
_local = threading.local()


def get_session(workers):
    """每线程独立 Session，避免多线程共享连接池导致互相干扰。"""
    if not hasattr(_local, "session"):
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=workers, pool_maxsize=workers)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _local.session = s
    return _local.session


def yml_str(s):
    return json.dumps(str(s or ""), ensure_ascii=False)


def render_md(meta, art):
    head = [
        "---",
        f"title: {yml_str(art['title'])}",
        f"date: {yml_str(meta.get('date') or art.get('date') or '')}",
        f"author: {yml_str(meta.get('author') or '孟岩')}",
        f"no: {art.get('no') or ''}",
        f"source: {yml_str(art['url'])}",
        f"images: {len(meta.get('images', []))}",
        "---",
        "",
        f"# {art['title']}",
        "",
        "",
    ]
    body = meta.get("body", "").strip()
    if body.startswith("# " + art["title"]):
        body = body[len("# " + art["title"]):].strip()
    return "\n".join(head) + body + "\n"


def fetch_one(art, workers=4, retries=2):
    session = get_session(workers)
    url = art["url"]
    for attempt in range(retries + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=35)
            r.encoding = "utf-8"
            raw = r.text
            meta = parse_article(raw, url)
            if meta["status"] == "ok":
                return art, meta, None
            err = meta.get("error", "unknown")
            if attempt == retries:
                return art, None, err
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            if attempt == retries:
                return art, None, err
        time.sleep(1.5 * (attempt + 1) + random.random())
    return art, None, "exhausted"


def main():
    global done_count
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seq", default="")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="重新抓取已存在的文件")
    args = ap.parse_args()

    arts = json.loads((DATA / "articles.json").read_text(encoding="utf-8"))
    if args.seq:
        wanted = {int(x) for x in args.seq.split(",") if x.strip().isdigit()}
        arts = [a for a in arts if a["seq"] in wanted]
    elif args.limit:
        arts = arts[:args.limit]
    elif not args.all:
        arts = arts[:3]

    ARTICLES.mkdir(parents=True, exist_ok=True)
    media_path = DATA / "media.json"
    if media_path.exists():
        media_all.update(json.loads(media_path.read_text(encoding="utf-8")))

    todo = []
    for a in arts:
        p = ARTICLES / a["file"]
        if p.exists() and p.stat().st_size > 120 and not args.force:
            continue
        todo.append(a)
    print(f"total={len(arts)}  todo={len(todo)}  skipped={len(arts)-len(todo)}  workers={args.workers}", flush=True)

    t0 = time.time()
    batch_size = args.workers * 8
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        # 小批提交、立即消费落盘，避免结果堆在内存里且进度不可见
        for start in range(0, len(todo), batch_size):
            batch = todo[start:start + batch_size]
            futures = {}
            for a in batch:
                futures[ex.submit(fetch_one, a, args.workers)] = a
                time.sleep(0.2 + random.random() * 0.25)
            for fu in as_completed(futures):
                art, meta, err = fu.result()
                with lock:
                    done_count += 1
                    if meta:
                        (ARTICLES / art["file"]).write_text(render_md(meta, art), encoding="utf-8")
                        media_all[art["file"]] = {"images": meta["images"], "media": meta["media"]}
                        print(f"[{done_count}/{len(todo)}] OK  {meta['char_count']:>6}字  {art['date'] or '?':<16} {art['title'][:34]}", flush=True)
                    else:
                        failed.append({"seq": art["seq"], "title": art["title"], "url": art["url"], "error": err})
                        print(f"[{done_count}/{len(todo)}] FAIL {err}  {art['title'][:34]}", flush=True)
                    if done_count % 20 == 0:
                        media_path.write_text(json.dumps(media_all, ensure_ascii=False, indent=1), encoding="utf-8")
                        (DATA / "failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")

    media_path.write_text(json.dumps(media_all, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / "failed.json").write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDONE ok={len(todo)-len(failed)} failed={len(failed)} elapsed={time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
