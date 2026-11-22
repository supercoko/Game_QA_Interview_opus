"""Generate the interview preparation website from the selected Markdown files."""

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt


WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
SITE_TITLE = "游戏测试面试资料库"
GROUPS = ("Neon分析", "方案")
REPOSITORY = "https://github.com/supercoko/Game_QA_Interview_opus"
SUPPLEMENTAL_LINKS = {
    "../tool/README.md": f"{REPOSITORY}/blob/master/tool/README.md",
    "../output/分析报告.md": f"{REPOSITORY}/blob/master/output/{quote('分析报告.md')}",
    "../output/checklists/": f"{REPOSITORY}/tree/master/output/checklists",
}


@dataclass(frozen=True)
class Document:
    group: str
    source: str
    slug: str
    title: str
    summary: str


DOCUMENTS = (
    Document("Neon分析", "01_个人经历优化与补全建议.md", "experience", "个人经历优化与补全建议", "梳理业务测试经历、工具贡献与投递前需要核实的细节。"),
    Document("Neon分析", "02_业务端游戏测试岗位匹配分析.md", "role-fit", "业务端游戏测试岗位匹配分析", "对照岗位要求，分析测试方向、能力匹配和投递优先级。"),
    Document("Neon分析", "03_业务端游戏测试高频面试题库与参考答案.md", "question-bank", "高频面试题库与参考答案", "覆盖项目经历、场景设计、自动化、技术基础和反问环节。"),
    Document("Neon分析", "04_补充信息核查与简历使用指南.md", "resume-guide", "补充信息核查与简历使用指南", "核对量化表述与经历边界，按目标岗位选择表达重点。"),
    Document("方案", "00_总览.md", "overview", "能力提升方案总览", "从公开缺陷案例、个人项目经历到测试开发作品的准备路线。"),
    Document("方案", "01_上线Bug模式分析.md", "bug-patterns", "上线 Bug 模式分析", "回看 4,104 条公开修复记录，总结常见触发条件、风险与分析局限。"),
    Document("方案", "02_测试方法论与真实案例.md", "test-methods", "测试方法论与真实案例", "用十组公开案例拆解状态残留、时序、输入切换和断线重连。"),
    Document("方案", "03_三个模块的测试设计.md", "module-testing", "三个模块的测试设计", "分别设计战斗与技能、系统与 UI、配置与构建的覆盖策略。"),
    Document("方案", "04_自动化与工具方案_UE主线.md", "ue-automation", "自动化与工具方案（UE 主线）", "查看八项工具方案、示意代码和 UE 与 Unity 的实现对照。"),
    Document("方案", "05_面试话术与深挖问答.md", "interview-stories", "面试话术与深挖问答", "练习自我介绍、STAR 经历、岗位侧重点和高频追问。"),
    Document("方案", "06_行动计划.md", "action-plan", "三周行动计划", "安排数据与工具练习、经历整理、小作品及模拟面试。"),
    Document("方案", "07_优化后的提示词.md", "research-prompt", "优化后的提示词", "复用任务背景、资料范围、目标岗位和交付要求的模板。"),
    Document("方案", "08_个人经历深挖问答.md", "experience-followups", "个人经历深挖问答", "从主 QA 的视角演练多层追问，并检查面试前需核实的事实。"),
    Document("方案", "09_战斗与任务通用方法论.md", "combat-and-quests", "战斗与任务通用方法论", "结合多款游戏的案例，拆解战斗规则、任务状态与高风险场景。"),
)
BY_SOURCE = {(doc.group, doc.source): doc for doc in DOCUMENTS}


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "code", "li", "p", "td", "th", "pre", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append(" ")


def plain_text(html):
    parser = TextExtractor()
    parser.feed(html)
    return " ".join("".join(parser.parts).split())


def render_inline_html(tokens, index, options, env):
    raw = tokens[index].content
    return "<br>" if re.fullmatch(r"<br\s*/?>", raw, re.IGNORECASE) else escape(raw)


def render_html_block(tokens, index, options, env):
    return f"<pre>{escape(tokens[index].content)}</pre>\n"


MARKDOWN = MarkdownIt("commonmark").enable(["table", "strikethrough"])
MARKDOWN.renderer.rules.update(html_inline=render_inline_html, html_block=render_html_block)
validate_markdown_link = MARKDOWN.validateLink
# Parse local file references so the renderer can retain their labels without exposing paths.
MARKDOWN.validateLink = lambda url: url.lower().startswith("file:") or validate_markdown_link(url)


