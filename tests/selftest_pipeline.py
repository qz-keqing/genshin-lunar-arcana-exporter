# -*- coding: utf-8 -*-
"""离线自测：用伪造的 role_combat 返回数据跑通导出全流程（核心逻辑不联网也能跑）。

验证点：
  1. 接口返回解析 -> tarot_card_state 提取（含本期 stat 统计）
  2. JSON 落盘
  3. HTML 渲染（未解锁灰显、×N 重复角标）

运行： python tests/selftest_pipeline.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import yysp_core as core  # noqa: E402

FAKE_CARDS = [{
    "icon": "",
    "name": "测试圣牌%02d" % i,
    "is_unlock": i <= 12,
    "unlock_num": (2 if i in (3, 7) else 1) if i <= 12 else 0,
} for i in range(1, 23)]

FAKE_PAYLOAD = {
    "retcode": 0, "message": "OK",
    "data": {
        "is_unlock": True,
        "tarot_card_state": {"total_num": 22, "curr_num": 12, "list": FAKE_CARDS},
        "data": [{
            "stat": {"difficulty_id": 5, "tarot_finished_cnt": 2, "max_round_id": 10},
            "schedule": {"schedule_id": 1, "schedule_type": 1},
        }],
    },
}

core.fetch_role_combat = lambda *a, **k: FAKE_PAYLOAD

out = os.path.join(HERE, "out")
res = core.export("ltuid_v2=0;ltoken_v2=0", "888888888", "os_asia", out,
                  log=lambda m: print("  " + m), with_icons=False)

assert res["unlocked"] == 12 and res["total"] == 22, "计数不正确"
data = json.load(open(res["json_path"], encoding="utf-8"))
assert data["tarot_card_state"]["curr_num"] == 12
assert len(data["tarot_card_state"]["list"]) == 22
assert data["stat"]["tarot_finished_cnt"] == 2 and data["stat"]["difficulty_id"] == 5, "stat 未落盘"

page = open(res["html_path"], encoding="utf-8").read()
assert "「月谕圣牌」收藏 12 / 22" in page, "HTML 标题/计数不正确"
assert page.count('class="card locked"') == 10, "未解锁卡片数量不正确"
assert page.count('class="cnt"') == 2, "重复持有角标数量不正确"

print("\n[PASS] 核心流程自测通过：解析 / JSON / HTML 均正确")
print("       预览： %s" % res["html_path"])
