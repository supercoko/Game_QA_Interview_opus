"""命令行入口。

    python -m bug_insight analyze                    # 导出 CSV/JSONL + 生成报告和三个模块的清单
    python -m bug_insight search 手柄 --game 原神     # 检索历史缺陷
    python -m bug_insight checklist --module "系统/UI/养成"
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from .analyze import TRIGGER_NAME, enrich, export, fixes_only
from .parser import load_all, validate
from .report import build_checklist, build_report
from .taxonomy import MODULES, TRIGGER_BY_ID

ROOT = Path(__file__).resolve().parents[2]          # 数据所在目录（tool/ 的上一级）
DEFAULT_OUT = ROOT / "output"
MY_MODULES = ["战斗/角色/技能", "系统/UI/养成"]      # 「配置/资源/构建」是横向视角，见报告第 7 节


def _load(data_dir: Path):
    # parser负责读取原始公告，enrich负责把解析后的Bug补充为带分类标签的Record。
    sections, bugs = load_all(data_dir)
    return sections, bugs, enrich(bugs)


def cmd_analyze(args) -> int:
    sections, bugs, records = _load(args.data)
    # 校验是数据质量提示，不直接中断：即使条目数略有偏差，仍可生成可用报告。
    problems = validate(sections, bugs)
    export(records, args.out)
    (args.out / "分析报告.md").write_text(build_report(sections, records, problems), encoding="utf-8")
    ck_dir = args.out / "checklists"
    ck_dir.mkdir(exist_ok=True)
    for m in MY_MODULES + ["任务/剧情", "玩法/活动", "场景/关卡/大世界"]:
        name = m.replace("/", "_")
        (ck_dir / f"{name}.md").write_text(build_checklist(records, m), encoding="utf-8")
    print(f"解析 {len(sections)} 篇公告、{len(bugs)} 条记录，统计口径 {len(fixes_only(records))} 条")
    for p in problems:
        print("  校验提示：", p)
    print(f"已输出到 {args.out}")
    return 0


def cmd_search(args) -> int:
    _, _, records = _load(args.data)
    # 列表推导式中的条件全部为“且”关系；未提供参数时对应条件不生效。
    hits = [r for r in records
            if (not args.keyword or args.keyword in r.bug.full_text)
            and (not args.game or r.bug.game == args.game)
            and (not args.module or r.module == args.module)
            and (not args.trigger or args.trigger in r.triggers)
            and (not args.severity or r.severity == args.severity)]
    print(f"命中 {len(hits)} 条")
    for r in hits[: args.limit]:
        trig = ",".join(TRIGGER_NAME[t] for t in r.triggers) or "-"
        print(f"[{r.bug.game} {r.bug.version}][{r.severity}][{r.module}][{trig}] {r.bug.full_text}")
    return 0


def cmd_checklist(args) -> int:
    _, _, records = _load(args.data)
    print(build_checklist(records, args.module, top_n=args.top))
    return 0


def cmd_sample(args) -> int:
    """随机抽样，用于人工评估规则精度。"""
    _, _, records = _load(args.data)
    pool = fixes_only(records)
    rnd = random.Random(args.seed)
    for r in rnd.sample(pool, args.n):
        trig = ",".join(TRIGGER_NAME[t] for t in r.triggers) or "-"
        print(f"{r.bug.id}\t{r.severity}\t{r.module}\t{trig}\t{r.bug.text}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        # 强制 UTF-8 输出，避免中文在 Windows 终端中出现 GBK/UTF-8 编码混用。
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="bug_insight", description="上线游戏问题修复记录分析")
    p.add_argument("--data", type=Path, default=ROOT, help="索引 md 所在目录")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="导出数据并生成报告")
    a.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a.set_defaults(func=cmd_analyze)

    s = sub.add_parser("search", help="检索历史缺陷")
    s.add_argument("keyword", nargs="?", default="")
    s.add_argument("--game", choices=["原神", "崩铁", "绝区零", "终末地"])
    s.add_argument("--module", choices=MODULES)
    s.add_argument("--trigger", choices=list(TRIGGER_BY_ID), help="触发维度 id")
    s.add_argument("--severity", choices=["S1", "S2", "S3", "S4", "S?"])
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_search)

    c = sub.add_parser("checklist", help="按模块生成风险清单")
    c.add_argument("--module", required=True, choices=MODULES)
    c.add_argument("--top", type=int, default=8)
    c.set_defaults(func=cmd_checklist)

    m = sub.add_parser("sample", help="随机抽样用于人工评估")
    m.add_argument("-n", type=int, default=50)
    m.add_argument("--seed", type=int, default=7)
    m.set_defaults(func=cmd_sample)

    args = p.parse_args(argv)
    return args.func(args)