def published_link(href, group):
    url = urlsplit(href)
    if url.scheme in {"https", "http"}:
        return href
    if url.scheme or url.netloc:
        return None
    source = unquote(url.path)
    if source.startswith("../"):
        return SUPPLEMENTAL_LINKS.get(source)
    doc = BY_SOURCE.get((group, source.removeprefix("./")))
    if doc:
        return f"{doc.slug}.html"
    return None


def rewrite_links(tokens, group):
    opening = None
    for token in tokens:
        if token.type == "link_open":
            opening = token
            href = published_link(token.attrGet("href") or "", group)
            if href:
                token.attrSet("href", href)
            else:
                token.tag = "span"
                token.attrs.pop("href", None)
        elif token.type == "link_close" and opening is not None:
            token.tag = opening.tag
            opening = None


def render_document(doc):
    source = (ROOT / doc.group / doc.source).read_text(encoding="utf-8-sig")
    env = {}
    tokens = MARKDOWN.parse(source, env)
    toc = []
    title = doc.title
    if tokens and tokens[0].tag == "h1":
        title = plain_text(MARKDOWN.renderer.renderInline(tokens[1].children, MARKDOWN.options, env))
        tokens = tokens[3:]

    for index, token in enumerate(tokens):
        if token.children:
            rewrite_links(token.children, doc.group)
        if token.type == "heading_open" and token.tag in {"h2", "h3"}:
            section = f"section-{len(toc) + 1}"
            token.attrSet("id", section)
            children = tokens[index + 1].children
            label = plain_text(MARKDOWN.renderer.renderInline(children, MARKDOWN.options, env))
            toc.append((token.tag, section, label))

    body = MARKDOWN.renderer.render(tokens, MARKDOWN.options, env)
    body = body.replace("<table>", '<div class="table-scroll" tabindex="0" role="region" aria-label="可横向滚动的表格"><table>')
    return title, body.replace("</table>", "</table></div>"), toc


def page(title, description, body, *, article=False):
    base = "../" if article else "./"
    scripts = "" if article else (
        '<script defer src="./assets/search-index.js"></script>\n'
        '<script defer src="./assets/search.js"></script>'
    )
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(description)}">
  <meta name="theme-color" content="#f8f7f3">
  <title>{escape(title)}</title>
  <script src="{base}assets/theme.js"></script>
  <link rel="stylesheet" href="{base}assets/style.css">
  {scripts}
</head>
<body>
  <a class="skip-link" href="#content">跳到正文</a>
  <header class="site-header">
    <div class="shell header-inner">
      <a class="brand" href="{base}index.html"><span class="brand-mark" aria-hidden="true">QA</span><span>{SITE_TITLE}</span></a>
      <div class="header-controls">
        <nav class="top-nav" aria-label="资料分类">
          <a href="{base}index.html#neon">Neon分析</a>
          <a href="{base}index.html#plan">方案</a>
        </nav>
        <div class="theme-picker" hidden>
          <select id="site-theme" aria-label="站点主题">
            <option value="system">跟随系统</option>
            <option value="light">日间模式</option>
            <option value="dark">夜间模式</option>
          </select>
        </div>
      </div>
    </div>
  </header>
  {body}
  <footer class="site-footer"><div class="shell">{SITE_TITLE}<a href="#content">返回顶部</a></div></footer>
