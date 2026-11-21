"""生成 Markdown 报告与模块风险清单。"""

from __future__ import annotations

from collections import Counter

from .analyze import (SYMPTOM_NAME, TRIGGER_NAME, Record, count_by, crosstab, fixes_only,
                      pick_examples, trend_by_version)
from .parser import Section
from .taxonomy import MODULES, SEVERITY_LABELS, TRIGGER_BY_ID, TRIGGERS

GAMES = ["原神", "崩铁", "绝区零", "终末地"]


def pct(a: int, b: int) -> str:
    # 分母为零时不做除法，以“-”表示该维度没有可统计数据。
    return f"{(100 * a / b):.1f}%" if b else "-"


def table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |",
             "| " + " | ".join("---" if i == 0 else "---:" for i in range(len(header))) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def cite(r: Record, prefix: str = "../") -> str:
    """prefix：从输出文件到数据目录的相对路径（报告在 output/，清单在 output/checklists/）。"""
    b = r.bug
    return f"{b.text}（{b.game} {b.version}，[{b.source_file}#L{b.line_no}]({prefix}{b.source_file}#L{b.line_no})）"


def build_report(sections: list[Section], records: list[Record], validation: list[str]) -> str:
    fx = fixes_only(records)
    total = len(fx)
    by_game = count_by(fx, lambda r: r.bug.game)
    out: list[str] = []
    w = out.append

    w("# 上线游戏「问题修复」数据分析报告（自动生成）\n")
    w("> 由 `python -m bug_insight analyze` 生成。分类基于关键词规则（多标签），是风险分布的近似画像，"
      "不是精确统计；规则精度见 方案/01 文档的人工抽检结果。\n")

    # ---- 数据概览
    w("## 1. 数据概览\n")
    sec_by_game = Counter(s.game for s in sections)
    rows = []
    for g in GAMES:
        n = by_game[g]
        rows.append([g, sec_by_game[g], count_by(records, lambda r: r.bug.game)[g], n,
                     f"{n / max(sec_by_game[g], 1):.1f}"])
    rows.append(["合计", len(sections), len(records), total, f"{total / max(len(sections), 1):.1f}"])
    w(table(["游戏", "公告数", "全部条目", "统计口径条目*", "平均每版本"], rows))
    w("\n\\* 统计口径：官方公告中以「修复/修正」开头的条目；排除「优化/调整」类条目与崩铁 1.1/1.2 玩家整理帖。\n")
    w("数据校验（解析条目数 vs 公告声明条目数）：" +
      ("全部一致。" if not validation else "")+ "\n")
    for v in validation:
        w(f"- {v}")
    w("")

    # ---- 严重度
    w("## 2. 严重度分布（按现象推断）\n")
    sev = {g: count_by([r for r in fx if r.bug.game == g], lambda r: r.severity) for g in GAMES}
    sev_all = count_by(fx, lambda r: r.severity)
    rows = []
    for s, label in SEVERITY_LABELS.items():
        rows.append([label] + [f"{sev[g][s]} ({pct(sev[g][s], by_game[g])})" for g in GAMES]
                    + [f"{sev_all[s]} ({pct(sev_all[s], total)})"])
    w(table(["严重度"] + GAMES + ["合计"], rows))
    w("")

    # ---- 模块
    w("## 3. 模块分布（公告原分类归一化）\n")
    mod = {g: count_by([r for r in fx if r.bug.game == g], lambda r: r.module) for g in GAMES}
    mod_all = count_by(fx, lambda r: r.module)
    rows = []
    for m in MODULES:
        if not mod_all[m]:
            continue
        rows.append([m] + [f"{mod[g][m]} ({pct(mod[g][m], by_game[g])})" for g in GAMES]
                    + [f"{mod_all[m]} ({pct(mod_all[m], total)})"])
    w(table(["模块"] + GAMES + ["合计"], rows))
    w("")

    # ---- 触发维度
    w("## 4. 触发维度：bug 在什么条件下才出现\n")
    w("一条缺陷可能命中多个维度。「有明确触发维度」= 至少命中一个维度。\n")
    trig = {g: count_by([r for r in fx if r.bug.game == g], lambda r: r.triggers) for g in GAMES}
    trig_all = count_by(fx, lambda r: r.triggers)
    rows = []
    for t in sorted(TRIGGERS, key=lambda t: -trig_all[t.id]):
        rows.append([t.name] + [f"{trig[g][t.id]} ({pct(trig[g][t.id], by_game[g])})" for g in GAMES]
                    + [f"{trig_all[t.id]} ({pct(trig_all[t.id], total)})"])
    has_trig = sum(1 for r in fx if r.triggers)
    vague = sum(1 for r in fx if r.vague)
    vague_only = sum(1 for r in fx if r.vague and not r.triggers)
    w(table(["触发维度"] + GAMES + ["合计"], rows))
    w(f"\n- 有明确触发维度：{has_trig} 条（{pct(has_trig, total)}）")
    w(f"- 含「特定情况下」等模糊条件：{vague} 条（{pct(vague, total)}），其中没有任何其他维度线索的 {vague_only} 条")
    w("")

    # ---- 维度 × 严重度
    w("## 5. 触发维度 × 严重度\n")
    w("看哪些维度更容易出高严重度问题（行内占比）。\n")
    ct = crosstab(fx, lambda r: r.triggers, lambda r: r.severity)
    rows = []
    for t in sorted(TRIGGERS, key=lambda t: -(ct[t.id]["S1"] + ct[t.id]["S2"]) / max(sum(ct[t.id].values()), 1)):
        n = sum(ct[t.id].values())
        if n < 10:
            continue
        rows.append([t.name, n, pct(ct[t.id]["S1"], n), pct(ct[t.id]["S2"], n),
                     pct(ct[t.id]["S1"] + ct[t.id]["S2"], n)])
    w(table(["触发维度", "条目", "S1占比", "S2占比", "S1+S2"], rows))
    w("")

    # ---- 模块 × 维度
    w("## 6. 模块 × 触发维度（每个模块的 Top 5 维度）\n")
    ct = crosstab(fx, lambda r: r.module, lambda r: r.triggers)
    rows = []
    for m in MODULES:
        n = mod_all[m]
        if n < 15:
            continue
        top = ct[m].most_common(5)
        rows.append([m, n, "、".join(f"{TRIGGER_NAME[k]} {pct(v, n)}" for k, v in top)])
    w(table(["模块", "条目", "Top 维度（占模块条目比例）"], rows))
    w("")

    # ---- 静态可检出
    w("## 7. 「配置/资源/构建」视角：静态检查有机会拦截的问题\n")
    st = [r for r in fx if r.static_checkable]
    st_game = count_by(st, lambda r: r.bug.game)
    w("命中文本错误、图标/描述与实际不一致、资源缺失、语音有误等关键词的条目——"
      "这类问题理论上不需要跑游戏，靠配置/资源静态检查就有机会发现。\n")
    w(table(["游戏", "条目", "占比"],
            [[g, st_game[g], pct(st_game[g], by_game[g])] for g in GAMES] + [["合计", len(st), pct(len(st), total)]]))
    w("\n代表案例：\n")
    for r in pick_examples(st, 6):
        w(f"- {cite(r)}")
    w("")

    # ---- 回归
    w("## 8. 版本回归与存量数据\n")
    reg = [r for r in fx if "regression" in r.triggers]
    leg = [r for r in fx if "legacy" in r.triggers]
    w(f"- 明确写出「版本更新后 / 与过往版本表现一致」等回归字样：{len(reg)} 条（{pct(len(reg), total)}）")
    w(f"- 涉及「已拥有 / 已完成 / 已领取」等存量数据状态：{len(leg)} 条（{pct(len(leg), total)}）\n")
    for r in pick_examples(reg, 5):
        w(f"- {cite(r)}")
    w("")

    # ---- 趋势
    w("## 9. 每个版本的修复条目数（按时间顺序）\n")
    w("条目数受公告写法影响很大（例如早期版本写得更细），只能粗看，不能直接当成质量趋势。\n")
    for g, series in trend_by_version(fx).items():
        w(f"- **{g}**：" + "，".join(f"{v}:{n}" for _, v, n in series))
    w("")

    # ---- 维度案例
    w("## 10. 各触发维度代表案例\n")
    for t in TRIGGERS:
        rs = [r for r in fx if t.id in r.triggers]
        if not rs:
            continue
        w(f"### {t.name}（{len(rs)} 条）\n")
        w(f"- 测试设计方法：{t.technique}")
        w(f"- 更适合的发现手段：{t.detection}")
        w(f"- 设计测试点时问自己：{t.hint}\n")
        for r in pick_examples(rs, 5):
            w(f"  - [{r.severity}] {cite(r)}")
        w("")
    return "\n".join(out)


