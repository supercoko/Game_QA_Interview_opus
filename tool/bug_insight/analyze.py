"""给解析出的缺陷打标签并做统计。"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .parser import Bug
from .taxonomy import (STATIC_CHECKABLE, SYMPTOMS, TRIGGERS, VAGUE, match_tags,
                       normalize_module, severity)


@dataclass
class Record:
    bug: Bug
    module: str
    triggers: list[str]
    symptoms: list[str]
    severity: str
    vague: bool
    static_checkable: bool
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        b = self.bug
        return {
            "id": b.id, "game": b.game, "version": b.version, "seq": b.seq,
            "official": b.official, "kind": b.kind, "category": b.category,
            "module": self.module, "severity": self.severity,
            "triggers": "|".join(self.triggers), "symptoms": "|".join(self.symptoms),
            "vague": self.vague, "static_checkable": self.static_checkable,
            "text": b.full_text, "source": f"{b.source_file}#L{b.line_no}", "url": b.url,
        }


def enrich(bugs: list[Bug]) -> list[Record]:
    out = []
    for b in bugs:
        # full_text 包含正文和附属说明，因此分类和检索不会漏掉调整前后信息。
        text = b.full_text
        trig = match_tags(text, TRIGGERS)
        sym = match_tags(text, SYMPTOMS)
        out.append(Record(
            bug=b,
            module=normalize_module(b.category, text),
            triggers=trig,
            symptoms=sym,
            severity=severity(sym, text),
            vague=bool(VAGUE.search(text)),
            static_checkable=bool(STATIC_CHECKABLE.search(text)),
        ))
    return out


def export(records: list[Record], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r.to_dict() for r in records]
    # utf-8-sig 会写入 BOM，Excel 在 Windows 上打开 CSV 时可正确识别中文。
    with (out_dir / "bugs.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with (out_dir / "bugs.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------

def fixes_only(records: list[Record]) -> list[Record]:
    """统计口径：官方公告中以「修复/修正」开头的条目。"""
    return [r for r in records if r.bug.kind == "修复" and r.bug.official]


def count_by(records, key) -> Counter:
    # key返回标量时逐条计数；返回列表时更新每个标签的计数，适合多标签维度。
    c = Counter()
    for r in records:
        v = key(r)
        if isinstance(v, (list, tuple, set)):
            c.update(v)
        else:
            c[v] += 1
    return c


def crosstab(records, row_key, col_key) -> dict[str, Counter]:
    # 交叉表允许一条记录同时属于多个维度和现象，统计时按笛卡尔组合累加。
    t: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        rows = row_key(r)
        cols = col_key(r)
        rows = rows if isinstance(rows, list) else [rows]
        cols = cols if isinstance(cols, list) else [cols]
        for a in rows:
            for b in cols:
                t[a][b] += 1
    return t


def specificity(r: Record) -> float:
    """挑代表案例时用：条件越具体、描述越完整越好。"""
    text = r.bug.text
    score = min(len(text), 120) / 120
    score += 0.3 * len(r.triggers)
    if r.vague:
        score -= 0.4
    if text.startswith("修复了部分") and len(text) < 30:
        score -= 1
    if r.severity in ("S1", "S2"):
        score += 0.3
    return score


def pick_examples(records: list[Record], n: int = 5, diverse_games: bool = True) -> list[Record]:
    ranked = sorted(records, key=specificity, reverse=True)
    if not diverse_games:
        return ranked[:n]
    picked, seen = [], Counter()
    # 轮流从不同游戏取，避免样本全被条目最多的原神占满
    for limit in (1, 2, 3, n):
        for r in ranked:
            if len(picked) >= n:
                break
            if r in picked or seen[r.bug.game] >= limit:
                continue
            picked.append(r)
            seen[r.bug.game] += 1
        if len(picked) >= n:
            break
    return picked


def trend_by_version(records: list[Record]) -> dict[str, list[tuple[int, str, int]]]:
    """每个游戏按时间顺序的 (seq, version, 条目数)。"""
    out: dict[str, dict[int, tuple[str, int]]] = defaultdict(dict)
    for r in records:
        seq, ver = r.bug.seq, r.bug.version
        prev = out[r.bug.game].get(seq, (ver, 0))
        out[r.bug.game][seq] = (ver, prev[1] + 1)
    return {g: [(s, v, n) for s, (v, n) in sorted(d.items())] for g, d in out.items()}


TRIGGER_NAME = {t.id: t.name for t in TRIGGERS}
SYMPTOM_NAME = {t.id: t.name for t in SYMPTOMS}
