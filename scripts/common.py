# -*- coding: utf-8 -*-
"""微信公众号文章：HTML 提取与逐字转 Markdown 的公共函数。

设计原则：只做结构还原，不改写、不摘要、不删段。
图片按 [图片] 占位，原始 URL 单独存进元数据，便于以后补图。
"""
import html as _html
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

CST = timezone(timedelta(hours=8))

BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "ul", "ol", "blockquote", "pre", "table", "tr", "hr", "figure",
}
CONTAINER_TAGS = {"section", "div"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "mpvoice", "mpvideo", "video", "iframe", "audio"}
HEADING_LEVEL = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
BAD_PAGE_MARKERS = ("环境异常", "去验证", "该内容已被发布者删除", "此内容因违规无法查看", "参数错误", "系统繁忙")


def extract_js_content(raw):
    """配对计数取出 <div id="js_content"> 的内部 HTML。"""
    m = re.search(r'<div[^>]*\bid="js_content"[^>]*>', raw, re.I)
    if not m:
        return None
    start = m.end()
    depth = 1
    pos = start
    tag_re = re.compile(r'</?div\b[^>]*>', re.I)
    end = None
    while depth:
        t = tag_re.search(raw, pos)
        if not t:
            return None
        if t.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                end = t.start()
                break
        else:
            depth += 1
        pos = t.end()
    return raw[start:end] if end else None


def _clean_text(s):
    s = s.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return s


def _img_url(tag):
    for key in ("data-src", "data-original", "src"):
        v = tag.get(key)
        if v and v.startswith("http"):
            return _html.unescape(v)
    return None


class Converter:
    def __init__(self):
        self.images = []
        self.media = []

    def _children(self, node):
        return [c for c in node.children if not isinstance(c, Comment)]

    def render(self, node, depth=0, list_kind=None, list_no=0):
        """返回 (文本, 是否为块) —— 块级结果自带前后空行。"""
        if isinstance(node, NavigableString):
            return _clean_text(str(node)), False

        if not isinstance(node, Tag):
            return "", False

        name = node.name.lower()
        style = (node.get("style") or "").lower()
        if "display:none" in style.replace(" ", "") or "display: none" in style:
            return "", False

        if name in SKIP_TAGS:
            label = {"mpvoice": "[音频]", "audio": "[音频]", "video": "[视频]",
                     "mpvideo": "[视频]", "iframe": "[视频]"}.get(name)
            if label:
                self.media.append(label)
                return "\n\n" + label + "\n\n", True
            return "", False

        if name == "img":
            url = _img_url(node)
            if url:
                self.images.append(url)
            return "\n\n[图片]\n\n", True

        if name == "br":
            return "\n", False
        if name == "hr":
            return "\n\n---\n\n", True

        if name == "table":
            return self._table(node), True

        if name in ("ul", "ol"):
            parts = []
            n = 0
            for c in self._children(node):
                if isinstance(c, Tag) and c.name.lower() == "li":
                    n += 1
                    inner, _ = self.render(c, depth + 1, name, n)
                    parts.append(inner)
            return "\n\n" + "".join(parts).strip() + "\n\n", True

        if name == "li":
            inner = self._render_children(node, depth + 1)
            inner = inner.strip()
            bullet = "- " if list_kind != "ol" else f"{list_no}. "
            pad = "  " * max(0, depth - 1)
            lines = inner.split("\n")
            out = pad + bullet + lines[0].strip()
            for ln in lines[1:]:
                if ln.strip():
                    out += "\n" + pad + "  " + ln.strip()
            return out + "\n", True

        if name in HEADING_LEVEL:
            inner = self._render_children(node, depth).strip()
            inner = inner.replace("\n", " ")
            if inner:
                # 主标题已占用 #，正文小标题整体降一级
                level = min(6, HEADING_LEVEL[name] + 1)
                return "\n\n" + "#" * level + " " + inner + "\n\n", True
            return "", False

        if name == "blockquote":
            inner = self._render_children(node, depth).strip()
            lines = [("> " + ln.strip()) if ln.strip() else ">" for ln in inner.split("\n")]
            return "\n\n" + "\n".join(lines) + "\n\n", True

        if name == "pre":
            inner = _clean_text(node.get_text())
            return "\n\n```\n" + inner.strip("\n") + "\n```\n\n", True

        if name == "a":
            inner = self._render_children(node, depth).strip().replace("\n", " ")
            href = _html.unescape(node.get("href") or "")
            if inner and href.startswith("http"):
                return "[" + inner + "](" + href + ")", False
            return inner, False

        if name in ("strong", "b"):
            inner = self._render_children(node, depth).strip()
            return ("**" + inner + "**") if inner else "", False
        if name in ("em", "i"):
            inner = self._render_children(node, depth).strip()
            return ("*" + inner + "*") if inner else "", False

        if name in CONTAINER_TAGS:
            inner = self._render_children(node, depth)
            if not inner.strip():
                return "", False
            # 纯容器（内部只有别的块）不额外加空行，避免段落被拆碎
            kids = [c for c in self._children(node) if isinstance(c, Tag)]
            has_direct_text = any(
                isinstance(c, NavigableString) and str(c).strip() for c in self._children(node)
            )
            only_blocks = kids and all(
                c.name.lower() in BLOCK_TAGS or c.name.lower() in CONTAINER_TAGS for c in kids
            )
            if only_blocks and not has_direct_text:
                return inner, True
            return "\n\n" + inner.strip() + "\n\n", True

        if name in ("p", "tr", "figure"):
            inner = self._render_children(node, depth)
            if not inner.strip():
                return "", False
            return "\n\n" + inner.strip() + "\n\n", True

        return self._render_children(node, depth), False

    def _table(self, node):
        rows = []
        for tr in node.find_all("tr"):
            cells = []
            for td in tr.find_all(["td", "th"], recursive=False):
                txt = self._render_children(td, 0).strip().replace("\n", " ")
                txt = txt.replace("|", "\\|")
                cells.append(txt)
            if cells:
                rows.append("| " + " | ".join(cells) + " |")
        if not rows:
            return ""
        width = rows[0].count("|") - 1
        sep = "| " + " | ".join(["---"] * max(1, width)) + " |"
        return "\n\n" + rows[0] + "\n" + sep + "\n" + "\n".join(rows[1:]) + "\n\n"

    def _render_children(self, node, depth):
        parts = []
        for c in self._children(node):
            txt, _ = self.render(c, depth)
            if txt:
                parts.append(txt)
        return "".join(parts)

    def convert(self, fragment):
        soup = BeautifulSoup(fragment, "lxml")
        body = soup.body or soup
        text = self._render_children(body, 0)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 微信编辑器常把相邻加粗拆成 **A****B**，合并成 **AB**
        while "****" in text:
            text = text.replace("****", "")
        text = re.sub(r"^\s+|\s+$", "", text)
        return text