</body>
</html>
'''


def document_card(doc):
    return f'''<li><a class="document-card" href="./articles/{doc.slug}.html">
        <span class="card-title">{escape(doc.title)}</span>
        <span class="card-summary">{escape(doc.summary)}</span>
      </a></li>'''


def home_page():
    sections = []
    for group, anchor, description in zip(GROUPS, ("neon", "plan"), (
        "按岗位梳理个人经历，练习面试题和项目追问。",
        "从线上缺陷模式出发，练习测试设计、UE 自动化和面试表达。",
    ), strict=True):
        docs = [doc for doc in DOCUMENTS if doc.group == group]
        cards = "\n".join(map(document_card, docs))
        sections.append(f'''<section class="collection" id="{anchor}" aria-labelledby="{anchor}-title">
        <header class="collection-header"><div><h2 id="{anchor}-title">{group}</h2><p>{description}</p></div><span>{len(docs)} 篇</span></header>
        <ul class="document-grid">{cards}</ul>
      </section>''')
    collections = "\n".join(sections)
    description = "围绕游戏业务测试和测试开发展开的案例、测试设计、工具方案与面试问答。"
    return page(SITE_TITLE, description, f'''<main id="content" tabindex="-1" class="shell home">
    <section class="hero" aria-labelledby="site-title">
      <div class="hero-copy">
        <p class="eyebrow">游戏 QA · 面试准备</p>
        <h1 id="site-title">{SITE_TITLE}</h1>
        <p>从上线缺陷案例练测试设计，从个人经历练面试表达。整理业务测试与测试开发常用的方法、工具方案和追问。</p>
        <a class="primary-link" href="./articles/overview.html">阅读方案总览</a>
      </div>
      <div class="hero-guide">
        <h2>备考入口</h2>
        <a href="./articles/role-fit.html">对照目标岗位</a>
        <a href="./articles/test-methods.html">练习案例与测试设计</a>
        <a href="./articles/ue-automation.html">准备 UE 自动化方案</a>
      </div>
    </section>
    <section class="search-box" aria-labelledby="search-title" id="search" hidden>
      <label id="search-title" for="search-input">搜索资料</label>
      <input id="search-input" type="search" placeholder="输入关键词，例如 状态残留 或 Functional Test" autocomplete="off">
      <p id="search-status" role="status" hidden></p>
    </section>
    <section id="search-results" aria-label="搜索结果" hidden><ul class="document-grid"></ul></section>
    <div id="collections">{collections}</div>
  </main>''')


def article_page(doc, title, body, toc):
    group_anchor = "neon" if doc.group == "Neon分析" else "plan"
    outline = "\n".join(
        f'<li class="toc-{level}"><a href="#{anchor}">{escape(label)}</a></li>'
        for level, anchor, label in toc
    )
    group_docs = [item for item in DOCUMENTS if item.group == doc.group]
    index = group_docs.index(doc)
    neighbors = []
    for label, offset in (("上一篇", -1), ("下一篇", 1)):
        if 0 <= index + offset < len(group_docs):
            item = group_docs[index + offset]
            neighbors.append(f'<a href="{item.slug}.html"><span>{label}</span>{escape(item.title)}</a>')
    navigation = "".join(neighbors)
    return page(f"{doc.title} · {SITE_TITLE}", doc.summary, f'''<main id="content" tabindex="-1" class="shell article-layout">
    <header class="article-header">
      <nav class="breadcrumb" aria-label="当前位置"><a href="../index.html#{group_anchor}">{doc.group} 资料</a><span aria-hidden="true">/</span><span>正文</span></nav>
      <h1>{escape(title)}</h1>
      <p>{escape(doc.summary)}</p>
    </header>
    <nav class="toc" aria-label="本文目录"><h2>本文目录</h2><ul>{outline}</ul></nav>
    <div class="reading-column">
      <article class="prose">{body}</article>
      <nav class="article-pagination" aria-label="相邻文章">{navigation}</nav>
    </div>
  </main>''', article=True)


def build(destination):
    rendered = [(doc, *render_document(doc)) for doc in DOCUMENTS]
    (destination / "articles").mkdir(parents=True, exist_ok=True)
    (destination / "assets").mkdir(exist_ok=True)
    if destination != WEB:
        for asset in ("style.css", "search.js", "theme.js"):
            shutil.copyfile(WEB / "assets" / asset, destination / "assets" / asset)

    index = []
    for doc, title, body, toc in rendered:
        (destination / "articles" / f"{doc.slug}.html").write_text(
            article_page(doc, title, body, toc), encoding="utf-8",
        )
        index.append({"group": doc.group, "title": doc.title, "summary": doc.summary,
                      "url": f"./articles/{doc.slug}.html", "text": f"{title} {plain_text(body)}"})

    (destination / "index.html").write_text(home_page(), encoding="utf-8")
    data = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    (destination / "assets" / "search-index.js").write_text(f"window.qaSearchIndex = {data};\n", encoding="utf-8")
    print(f"Built {len(index)} documents in {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WEB, help="Static output directory")
    build(parser.parse_args().output.resolve())
