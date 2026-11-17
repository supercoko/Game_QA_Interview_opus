import tempfile
import unittest
from pathlib import Path

from bug_insight.parser import load_all, parse_file, validate

SAMPLE = """# 原神版本更新公告：问题修复分类索引

## 版本索引

| 版本 | 米游社公告 | 提取条目数 |
| --- | --- | ---: |
| 7.2 | [x](https://a) | 3 |

## 按版本和公告分类整理

### 7.2｜[「新版本」7.2版本](https://example.com/72)

提取 3 条公告项目。

**任务**

- 修复了特定情况下，任务无法推进的问题。

**角色**

- 修复了角色技能描述有误的问题。
  - 调整前：造成伤害
  - 调整后：造成物理伤害
- 优化了部分界面表现。

### 7.1｜[「旧版本」7.1版本](https://example.com/71)

提取 2 条公告项目。

**其他**

- 修复了部分文本错误。
"""


class ParserTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "原神测试问题修复分类索引.md"
        self.path.write_text(SAMPLE, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_sections_and_bugs(self):
        sections, bugs = parse_file(self.path)
        self.assertEqual([s.key for s in sections], ["7.2", "7.1"])
        self.assertEqual(len(bugs), 4)
        self.assertEqual(bugs[0].category, "任务")
        self.assertEqual(bugs[0].game, "原神")

    def test_subbullets_attach_to_previous(self):
        _, bugs = parse_file(self.path)
        self.assertEqual(bugs[1].details, ["调整前：造成伤害", "调整后：造成物理伤害"])
        self.assertIn("调整后", bugs[1].full_text)

    def test_kind(self):
        _, bugs = parse_file(self.path)
        self.assertEqual([b.kind for b in bugs], ["修复", "修复", "优化", "修复"])

    def test_seq_is_chronological(self):
        sections, bugs = parse_file(self.path)
        seq = {s.key: s.seq for s in sections}
        self.assertLess(seq["7.1"], seq["7.2"])
        self.assertEqual(bugs[-1].seq, seq["7.1"])

    def test_validate_reports_mismatch(self):
        sections, bugs = parse_file(self.path)
        problems = validate(sections, bugs)
        # 7.2 声明 3 条且解析到 3 条；7.1 声明 2 条只解析到 1 条
        self.assertEqual(len(problems), 1)
        self.assertIn("7.1", problems[0])


class RealDataTest(unittest.TestCase):
    """对真实数据做一次冒烟：解析条目数必须与公告声明一致（原神 2.0 原帖为图片，已知缺失）。"""

    DATA = Path(__file__).resolve().parents[2]

    @unittest.skipUnless(any(DATA.glob("*问题修复分类索引.md")), "没有真实数据文件")
    def test_declared_counts_match(self):
        sections, bugs = load_all(self.DATA)
        problems = [p for p in validate(sections, bugs) if not p.startswith("原神 2.0")]
        self.assertEqual(problems, [])
        self.assertGreater(len(bugs), 4000)


if __name__ == "__main__":
    unittest.main()
