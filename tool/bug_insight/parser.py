"""解析「问题修复分类索引」Markdown 文件。

输入文件结构（四个游戏一致）：

    # 标题
    ## 版本索引 / 公告索引           <- 表格，忽略
    ## 按版本和类别整理
    ### 7.2｜[公告标题](url)          <- 版本段落开始
    来源：...；提取 39 条。           <- 声明条目数，用于数据校验
    **任务**                          <- 公告原文分类
    - 修复了……                        <- 一条缺陷记录
      - 调整前：……                    <- 附属说明，挂到上一条记录
    *以下为公告所列简体中文文本修复补充。*
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# 文件名前缀 -> 游戏简称
GAME_BY_PREFIX = {
    "原神": "原神",
    "崩铁": "崩铁",
    "绝区零": "绝区零",
    "终末地": "终末地",
}

RE_SECTION = re.compile(r"^###\s+(?P<key>[^｜|]+)[｜|]\s*\[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)")
RE_CATEGORY = re.compile(r"^\*\*(?P<cat>[^*]+)\*\*\s*$")
RE_BULLET = re.compile(r"^- (?P<text>.+)$")
RE_SUBBULLET = re.compile(r"^\s{2,}- (?P<text>.+)$")
RE_DECLARED = re.compile(r"(?:提取|收录)\s*(?P<n>\d+)\s*条")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_SUPPLEMENT = re.compile(r"^\*以下为.*补充.*\*$")


@dataclass
class Section:
    game: str
    key: str            # 版本号；终末地为公告日期
    title: str
    url: str
    line_no: int
    declared: int | None = None
    official: bool = True
    seq: int = 0        # 时间顺序，0 = 最早


@dataclass
class Bug:
    id: str
    game: str
    version: str
    section_title: str
    url: str
    category: str       # 公告原文分类
    text: str
    details: list[str] = field(default_factory=list)
    line_no: int = 0
    source_file: str = ""
    official: bool = True
    seq: int = 0
    kind: str = "修复"   # 修复 / 优化 / 其他

    @property
    def full_text(self) -> str:
        return self.text + ("；" + "；".join(self.details) if self.details else "")


def game_of(path: Path) -> str:
    for prefix, game in GAME_BY_PREFIX.items():
        if path.name.startswith(prefix):
            return game
    return path.stem


def classify_kind(text: str) -> str:
    if text.startswith(("修复", "修正")):
        return "修复"
    if text.startswith(("优化", "调整", "对")):
        return "优化"
    return "其他"


def parse_file(path: Path) -> tuple[list[Section], list[Bug]]:
    game = game_of(path)
    sections: list[Section] = []
    bugs: list[Bug] = []
    current: Section | None = None
    category = "未分类"

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.rstrip()

        m = RE_SECTION.match(line)
        if m:
            current = Section(game=game, key=m["key"].strip(), title=m["title"].strip(),
                              url=m["url"].strip(), line_no=line_no)
            sections.append(current)
            category = "未分类"
            continue
        if current is None:
            continue  # 段落开始之前的说明和索引表

        if line.startswith("来源：") or line.startswith("提取"):
            d = RE_DECLARED.search(line)
            if d:
                current.declared = int(d["n"])
            if "玩家整理" in line:
                current.official = False
            continue

        m = RE_CATEGORY.match(line)
        if m:
            category = m["cat"].strip()
            continue
        if RE_SUPPLEMENT.match(line):
            category = "简中文本补充"
            continue

        m = RE_SUBBULLET.match(raw)
        if m and bugs and bugs[-1].line_no >= current.line_no:
            bugs[-1].details.append(m["text"].strip())
            continue

        m = RE_BULLET.match(line)
        if m:
            text = m["text"].strip()
            bugs.append(Bug(
                id="",  # 稍后统一编号
                game=game, version=current.key, section_title=current.title, url=current.url,
                category=category, text=text, line_no=line_no, source_file=path.name,
                official=current.official, kind=classify_kind(text),
            ))

    # 文件按时间倒序排列，换算成正序编号便于做趋势
    n = len(sections)
    for i, s in enumerate(sections):
        s.seq = n - 1 - i
    seq_of = {(s.game, s.key): (s.seq, s.official) for s in sections}
    for i, b in enumerate(bugs):
        b.seq, b.official = seq_of[(b.game, b.version)]
        b.id = f"{game}-{b.version}-{i:04d}"
    return sections, bugs


def load_all(data_dir: Path) -> tuple[list[Section], list[Bug]]:
    files = sorted(data_dir.glob("*问题修复分类索引.md"))
    if not files:
        raise FileNotFoundError(f"{data_dir} 下没有找到 *问题修复分类索引.md")
    all_sections: list[Section] = []
    all_bugs: list[Bug] = []
    for f in files:
        s, b = parse_file(f)
        all_sections += s
        all_bugs += b
    return all_sections, all_bugs


def validate(sections: list[Section], bugs: list[Bug]) -> list[str]:
    """把解析出的条目数和公告声明条目数对比，返回不一致的说明。"""
    counts: dict[tuple[str, str], int] = {}
    for b in bugs:
        counts[(b.game, b.version)] = counts.get((b.game, b.version), 0) + 1
    problems = []
    for s in sections:
        got = counts.get((s.game, s.key), 0)
        if s.declared is not None and got != s.declared:
            problems.append(f"{s.game} {s.key}: 声明 {s.declared} 条，解析到 {got} 条")
        if s.declared is None:
            problems.append(f"{s.game} {s.key}: 未找到声明条目数，解析到 {got} 条")
    return problems


def is_date_key(key: str) -> bool:
    return bool(RE_DATE.match(key))
