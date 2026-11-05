# -*- coding: utf-8 -*-
"""解析公众号自发的三版「文章合集」目录，合并去重成待抓清单。"""
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from common import extract_js_content, slugify

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted((ROOT / "source").glob("index_*.html"))
OUT = ROOT / "data" / "articles.json"

DATE_RE = re.compile(
    r"(\d{4})[-年](\d{1,2})[-月](\d{1,2})日?(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?"
)
SKIP_TITLES = ("会员服务说明", "电子书下载方法", "PDF 电子书")


def norm_date(m):
    y, mo, d, h, mi, sec = m.groups()
    base = f"{y}-{int(mo):02d}-{int(d):02d}"
    if not h:
        return base
    return base + f" {int(h):02d}:{mi}" + (f":{sec}" if sec else "")


def url_key(url):
    q = parse_qs(urlparse(html.unescape(url)).query)
    return "|".join([q.get("__biz", [""])[0], q.get("mid", [""])[0],
                     q.get("idx", ["1"])[0], q.get("sn", [""])[0]])


def parse_source(path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    frag = extract_js_content(raw)
    if not frag:
        print(f"  {path.name}: no js_content", file=sys.stderr)
        return []
    soup = BeautifulSoup(frag, "lxml")
    # 不同整理号用 section 或 p 作为条目容器；p 优先，避免外层 section 重复计入
    containers = soup.find_all(["section", "p"])
    texts = []
    for s in containers:
        t = s.get_text(" ", strip=True).replace("\xa0", " ")
        texts.append(re.sub(r"\s+", " ", t).strip())

    items = []
    for i, sec in enumerate(containers):
        if sec.name == "section" and sec.find("p") and any(
            p.find("a", href=re.compile(r"mp\.weixin\.qq\.com/s")) for p in sec.find_all("p")
        ):
            continue
        links = []
        for a in sec.find_all("a", href=True):
            href = html.unescape(a["href"])
            if "mp.weixin.qq.com/s" not in href or "mid=" not in href or "sn=" not in href:
                continue
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
            if title:
                links.append((title, href))
        if not links:
            continue

        no = None
        m = re.match(r"^(\d{1,3})\b", texts[i])
        if m:
            no = int(m.group(1))

        date = ""
        for j in (i, i + 1, i + 2):
            if j >= len(texts):
                break
            dm = DATE_RE.search(texts[j])
            if dm:
                date = norm_date(dm)
                break

        for title, href in links:
            # 合集里偶尔有「点这里下载电子书」之类的非文章链接
            if no is None and not date:
                continue
            if any(k in title for k in SKIP_TITLES):
                continue
            items.append({"no": no, "title": title, "date": date,
                          "url": href.split("#")[0], "key": url_key(href), "from": path.name})
    return items


def main():
    merged = {}
    for path in SOURCES:
        items = parse_source(path)
        print(f"{path.name}: {len(items)} links")
        for it in items:
            k = it["key"]
            if k not in merged:
                merged[k] = dict(it)
            else:
                cur = merged[k]
                if not cur["date"] and it["date"]:
                    cur["date"] = it["date"]
                if not cur["no"] and it["no"]:
                    cur["no"] = it["no"]

    arts = list(merged.values())
    arts.sort(key=lambda a: (a["date"] or "0000", a["no"] or 0), reverse=True)

    used = set()
    for i, a in enumerate(arts, 1):
        a["seq"] = i
        day = (a["date"] or "unknown")[:10].replace("-", "")
        sn = re.search(r"sn=([0-9a-f]+)", a["url"])
        uid = (sn.group(1)[:8] if sn else str(i).zfill(4))
        base = f"{day}_{uid}_{slugify(a['title'], 30)}"
        fname = base + ".md"
        n = 2
        while fname in used:
            fname = f"{base}_{n}.md"
            n += 1
        used.add(fname)
        a["file"] = fname

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(arts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTOTAL unique: {len(arts)}")
    print(f"WITH DATE  : {sum(1 for a in arts if a['date'])}")
    print(f"DATE RANGE : {min((a['date'] for a in arts if a['date']), default='-')} ~ "
          f"{max((a['date'] for a in arts if a['date']), default='-')}")
    print("\nFIRST 8:")
    for a in arts[:8]:
        print(f"  {a['seq']:>3} {a['date'] or '?':<17} {a['title'][:36]}")
    print("\nLAST 5:")
    for a in arts[-5:]:
        print(f"  {a['seq']:>3} {a['date'] or '?':<17} {a['title'][:36]}")


if __name__ == "__main__":
    main()
