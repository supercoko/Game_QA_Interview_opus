"""分类规则的回归用例。

人工抽检中发现的每一次误判，修好规则后都要在这里加一条用例，
防止之后改规则时把它又改坏。
"""

import unittest

from bug_insight.taxonomy import (SYMPTOMS, TRIGGERS, match_tags, normalize_module,
                                  severity)


def sev(text: str) -> str:
    return severity(match_tags(text, SYMPTOMS), text)


def trig(text: str) -> list[str]:
    return match_tags(text, TRIGGERS)


class SeverityTest(unittest.TestCase):
    def test_blocking(self):
        self.assertEqual(sev("修复了特定情况下，支线任务中部分敌人消失，导致无法正常推进任务的问题。"), "S1")
        self.assertEqual(sev("修复了有概率导致游戏进程异常的问题。"), "S1")

    def test_quit_game_is_not_blocking(self):
        # 「结束游戏进程」是触发条件，不是崩溃
        text = "修复了在护盾存在时结束游戏进程，固有天赋效果持续时间有概率出现异常的问题；"
        self.assertEqual(sev(text), "S2")

    def test_display_only_is_capped(self):
        text = "修复了部分角色激活终结技时，终结技按键部分UI及特效表现异常的问题。该问题不影响实际技能效果。"
        self.assertEqual(sev(text), "S3")

    def test_logic(self):
        self.assertEqual(sev("修复了特定情况下，部分角色的自动战斗目标选取逻辑异常的问题。"), "S2")
        self.assertEqual(sev("修复了角色施放元素爆发后一段时间内，重击不消耗体力的问题；"), "S2")

    def test_residue_model_is_visual(self):
        # 「仍会异常残留」的是模型，属于表现问题
        self.assertEqual(sev("修复了角色元素爆发结束后，潜水头盔模型仍会异常残留的问题；"), "S3")

    def test_voice_not_trigger_is_audio(self):
        self.assertEqual(sev("修复了角色「柯莱」的语音“阳光很好…”无法正常触发的问题；"), "S3")

    def test_text(self):
        self.assertEqual(sev("修正了部分文本中的错别字。"), "S4")

    def test_progress_not_counted_is_data(self):
        self.assertEqual(sev("修复了在参与玩法后，可能出现无法正确计入成长任务进度的问题。"), "S2")


class TriggerTest(unittest.TestCase):
    def test_npc_is_not_pc(self):
        self.assertNotIn("platform", trig("修复了部分NPC模型表现异常的问题。"))
        self.assertIn("platform", trig("修复了PC端部分界面显示异常的问题。"))

    def test_upper_limit_is_not_time_limited(self):
        text = "修复了背包中部分道具数量大于等于上限时，有概率无法进入部分关卡的问题。"
        self.assertNotIn("time", trig(text))
        self.assertIn("boundary", trig(text))

    def test_language_switch_hint_is_not_settings(self):
        text = "对13个语言的游戏内文本进行了修复。开拓者可通过“手机界面-设置-语言”切换游戏语言。"
        self.assertNotIn("settings", trig(text))
        self.assertIn("locale", trig(text))

    def test_real_settings(self):
        self.assertIn("settings", trig("修复了设置中【非当前窗口静音】功能有概率无法正常生效的问题。"))

    def test_quick_assist_is_skill_name(self):
        text = "修复了当队伍中任意角色[快速支援]命中敌人时无法正常回复[燎火]的问题。"
        self.assertNotIn("timing", trig(text))

    def test_regression(self):
        self.assertIn("regression", trig("修复了1.5版本更新后，击败敌方后有概率无法获取奖励的问题。"))
        self.assertIn("regression", trig("修复后光锥技能的实际效果与2.6版本更新前保持一致。"))

    def test_not_regression(self):
        text = "修复了 DX12 模式下首次进入游戏时出现卡顿的问题。为确保本次版本更新后的游戏体验，将重新触发一次着色器编译。"
        self.assertNotIn("regression", trig(text))

    def test_legacy_affected_data(self):
        text = "修复了任务道具异常消失的问题；修复前遇到该问题的旅行者，消失的道具会自动补发到背包内。"
        self.assertIn("legacy", trig(text))

    def test_input_hot_switch(self):
        self.assertIn("input", trig("修复了「赛跑挑战」玩法中，进行手柄热切换操作后，玩法倒计时异常不显示的问题。"))

    def test_combo(self):
        self.assertIn("combo", trig("修复了代理人「叶瞬光」装备音擎「加农转子」在战斗中伤害数字颜色错误的问题。"))


class ModuleTest(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(normalize_module("代理人", "x"), "战斗/角色/技能")
        self.assertEqual(normalize_module("其他", "修复了部分文本错误"), "文本/本地化")
        self.assertEqual(normalize_module("其他", "修复了部分场景音效缺失"), "音频/语音")


if __name__ == "__main__":
    unittest.main()
