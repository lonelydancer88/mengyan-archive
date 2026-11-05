# -*- coding: utf-8 -*-
"""生成归档索引：index.md、自包含可阅读的 index.html、逐字全文合集。

index.html 把全部正文内嵌进页面（script type="text/plain"），
点标题直接在页内阅读，不依赖 articles/ 目录能否被静态服务托管。
"""
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ARTICLES = ROOT / "articles"
arts = json.loads((DATA / "articles.json").read_text(encoding="utf-8"))
failed = {}
fp = DATA / "failed.json"
if fp.exists():
    failed = {f["title"]: f["error"] for f in json.loads(fp.read_text(encoding="utf-8"))}

media = {}
mp = DATA / "media.json"
if mp.exists():
    media = json.loads(mp.read_text(encoding="utf-8"))

for a in arts:
    p = ARTICLES / a["file"]
    if p.exists():
        txt = p.read_text(encoding="utf-8")
        body = txt.split("---\n", 2)[-1]
        a["chars"] = len(re.sub(r"\s", "", body))
        a["imgs"] = len(media.get(a["file"], {}).get("images", []))
        a["state"] = "ok"
    else:
        a["chars"] = 0
        a["imgs"] = 0
        a["state"] = "failed" if a["title"] in failed else "missing"

by_year = defaultdict(list)
for a in arts:
    by_year[(a["date"] or "未标日期")[:4]].append(a)
years = sorted(by_year, reverse=True)

ok = [a for a in arts if a["state"] == "ok"]
total_chars = sum(a["chars"] for a in ok)
dates = sorted(a["date"] for a in ok if a["date"])

# ---------- index.md ----------
lines = [
    "# 孟岩公众号「孟岩」文章归档",
    "",
    f"共 {len(arts)} 篇（已抓 {len(ok)} 篇），{dates[0][:10] if dates else '-'} 至 {dates[-1][:10] if dates else '-'}，正文合计约 {total_chars:,} 字。",
    "",
    "目录来自四份《文章合集 / 阅读导航》页，合并去重；正文逐字保留，图片以 `[图片]` 占位，原图地址见 `data/media.json`。",
    "",
]
for y in years:
    lines += [f"## {y}（{len(by_year[y])} 篇）", ""]
    for a in by_year[y]:
        mark = "" if a["state"] == "ok" else " `未抓取`"
        lines.append(f"- {a['date'] or '日期未知'} · [{a['title']}](articles/{quote(a['file'], safe='')}){mark}")
    lines.append("")
(ROOT / "index.md").write_text("\n".join(lines), encoding="utf-8")

# ---------- 全文合集（按时间倒序，逐字拼接） ----------
vol = ["# 孟岩公众号文章合集", "",
       f"共 {len(ok)} 篇，{dates[0][:10] if dates else '-'} 至 {dates[-1][:10] if dates else '-'}。正文逐字保留，图片以 [图片] 占位。", "", "---", ""]
for a in ok:
    body = (ARTICLES / a["file"]).read_text(encoding="utf-8").split("---\n", 2)[-1].strip()
    vol += [body, "", "", "---", ""]
(ROOT / "孟岩公众号文章合集.md").write_text("\n".join(vol), encoding="utf-8")


# ---------- Markdown -> HTML 片段 ----------
def esc(s):
    return html.escape(str(s or ""), quote=True)


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`([^`]+?)`", r"<code>\1</code>", t)
    return t


def table_html(rows):
    parsed = []
    for r in rows:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells):
            continue
        parsed.append(cells)
    if not parsed:
        return ""
    head, rest = parsed[0], parsed[1:]
    out = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead>"
    if rest:
        out += "<tbody>" + "".join(
            "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in rest
        ) + "</tbody>"
    return out + "</table>"


def is_block(s):
    return bool(
        re.match(r"^#{1,6}\s", s) or s.startswith("|") or s.startswith("> ")
        or re.match(r"^([-*]|\d+\.)\s", s) or re.match(r"^-{3,}$", s)
        or re.match(r"^\[(图片|视频|音频)\]$", s) or s.startswith("```")
    )