def build_checklist(records: list[Record], module: str, top_n: int = 8, per_tag: int = 4) -> str:
    fx = [r for r in fixes_only(records) if r.module == module]
    if not fx:
        raise ValueError(f"模块「{module}」没有数据，可选：{', '.join(MODULES)}")
    n = len(fx)
    trig = count_by(fx, lambda r: r.triggers)
    sev = count_by(fx, lambda r: r.severity)
    sym = count_by(fx, lambda r: r.symptoms)
    out = [f"# 风险清单：{module}\n",
           f"> 由 `python -m bug_insight checklist --module \"{module}\"` 基于 {n} 条上线修复记录生成。"
           "用法：写测试用例/评审需求前过一遍，每个维度至少回答一次「这个需求在这个维度下会怎样」。\n",
           "## 概况\n",
           "- 严重度：" + "，".join(f"{SEVERITY_LABELS[k]} {pct(v, n)}" for k, v in sorted(sev.items())),
           "- 主要现象：" + "，".join(f"{SYMPTOM_NAME[k]} {pct(v, n)}" for k, v in sym.most_common(5)),
           ""]
    out.append("## 按历史频率排序的检查维度\n")
    for i, (tid, c) in enumerate(trig.most_common(top_n), start=1):
        t = TRIGGER_BY_ID[tid]
        out.append(f"### {i}. {t.name}（占本模块 {pct(c, n)}）\n")
        out.append(f"- [ ] {t.hint}")
        out.append(f"- 方法：{t.technique}；手段：{t.detection}")
        out.append("- 历史案例：")
        for r in pick_examples([r for r in fx if tid in r.triggers], per_tag):
            out.append(f"  - [{r.severity}] {cite(r, prefix='../../')}")
        out.append("")
    return "\n".join(out)
