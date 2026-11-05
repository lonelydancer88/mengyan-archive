"""生成《书单与访谈》HTML 与 Markdown。"""
import html
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# 原文语境不是书，或豆瓣误匹配到不相干出版物的条目
BLACKLIST = {
    "无人知晓", "华尔街日报", "金融时报", "新京报", "财经", "十三邀", "组织进化论",
    "让奇迹发生", "所有命运赠送的礼物，早已在暗中标好了价格", "无限游戏",
    "肖申克的救赎", "隐秘的角落", "绿里", "纸牌屋", "少年派的奇幻漂流",
    "丹宸永固——紫禁城建成六百年", "颠覆式创新", "深度学习基础", "聪明投资者",
    "三段论", "三国志·武帝纪", "孙子兵法·地形", "念奴娇·赤壁怀古",
    "感悟与成长", "停战协定", "心理学年鉴", "Howtodogreatwork",
    "中国统计年鉴2023", "中国大类资产投资2025年报", "养老金保护法",
    "失败", "礼物", "网", "零度", "理性", "感受", "空", "中", "行星",
}

# 同一本书的不同写法 -> 主名
ALIAS = {
    "原则Principles": "原则",
    "巴菲特和索罗斯的投资习惯": "巴菲特与索罗斯的投资习惯",
    "高效能人士的7个习惯": "高效能人士的七个习惯",
    "投资中最重要的事": "投资最重要的事",
    "让伟大不能被计划": "为什么伟大不能被计划",
    "写出你心": "写出我心",
    "写作那回事儿": "写作这回事",
    "富爸爸穷爸爸": "富爸爸，穷爸爸",
    "巴菲特致股东信": "巴菲特致股东的信",
    "文明、现代化、价值投资和中国": "文明、现代化、价值投资与中国",
    "投资中不简单的事儿": "投资中不简单的事",
    "股市进阶之道----一个散户的自我修养": "股市进阶之道",
    "制造消费者：消费主义全球史": "制造消费者",
    "重来3": "重来3：跳出疯狂的忙碌",
    "创造日本1853-1964": "创造日本",
    "天朝的崩溃：鸦片战争再研究": "天朝的崩溃",
    "不落俗套的成功:最好的个人投资方法": "不落俗套的成功",
    "创意行为·存在即答案": "创意行为",
    "StartWithWhy": "Start with Why",
    "StartwithWhy": "Start with Why",
    "Theinnergameoftennis": "The Inner Game of Tennis",
    "TheInnergameofTennis": "The Inner Game of Tennis",
    "TheinnergameofTennis": "The Inner Game of Tennis",
    "Howtodogreatwork": "How to Do Great Work",
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def build_books():
    rows = json.loads((DATA /"douban_books.json").read_text(encoding="utf-8"))
    rows = [r for r in rows if r["mentioned_as"] not in BLACKLIST]

    # 先按别名把提及次数并到主名（同书不同版本）
    by_alias = defaultdict(list)
    for r in rows:
        key = ALIAS.get(r["mentioned_as"], r["mentioned_as"])
        by_alias[key].append(r)
    merged = []
    for key, group in by_alias.items():
        base = max(group, key=lambda x: (x["mentions"], x["rating"] or 0))
        item = dict(base)
        item["mentioned_as"] = key
        item["mentions"] = sum(x["mentions"] for x in group)
        item["variants"] = sorted({x["mentioned_as"] for x in group} - {key})
        merged.append(item)

    # 再按豆瓣 id 合并（不同写法命中同一条目）
    by_id = defaultdict(list)
    for r in merged:
        by_id[r["id"]].append(r)
    final = []
    for _id, group in by_id.items():
        base = max(group, key=lambda x: (x["mentions"], x["rating"] or 0))
        item = dict(base)
        item["mentions"] = sum(x["mentions"] for x in group)
        item["variants"] = sorted({v for x in group for v in ([x["mentioned_as"]] + x.get("variants", []))} - {item["mentioned_as"]})
        final.append(item)

    # 豆瓣搜索接口限流，这一本手工补：中文版评分取自公开书单的豆瓣引用值
    final.append({
        "mentioned_as": "点球成金", "mentions": 8,
        "douban_title": "点球成金（Moneyball 中文版）", "douban_author": "迈克尔·刘易斯",
        "press": None, "year": None, "rating": 8.4, "votes": None,
        "id": "search", "url": "https://book.douban.com/subject_search?search_text=%E7%82%B9%E7%90%83%E6%88%90%E9%87%91",
        "variants": [], "note": "中文版；英文原版 Moneyball 豆瓣 8.7",
    })
    final.sort(key=lambda x: (-x["mentions"], -(x["rating"] or 0), x["douban_title"]))
    return final


CSS = """
:root{--bg:#faf9f6;--card:#fff;--line:#e8e5df;--ink:#26241f;--muted:#8b877e;--accent:#6b6f9c;--warm:#a4543c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:44px 24px 90px}
header h1{font-size:27px;font-weight:600;margin:0 0 8px}
header p{color:var(--muted);margin:0 0 20px;font-size:14px}
.stats{display:flex;gap:26px;flex-wrap:wrap;padding:15px 20px;background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:18px}
.stats b{display:block;font-size:20px;font-weight:600;line-height:1.3}
.stats span{font-size:12px;color:var(--muted)}
#q{width:100%;padding:11px 15px;border:1px solid var(--line);border-radius:8px;background:var(--card);font-size:15px;color:var(--ink);outline:none;margin-bottom:10px}
#q:focus{border-color:var(--accent)}
.tabs{display:flex;gap:8px;margin-bottom:22px;flex-wrap:wrap}
.tabs button{border:1px solid var(--line);background:var(--card);color:var(--muted);padding:6px 14px;border-radius:20px;font-size:13px;cursor:pointer}
.tabs button.on{background:var(--accent);border-color:var(--accent);color:#fff}
h2{font-size:17px;font-weight:600;margin:34px 0 6px}
h2 small{font-weight:400;color:var(--muted);font-size:13px;margin-left:8px}
.note{color:var(--muted);font-size:13px;margin:0 0 12px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:14px}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f4f2ed;font-weight:600;font-size:12px;color:var(--muted);letter-spacing:.03em;white-space:nowrap}
tr:last-child td{border-bottom:none}
tr.hide{display:none}
td.r{white-space:nowrap;font-variant-numeric:tabular-nums}
.rate{font-weight:600;color:var(--warm)}
.rate.low{color:var(--muted);font-weight:400}
a{color:#4c5680;text-decoration:none}
a:hover{text-decoration:underline}
.sub{color:var(--muted);font-size:12px;display:block}
.iv td:first-child{width:22%}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
.back{display:inline-block;margin-bottom:14px;font-size:13px}
"""


def book_rows(books):
    out = []
    for b in books:
        rating = b.get("rating")
        rate = f'<span class="rate">{rating:.1f}</span>' if rating and rating >= 8 else (
            f'<span class="rate low">{rating:.1f}</span>' if rating else '<span class="sub">暂无</span>')
        votes = f'{b["votes"]:,}' if b.get("votes") else "—"
        title = esc(b["douban_title"])
        alias = ""
        if b["douban_title"] != b["mentioned_as"]:
            alias = f'<span class="sub">原文作《{esc(b["mentioned_as"])}》</span>'
        variants = ""
        if b.get("variants"):
            variants = '<span class="sub">另作：' + "、".join(esc(v) for v in b["variants"][:3]) + '</span>'
        note = f'<span class="sub">{esc(b["note"])}</span>' if b.get("note") else ""
        out.append(
            f'<tr data-s="{esc((b["douban_title"]+b["mentioned_as"]+(b["douban_author"] or ""))).lower()}">'
            f'<td><a href="{esc(b["url"])}" target="_blank" rel="noopener">{title} ↗</a>{alias}{variants}{note}</td>'
            f'<td>{esc(b["douban_author"])}</td>'
            f'<td class="r">{rate}</td><td class="r sub">{votes}</td>'
            f'<td class="r">{b["mentions"]}</td></tr>')
    return "\n".join(out)


def md_books(books):
    lines = ["| 书名 | 作者 | 豆瓣评分 | 评价人数 | 提及次数 |", "|---|---|---|---|---|"]
    for b in books:
        r = b.get("rating")
        votes = f'{b["votes"]:,}' if b.get("votes") else "—"
        lines.append(f'| [{b["douban_title"]}]({b["url"]}) | {b["douban_author"] or "—"} | {f"{r:.1f}" if r else "—"} | {votes} | {b["mentions"]} |')
    return "\n".join(lines)


def main():
    books = build_books()
    interviews = json.loads((DATA /"interviews.json").read_text(encoding="utf-8"))
    rated = [b for b in books if b.get("rating")]
    often = [b for b in books if b["mentions"] >= 3]
    rest = [b for b in books if b["mentions"] < 3]

    # 访谈 HTML
    own_rows = "\n".join(
        f'<tr data-s="{esc((x["name"]+x["detail"]+x["source"]).lower())}"><td><b>{esc(x["name"])}</b></td>'
        f'<td>{esc(x["detail"])}<span class="sub">{esc(x["source"])}</span></td></tr>' for x in interviews["own"])
    quoted_rows = "\n".join(
        f'<tr data-s="{esc((x["who"]+x["what"]+x["source"]).lower())}"><td><b>{esc(x["who"])}</b></td>'
        f'<td>{esc(x["what"])}<span class="sub">{esc(x["source"])}</span></td></tr>' for x in interviews["quoted"])
    prog_rows = "\n".join(
        f'<tr data-s="{esc((x["name"]+x["note"]).lower())}"><td><b>{esc(x["name"])}</b></td>'
        f'<td>{esc(x["note"])}</td></tr>' for x in interviews["programs"])

    book_table = lambda rows: (
        '<table class="books"><thead><tr><th>书名（点开豆瓣）</th><th>作者</th><th>评分</th><th>评价人数</th><th>提及次数</th></tr></thead>'
        f'<tbody>{book_rows(rows)}</tbody></table>')

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>孟岩提到的书与访谈</title>
<style>{CSS}</style></head><body><div class="wrap">
<a class="back" href="index.html">← 返回文章归档</a>
<header><h1>孟岩提到的书与访谈</h1>
<p>从 423 篇公众号文章（2016–2026）里逐条核对出来的，书名后附豆瓣评分。评分抓取于 2026-11-05，会随豆瓣变动。</p></header>
<div class="stats">
<div><b>{len(books)}</b><span>本书 / 出版物</span></div>
<div><b>{len(rated)}</b><span>本有豆瓣评分</span></div>
<div><b>{len(interviews['own'])}</b><span>档他主理或参与的播客</span></div>
<div><b>{len(interviews['quoted'])}</b><span>次引用他人访谈</span></div>
<div><b>{len(interviews['programs'])}</b><span>个提到的节目</span></div>
</div>
<input id="q" placeholder="搜书名、作者、人名、节目名…" autocomplete="off">
<div class="tabs"><button class="on" data-sort="mentions">按提及次数</button><button data-sort="rating">按豆瓣评分</button><button data-sort="reset">恢复原始顺序</button></div>

<h2>反复提到的书 <small>文中出现 3 次以上，{len(often)} 本</small></h2>
<p class="note">这几本大致能看出他的阅读底盘：格雷厄姆、霍华德·马克斯、塔勒布那一脉，加上冥想、写作和创业自传。</p>
{book_table(often)}
<h2>其余提到的书 <small>{len(rest)} 本</small></h2>
{book_table(rest)}

<h2>他自己主理 / 参与的播客与对谈 <small>{len(interviews['own'])} 条</small></h2>
<p class="note">《无人知晓》占了大半，括号里是文中能定位到的嘉宾或单期；出处列的是提到它的那篇文章。</p>
<table class="iv"><tbody>{own_rows}</tbody></table>

<h2>他引用、推荐过的访谈 <small>{len(interviews['quoted'])} 条</small></h2>
<p class="note">这些不是节目名，而是他在文章里具体引了某人的某次采访、专访或访谈纪要。</p>
<table class="iv"><tbody>{quoted_rows}</tbody></table>

<h2>他提到的访谈 / 播客节目 <small>{len(interviews['programs'])} 个</small></h2>
<p class="note">包括他自己列过的收听清单、文中随手提到的节目，以及几部访谈式纪录片。</p>
<table class="iv"><tbody>{prog_rows}</tbody></table>

<footer>
口径说明：书以原文里出现的书名号为线索，逐个用豆瓣图书条目核对，剔除了媒体名、报告、法规、播客栏目和明显错配的条目；同一本书的不同写法、不同版本合并计一次。少数条目（如《点球成金》《大空头》《西游记》《哈利·波特》）原文里书与影视兼指，仍按同名出版物收录。个别书豆瓣没有评分或评价人数不足，标为「暂无」。《点球成金》因豆瓣搜索接口当时限流，中文版 8.4 取自公开书单对豆瓣评分的引用，链接指向豆瓣搜索页。<br><br>
访谈部分只收能在原文里定位到对象或节目的，泛泛说「某次采访」的不列。
</footer>
</div>
<script>
var q=document.getElementById('q'), rows=[].slice.call(document.querySelectorAll('tbody tr'));
var order=rows.map(function(r,i){{return {{r:r,i:i}};}});
q.addEventListener('input',function(){{
  var v=q.value.trim().toLowerCase();
  rows.forEach(function(r){{r.classList.toggle('hide', !!v && (r.dataset.s||'').indexOf(v)<0);}});
}});
document.querySelectorAll('.tabs button').forEach(function(btn){{
  btn.addEventListener('click',function(){{
    document.querySelectorAll('.tabs button').forEach(function(b){{b.classList.remove('on');}});
    btn.classList.add('on');
    var mode=btn.dataset.sort;
    document.querySelectorAll('table.books tbody').forEach(function(tb){{
      var trs=[].slice.call(tb.querySelectorAll('tr'));
      if(mode==='reset'){{
        var orig=trs.slice().sort(function(a,b){{return (+a.dataset.idx)-(+b.dataset.idx);}});
        orig.forEach(function(tr){{tb.appendChild(tr);}});
      }} else {{
        var key=mode==='rating'?2:4;
        var num=function(tr){{
          var t=((tr.children[key]||{{}}).textContent||'').replace(/,/g,'');
          return parseFloat(t)||0;
        }};
        var sorted=trs.slice().sort(function(a,b){{return num(b)-num(a);}});
        sorted.forEach(function(tr){{tb.appendChild(tr);}});
      }}
    }});
  }});
}});
document.querySelectorAll('tbody tr').forEach(function(tr,i){{tr.dataset.idx=i;}});
</script>
</body></html>"""

    (ROOT / "书单与访谈.html").write_text(doc, encoding="utf-8")

    md = ["# 孟岩提到的书与访谈", "",
          f"从 423 篇公众号文章（2016–2026）里核对出的书与访谈。豆瓣评分抓取于 2026-11-05，共 {len(books)} 本，其中 {len(rated)} 本有评分。", "",
          "## 书籍", "", md_books(books), "",
          "## 他自己主理 / 参与的播客与对谈", ""]
    for x in interviews["own"]:
        md.append(f"- **{x['name']}**：{x['detail']}（{x['source']}）")
    md += ["", "## 他引用、推荐过的访谈", ""]
    for x in interviews["quoted"]:
        md.append(f"- **{x['who']}**：{x['what']}（{x['source']}）")
    md += ["", "## 他提到的访谈 / 播客节目", ""]
    for x in interviews["programs"]:
        md.append(f"- **{x['name']}**：{x['note']}")
    md += ["", "---", "",
           "口径：书以原文书名号为线索逐个用豆瓣图书条目核对，剔除了媒体名、报告、法规、播客栏目和错配条目；同书不同写法与版本合并。少数条目原文书影兼指，仍按同名出版物收录。访谈只收能定位到对象或节目的。",
           "《点球成金》中文版 8.4 取自公开书单对豆瓣评分的引用（豆瓣搜索接口当时限流）。", ""]
    (ROOT / "书单与访谈.md").write_text("\n".join(md), encoding="utf-8")
    print(f"生成完成：{len(books)} 本书，{len(rated)} 本有评分，{len(often)} 本反复提及")
    print(f"HTML {len(doc):,} 字符")


if __name__ == "__main__":
    main()
