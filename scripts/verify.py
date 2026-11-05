# -*- coding: utf-8 -*-
"""归档质量校验：覆盖率、异常页、短文与图片分布。"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ART = ROOT / "articles"
arts = json.loads((DATA / "articles.json").read_text(encoding="utf-8"))
media = json.loads((DATA / "media.json").read_text(encoding="utf-8")) if (DATA / "media.json").exists() else {}

BAD = ["环境异常", "该内容已被发布者删除", "此内容因违规无法查看", "参数错误"]
missing, short, dirty = [], [], []
chars, imgs = [], []
for a in arts:
    p = ART / a["file"]
    if not p.exists():
        missing.append(a)
        continue
    txt = p.read_text(encoding="utf-8")
    body = txt.split("---\n", 2)[-1]
    n = len(re.sub(r"\s", "", body))
    chars.append(n)
    imgs.append(len(media.get(a["file"], {}).get("images", [])))
    if n < 200:
        short.append((a, n))
    hit = [b for b in BAD if b in body]
    if hit:
        dirty.append((a, hit))

print(f"目录条目      : {len(arts)}")
print(f"已落盘        : {len(chars)}")
print(f"缺失          : {len(missing)}")
print(f"正文总字数    : {sum(chars):,}")
print(f"平均/中位字数 : {sum(chars)//max(1,len(chars)):,} / {sorted(chars)[len(chars)//2] if chars else 0:,}")
print(f"图片总数      : {sum(imgs):,}   图片数分布: {dict(Counter(imgs).most_common(6))}")
print(f"异常页        : {len(dirty)}")
print(f"短文(<200字)  : {len(short)}")

if missing:
    print("\n--- 缺失（前 25）---")
    for a in missing[:25]:
        print(f"  {a['seq']:>3} {a['date'] or '?':<17} {a['title'][:40]}")
if dirty:
    print("\n--- 异常页 ---")
    for a, hit in dirty[:20]:
        print(f"  {a['seq']:>3} {hit} {a['title'][:36]}")
if short:
    print("\n--- 短文（前 25）---")
    for a, n in short[:25]:
        print(f"  {a['seq']:>3} {n:>5}字 {a['date'] or '?':<17} {a['title'][:40]}")

fp = DATA / "failed.json"
if fp.exists():
    f = json.loads(fp.read_text(encoding="utf-8"))
    print(f"\n--- 本轮抓取失败 {len(f)} 篇 ---")
    for x in f[:25]:
        print(f"  {x['seq']:>3} {x['error'][:28]:<30} {x['title'][:36]}")