def md_to_html(md, title, images):
    """把一篇归档 Markdown 转成 HTML 片段；图片占位按出现顺序挂原图链接。"""
    lines = md.splitlines()
    out = []
    img_i = 0
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        # 主标题已在阅读器顶栏显示，正文里不重复
        if i == 0 and s == "# " + title:
            i += 1
            continue
        if s.startswith("```"):
            j, buf = i + 1, []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(html.escape(lines[j]))
                j += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            i = j + 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lv = min(6, len(m.group(1)))
            out.append(f"<h{lv}>" + inline(m.group(2)) + f"</h{lv}>")
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            out.append("<hr>")
            i += 1
            continue
        if s.startswith("|") and s.endswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(table_html(rows))
            continue
        ph = re.match(r"^\[(图片|视频|音频)\]$", s)
        if ph:
            label = ph.group(1)
            url = images[img_i] if label == "图片" and img_i < len(images) else ""
            img_i += 1 if label == "图片" else 0
            link = (f' <a href="{esc(url)}" target="_blank" rel="noopener">查看原图 ↗</a>' if url else "")
            out.append(f'<div class="ph">[{label}]{link}</div>')
            i += 1
            continue
        if s.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + "".join(f"<p>{inline(x)}</p>" for x in buf if x) + "</blockquote>")
            continue
        lm = re.match(r"^(\d+\.|[-*])\s+(.*)$", s)
        if lm:
            ordered = lm.group(1)[0].isdigit()
            items = []
            while i < len(lines):
                t = lines[i].strip()
                mo = re.match(r"^\d+\.\s+(.*)$", t) if ordered else re.match(r"^[-*]\s+(.*)$", t)
                if not mo:
                    break
                items.append("<li>" + inline(mo.group(1)) + "</li>")
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        buf = []
        while i < len(lines):
            t = lines[i].strip()
            if not t or is_block(t):
                break
            buf.append(inline(t))
            i += 1
        if buf:
            out.append("<p>" + "<br>".join(buf) + "</p>")
    return "\n".join(out)


# ---------- 列表与内嵌正文 ----------
def safe_doc(fragment):
    # 防止正文里出现 </script> 截断数据块
    return fragment.replace("</script", "<\\/script")


rows, docs = [], []
for y in years:
    rows.append(f'<h2 class="year">{esc(y)} <span>{len(by_year[y])} 篇</span></h2>')
    rows.append('<div class="list">')
    for a in by_year[y]:
        cls = "item ok" if a["state"] == "ok" else "item bad"
        tail = (f'{a["chars"]:,} 字' if a["state"] == "ok" else "未抓取")
        if a["imgs"]:
            tail += f' · {a["imgs"]} 图'
        rows.append(
            f'<div class="{cls}" data-seq="{a["seq"]}" data-title="{esc(a["title"].lower())}" '
            f'data-date="{esc((a["date"] or "日期未知")[:16])}" data-url="{esc(a["url"])}">'
            f'<span class="date">{esc((a["date"] or "日期未知")[:10])}</span>'
            f'<a class="title" href="#doc-{a["seq"]}">{esc(a["title"])}</a>'
            f'<span class="meta">{esc(tail)}</span>'
            f'<a class="orig" href="{esc(a["url"])}" target="_blank" rel="noopener" title="打开微信原文">原文 ↗</a>'
            f'</div>'
        )
        if a["state"] == "ok":
            md = (ARTICLES / a["file"]).read_text(encoding="utf-8").split("---\n", 2)[-1]
            imgs = media.get(a["file"], {}).get("images", [])
            frag = md_to_html(md, a["title"], imgs)
        else:
            reason = failed.get(a["title"], "未能抓取")
            frag = (f'<div class="ph">这篇原文已经不可访问（{esc(reason)}），没有抓到正文。'
                    f'可以点右上角「微信原文」碰碰运气。</div>')
        docs.append(f'<script type="text/plain" id="doc-{a["seq"]}">{safe_doc(frag)}</script>')
    rows.append('</div>')

PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>孟岩公众号文章归档</title>
<style>
:root{--bg:#faf9f6;--card:#fff;--line:#e8e5df;--ink:#26241f;--muted:#8b877e;--accent:#6b6f9c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",sans-serif}
.wrap{max-width:940px;margin:0 auto;padding:48px 24px 80px}
header h1{font-size:28px;font-weight:600;letter-spacing:.02em;margin:0 0 8px}
header p{color:var(--muted);margin:0 0 22px;font-size:14px}
.stats{display:flex;gap:28px;flex-wrap:wrap;padding:16px 20px;background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:20px}
.stats b{display:block;font-size:20px;font-weight:600;line-height:1.3}
.stats span{font-size:12px;color:var(--muted)}
#q{width:100%;padding:12px 16px;border:1px solid var(--line);border-radius:8px;background:var(--card);font-size:15px;color:var(--ink);outline:none}
#q:focus{border-color:var(--accent)}
h2.year{font-size:14px;font-weight:600;color:var(--muted);margin:32px 0 8px;letter-spacing:.08em}
h2.year span{font-weight:400;opacity:.7}
.list{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.item{display:flex;align-items:baseline;gap:14px;padding:11px 16px;border-bottom:1px solid var(--line)}
.item:last-child{border-bottom:0}
.item:hover{background:#f6f5f1}
.item .date{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;flex:0 0 84px}
.item .title{flex:1;text-decoration:none;color:var(--ink);font-size:15px;cursor:pointer}
.item .title:hover{color:var(--accent)}
.item .meta{font-size:12px;color:var(--muted);white-space:nowrap}
.item .orig{font-size:12px;color:var(--accent);text-decoration:none;white-space:nowrap}
.item.bad{opacity:.55}
.hide{display:none!important}
footer{margin-top:36px;color:var(--muted);font-size:12px;line-height:1.9}
.overlay{position:fixed;inset:0;background:rgba(38,36,31,.42);z-index:50;display:none;padding:22px}
.overlay.on{display:flex;justify-content:center;align-items:center}
.reader{background:var(--card);width:min(820px,100%);height:100%;max-height:920px;border-radius:12px;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 18px 60px rgba(0,0,0,.22)}
.rhead{padding:18px 26px 14px;border-bottom:1px solid var(--line);flex:0 0 auto}
.rhead .rtopline{display:flex;align-items:flex-start;gap:16px}
.rhead h1{font-size:21px;font-weight:600;line-height:1.45;margin:0;flex:1}
.rmeta{color:var(--muted);font-size:12px;margin-top:6px}
.rbtns{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.rbtns a,.rbtns button{font:12px/1 inherit;font-size:12px;color:var(--accent);text-decoration:none;background:#f4f3ef;border:1px solid var(--line);border-radius:6px;padding:6px 11px;cursor:pointer}
.rbtns a:hover,.rbtns button:hover:not(:disabled){border-color:var(--accent)}
.rbtns button:disabled{opacity:.4;cursor:default}
.rbtns .close{margin-left:auto;color:var(--muted)}
.rbody{overflow:auto;padding:26px 34px 70px;font-size:16px;line-height:1.95;color:#2d2a25}
.rbody h1{font-size:21px;margin:30px 0 14px;font-weight:600}
.rbody h2{font-size:18px;margin:34px 0 14px;font-weight:600;color:#3a4657}
.rbody h3,.rbody h4{font-size:16px;margin:26px 0 10px;font-weight:600}
.rbody p{margin:0 0 1.15em}
.rbody a{color:var(--accent);text-decoration:underline;text-underline-offset:2px}
.rbody blockquote{margin:1.4em 0;padding:2px 0 2px 16px;border-left:3px solid #d9d6ce;color:#5c5850}
.rbody blockquote p{margin:.4em 0}
.rbody ul,.rbody ol{margin:0 0 1.2em;padding-left:1.6em}
.rbody li{margin:.3em 0}
.rbody hr{border:0;border-top:1px solid var(--line);margin:30px 0}
.rbody strong{font-weight:600}
.rbody code{background:#f4f3ef;border-radius:3px;padding:1px 4px;font-size:.9em}
.rbody pre{background:#f4f3ef;padding:14px;border-radius:8px;overflow:auto;font-size:13px;line-height:1.6}
.rbody pre code{background:none;padding:0}
.rbody table{border-collapse:collapse;width:100%;margin:1.4em 0;font-size:14px}
.rbody th,.rbody td{border:1px solid var(--line);padding:7px 10px;text-align:left}
.rbody th{background:#f7f6f2;font-weight:600}
.ph{margin:1.4em 0;padding:14px;background:#f7f6f2;border:1px dashed #ddd9d0;border-radius:8px;text-align:center;color:var(--muted);font-size:13px}
.ph a{font-size:12px;margin-left:8px}
@media(max-width:640px){.wrap{padding:24px 14px 60px}.item{flex-wrap:wrap;gap:6px}.item .date{flex-basis:100%}.item .meta,.item .orig{font-size:11px}.overlay{padding:0}.reader{border-radius:0;max-height:none}.rhead{padding:14px 18px 12px}.rbody{padding:20px 18px 60px;font-size:15px}}
</style></head><body>
<div class="wrap">
<header><h1>孟岩 · 公众号文章归档</h1>
<p>点标题直接在页内读全文；正文逐字保留，图片以占位块标出并附原图链接。</p></header>
<div class="stats">
<div><b>__TOTAL__</b><span>目录条目</span></div>
<div><b>__OK__</b><span>已抓正文</span></div>
<div><b>__CHARS__</b><span>正文总字数</span></div>
<div><b>__RANGE__</b><span>时间跨度</span></div>
</div>
<input id="q" placeholder="搜索标题…" autocomplete="off">
__ROWS__
<footer>全文已内嵌在本页，离线也能读。单篇 Markdown 与图片地址分别在 articles/ 和 data/media.json。<br>
「原文 ↗」跳转微信原页面；按 Esc 或点遮罩关闭阅读器。</footer>
</div>
<div class="overlay" id="overlay"><div class="reader" role="dialog" aria-modal="true">
<div class="rhead">
<div class="rtopline"><h1 id="rtitle"></h1><button class="close" id="rclose" type="button">关闭 ✕</button></div>
<div class="rmeta" id="rmeta"></div>
<div class="rbtns">
<button type="button" id="rprev">← 上一篇</button><button type="button" id="rnext">下一篇 →</button>
<a id="rorig" href="#" target="_blank" rel="noopener">微信原文 ↗</a>
</div></div>
<div class="rbody" id="rbody"></div>
</div></div>
__DOCS__
<script>
(function(){
  const q=document.getElementById('q');
  const overlay=document.getElementById('overlay');
  const rbody=document.getElementById('rbody');
  const rtitle=document.getElementById('rtitle');
  const rmeta=document.getElementById('rmeta');
  const rorig=document.getElementById('rorig');
  const rprev=document.getElementById('rprev');
  const rnext=document.getElementById('rnext');
  const items=[...document.querySelectorAll('.item')];
  const seqs=items.map(x=>+x.dataset.seq);
  let current=null;

  q.addEventListener('input',()=>{
    const k=q.value.trim().toLowerCase();
    items.forEach(el=>el.classList.toggle('hide',!!k&&!el.dataset.title.includes(k)));
    document.querySelectorAll('.list').forEach(list=>{
      const vis=[...list.querySelectorAll('.item')].some(x=>!x.classList.contains('hide'));
      list.classList.toggle('hide',!vis);
      const y=list.previousElementSibling;
      if(y&&y.classList.contains('year'))y.classList.toggle('hide',!vis);
    });
  });

  function openDoc(seq){
    const src=document.getElementById('doc-'+seq);
    const item=items.find(x=>+x.dataset.seq===seq);
    if(!src||!item)return;
    rbody.innerHTML=src.textContent;
    rtitle.textContent=item.querySelector('.title').textContent;
    rmeta.textContent=item.dataset.date+' · '+item.querySelector('.meta').textContent;
    rorig.href=item.dataset.url;
    const idx=seqs.indexOf(seq);
    rprev.disabled=idx<=0;
    rnext.disabled=idx>=seqs.length-1;
    current=seq;
    overlay.classList.add('on');
    document.body.style.overflow='hidden';
    rbody.scrollTop=0;
  }
  function closeDoc(){
    overlay.classList.remove('on');
    document.body.style.overflow='';
    current=null;
  }
  function sync(){
    const m=/^#doc-(\\d+)$/.exec(location.hash);
    if(m)openDoc(+m[1]); else closeDoc();
  }
  items.forEach(item=>{
    item.querySelector('.title').addEventListener('click',e=>{
      e.preventDefault();
      const seq=+item.dataset.seq;
      if(location.hash==='#doc-'+seq)openDoc(seq); else location.hash='doc-'+seq;
    });
  });
  document.getElementById('rclose').addEventListener('click',()=>{location.hash='';closeDoc();});
  overlay.addEventListener('click',e=>{if(e.target===overlay){location.hash='';closeDoc();}});
  document.addEventListener('keydown',e=>{
    if(e.key==='Escape'&&overlay.classList.contains('on')){location.hash='';closeDoc();}
    if(!overlay.classList.contains('on'))return;
    const i=seqs.indexOf(current);
    if(e.key==='ArrowLeft'&&i>0)location.hash='doc-'+seqs[i-1];
    if(e.key==='ArrowRight'&&i<seqs.length-1)location.hash='doc-'+seqs[i+1];
  });
  rprev.addEventListener('click',()=>{const i=seqs.indexOf(current);if(i>0)location.hash='doc-'+seqs[i-1];});
  rnext.addEventListener('click',()=>{const i=seqs.indexOf(current);if(i<seqs.length-1)location.hash='doc-'+seqs[i+1];});
  window.addEventListener('hashchange',sync);
  sync();
})();
</script></body></html>"""

page = (PAGE.replace("__TOTAL__", str(len(arts)))
            .replace("__OK__", str(len(ok)))
            .replace("__CHARS__", f"{total_chars:,}")
            .replace("__RANGE__", f"{(dates[0][:4] if dates else '-')}–{(dates[-1][:4] if dates else '-')}")
            .replace("__ROWS__", "\n".join(rows))
            .replace("__DOCS__", "\n".join(docs)))
(ROOT / "index.html").write_text(page, encoding="utf-8")
print(f"index.md / 孟岩公众号文章合集.md / index.html 已生成：{len(arts)} 篇，"
      f"内嵌正文 {len(docs)} 篇，正文 {total_chars:,} 字，HTML {len(page)/1024/1024:.1f} MB")