def _meta(raw, pattern, default=""):
    m = re.search(pattern, raw, re.I | re.S)
    return _html.unescape(m.group(1)).strip() if m else default


def parse_article(raw, url=""):
    """解析一篇文章的原始 HTML，返回结构化数据；失败时 status=error。"""
    out = {"url": url, "raw_size": len(raw)}
    for marker in BAD_PAGE_MARKERS:
        if marker in raw[:200000]:
            out.update(status="error", error=marker)
            return out

    fragment = extract_js_content(raw)
    if not fragment or len(fragment) < 100:
        out.update(status="error", error="no_js_content")
        return out

    title = _meta(raw, r'<meta\s+property="og:title"\s+content="([^"]*)"')
    if not title:
        title = _meta(raw, r"var\s+msg_title\s*=\s*'([^']*)'")
    if not title:
        title = _meta(raw, r"<h1[^>]*class=\"[^\"]*rich_media_title[^\"]*\"[^>]*>(.*?)</h1>")
    title = re.sub(r"<[^>]+>", "", title).strip()

    ts = _meta(raw, r'var\s+ct\s*=\s*"(\d{9,11})"')
    date = ""
    if ts:
        date = datetime.fromtimestamp(int(ts), CST).strftime("%Y-%m-%d %H:%M")

    author = _meta(raw, r'var\s+nickname\s*=\s*"([^"]*)"')
    if not author:
        author = _meta(raw, r'<meta\s+name="author"\s+content="([^"]*)"')

    conv = Converter()
    body = conv.convert(fragment)

    out.update(
        status="ok",
        title=title,
        author=author or "孟岩",
        date=date,
        body=body,
        images=conv.images,
        media=conv.media,
        char_count=len(re.sub(r"\s", "", body)),
    )
    return out


def slugify(title, limit=40):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "", title).strip()
    s = re.sub(r"\s+", "-", s)
    return s[:limit].strip("-") or "untitled"
