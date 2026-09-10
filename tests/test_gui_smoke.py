# -*- coding: utf-8 -*-
"""GUI 冒烟测试：不联网、不弹窗，只验证界面能构建、表格/汇总/二维码渲染正确。

运行： python tests/test_gui_smoke.py   （需要 pip install segno）
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import tkinter as tk  # noqa: E402

import yysp_core  # noqa: E402
import yysp_gui  # noqa: E402

root = tk.Tk()
root.withdraw()  # 不真的显示窗口
app = yysp_gui.App(root)
root.update()
app.say = lambda *a, **k: None          # 冒烟测试里屏蔽模态弹窗，避免等待点击
app.log = lambda *a, **k: None
root.update()

# 1) 服务器下拉框
app.cmb_server.current(2)
assert app.server_code() == list(yysp_core.SERVER_NAMES)[2]
assert app.ent_out.get().strip() != ""

# 2) 二维码渲染（segno -> PNG -> tk.PhotoImage）
import segno  # noqa: E402

buf = io.BytesIO()
segno.make("https://user.mihoyo.com/login-platform/mobile.html?tk=test", error="l").save(
    buf, kind="png", scale=4, border=2)
tmp = os.path.join(os.environ.get("TEMP") or ".", "yysp_smoke_qr.png")
with open(tmp, "wb") as f:
    f.write(buf.getvalue())
img = tk.PhotoImage(file=tmp)
assert img.width() > 50, "二维码渲染尺寸异常"

# 3) 导出结果 -> 表格渲染
fake = {
    "uid": "888888888", "server": "cn_gf01", "total": 22, "unlocked": 12,
    "json_path": "", "html_path": "",
    "cards": [{"name": "圣牌%02d" % i, "is_unlock": i <= 12, "unlock_num": 1 if i <= 12 else 0}
              for i in range(1, 23)],
}
app._export_done(fake)
root.update()
rows = app.tree.get_children()
assert len(rows) == 22, "表格行数不正确：%d" % len(rows)
assert app.tree.item(rows[0], "values")[2] == "已获得"
assert app.tree.item(rows[21], "values")[2] == "未解锁"
assert app.lbl_summary.cget("text") == "已收集 12 / 22"

# 4) 二维码展示路径（_show_qr 内部会起轮询线程，测试里先置停止标志）
app.qr_stop.set()
app._show_qr({"ticket": "smoke", "device_id": "smoke",
              "url": "https://user.mihoyo.com/login-platform/mobile.html?tk=smoke#/login/qr"})
root.update()
assert getattr(app.qr_label, "image", None) is not None, "二维码未显示到界面上"
assert "扫码" in app.qr_status.cget("text"), "扫码状态提示不正确"
app.qr_stop.set()

root.destroy()
print("[PASS] GUI 冒烟测试通过：界面构建 / 二维码渲染 / 22 行表格 / 汇总标签 均正常")
