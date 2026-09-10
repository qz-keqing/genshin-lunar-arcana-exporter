# -*- coding: utf-8 -*-
"""月谕圣牌导出器 —— 图形界面（tkinter）

启动后：① 米游社 App 扫码登录（国服）或粘贴 Cookie ② 填/选 UID ③ 一键导出。
数据来自原神官方战绩接口 role_combat 的 tarot_card_state 字段。

无界面用法（同一个 exe 也支持）：
  月谕圣牌导出器.exe --selftest 日志文件      # 自检
  月谕圣牌导出器.exe --uid UID --cookie "..." --server cn_gf01 --out out
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import threading
import time
import traceback
import webbrowser

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import yysp_core as core
import yysp_login as login

APP_TITLE = "月谕圣牌导出器 v%s" % core.VERSION
CN_RECORD_PAGE = "https://webstatic.mihoyo.com/app/community-game-records/index.html#/ys/role-combat"
MYS_PAGE = "https://www.miyoushe.com/ys/"


def open_path(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except Exception:
        webbrowser.open("file://" + path.replace("\\", "/"))


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.cookie = ""
        self.qr_ticket = None
        self.qr_device = None
        self.qr_stop = threading.Event()
        self.result = None
        self.busy = False

        root.title(APP_TITLE)
        root.geometry("760x720")
        root.minsize(700, 620)

        self._build_widgets()
        self._restore_session()

    # ------------------------------------------------------------ UI
    def _build_widgets(self) -> None:
        pad = dict(padx=10, pady=6)

        head = ttk.Frame(self.root)
        head.pack(fill="x", **pad)
        ttk.Label(head, text="「月谕圣牌」一键导出",
                  font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w")
        ttk.Label(head, text="数据来源：原神官方战绩接口 role_combat › tarot_card_state"
                             "（幻想真境剧诗·月谕圣牌收藏）",
                  foreground="#666").pack(anchor="w")

        nb = ttk.Notebook(self.root)
        nb.pack(fill="x", **pad)

        # --- Tab 1: 扫码登录
        tab_qr = ttk.Frame(nb)
        nb.add(tab_qr, text="① 扫码登录（国服）")
        row = ttk.Frame(tab_qr)
        row.pack(fill="x", padx=10, pady=8)
        self.btn_qr = ttk.Button(row, text="获取二维码", command=self.on_get_qr)
        self.btn_qr.pack(side="left")
        ttk.Button(row, text="在浏览器打开登录页", command=self.on_open_qr_page).pack(side="left", padx=8)
        self.qr_label = ttk.Label(tab_qr, text="（点「获取二维码」后用米游社 App 扫码）",
                                  anchor="center", width=40)
        self.qr_label.pack(pady=6)
        self.qr_status = ttk.Label(tab_qr, text="未登录", foreground="#a33")
        self.qr_status.pack(pady=(0, 8))

        # --- Tab 2: Cookie
        tab_ck = ttk.Frame(nb)
        nb.add(tab_ck, text="② 粘贴 Cookie（国际服/备用）")
        ttk.Label(tab_ck, text="浏览器登录米游社或 HoYoLAB → F12 → Network → 任意请求 → "
                               "复制 Request Headers 里的 Cookie（含 ltuid_v2 / ltoken_v2）",
                  wraplength=700, foreground="#666").pack(anchor="w", padx=10, pady=(8, 2))
        self.txt_cookie = tk.Text(tab_ck, height=4, wrap="char")
        self.txt_cookie.pack(fill="x", padx=10)
        row2 = ttk.Frame(tab_ck)
        row2.pack(fill="x", padx=10, pady=8)
        ttk.Button(row2, text="使用这个 Cookie", command=self.on_use_cookie).pack(side="left")
        ttk.Button(row2, text="打开米游社", command=lambda: webbrowser.open(MYS_PAGE)).pack(side="left", padx=8)
        ttk.Button(row2, text="打开官方战绩页", command=lambda: webbrowser.open(CN_RECORD_PAGE)).pack(side="left")

        # --- 账号与输出
        body = ttk.LabelFrame(self.root, text="账号与输出")
        body.pack(fill="x", **pad)
        r1 = ttk.Frame(body)
        r1.pack(fill="x", padx=10, pady=6)
        ttk.Label(r1, text="UID：").pack(side="left")
        self.ent_uid = ttk.Entry(r1, width=16)
        self.ent_uid.pack(side="left")
        ttk.Label(r1, text="  服务器：").pack(side="left")
        self.cmb_server = ttk.Combobox(r1, width=16, state="readonly",
                                       values=[core.server_name(s) for s in core.SERVER_NAMES])
        self.cmb_server.current(0)
        self.cmb_server.pack(side="left")
        ttk.Button(r1, text="列出我的角色", command=self.on_list_roles).pack(side="left", padx=8)

        r2 = ttk.Frame(body)
        r2.pack(fill="x", padx=10, pady=6)
        ttk.Label(r2, text="输出目录：").pack(side="left")
        self.ent_out = ttk.Entry(r2)
        self.ent_out.insert(0, os.path.join(os.path.expanduser("~"), "Documents", "月谕圣牌导出"))
        self.ent_out.pack(side="left", fill="x", expand=True)
        ttk.Button(r2, text="选择…", command=self.on_choose_dir).pack(side="left", padx=8)

        r3 = ttk.Frame(body)
        r3.pack(fill="x", padx=10, pady=6)
        self.var_remember = tk.BooleanVar(value=True)
        ttk.Checkbutton(r3, text="记住登录态（保存在本机 %s）" % login.SESSION_FILE,
                        variable=self.var_remember).pack(side="left")
        ttk.Button(r3, text="清除登录态", command=self.on_clear_session).pack(side="right")

        # --- 执行
        run = ttk.Frame(self.root)
        run.pack(fill="x", **pad)
        self.btn_export = ttk.Button(run, text="一键导出月谕圣牌", command=self.on_export)
        self.btn_export.pack(side="left")
        self.lbl_summary = ttk.Label(run, text="未导出", font=("Microsoft YaHei UI", 10, "bold"))
        self.lbl_summary.pack(side="left", padx=12)

        cols = ("idx", "name", "state", "cnt")
        self.tree = ttk.Treeview(self.root, columns=cols, show="headings", height=12)
        for c, t, w in (("idx", "序号", 60), ("name", "圣牌名称", 300),
                        ("state", "状态", 120), ("cnt", "持有张数", 100)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=6)

        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Button(bottom, text="打开 HTML 收藏页", command=self.on_open_html).pack(side="left")
        ttk.Button(bottom, text="打开输出目录", command=self.on_open_dir).pack(side="left", padx=8)

        self.status = tk.StringVar(value="就绪。建议先扫码登录，或粘贴 Cookie。")
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w").pack(
            fill="x", side="bottom")

    # ------------------------------------------------------------ 小工具
    def log(self, msg: str) -> None:
        """线程安全地把进度写到状态栏。"""
        try:
            self.root.after(0, lambda m=str(msg): self.status.set(m))
        except Exception:
            pass

    def in_thread(self, fn) -> None:
        threading.Thread(target=fn, daemon=True).start()

    def say(self, title: str, msg: str, warn: bool = False) -> None:
        (messagebox.showwarning if warn else messagebox.showinfo)(title, msg)

    def server_code(self) -> str:
        idx = self.cmb_server.current()
        return list(core.SERVER_NAMES)[idx] if idx >= 0 else "cn_gf01"

    def set_server_code(self, code: str) -> None:
        if code in core.SERVER_NAMES:
            self.cmb_server.current(list(core.SERVER_NAMES).index(code))

    # ------------------------------------------------------------ 登录
    def _restore_session(self) -> None:
        s = login.load_session()
        if not s.get("cookie"):
            return
        self.cookie = s["cookie"]
        if s.get("uid"):
            self.ent_uid.delete(0, "end")
            self.ent_uid.insert(0, s["uid"])
        if s.get("server"):
            self.set_server_code(s["server"])
        self.qr_status.config(text="已恢复上次登录态（%s）" % s.get("saved_at", ""), foreground="#276")
        self.log("已恢复本机保存的登录态；如需切换账号请点「清除登录态」。")

    def _after_login(self, cookie: str, source: str) -> None:
        self.cookie = cookie
        self.qr_status.config(text="登录成功（%s）" % source, foreground="#276")
        self.log("登录成功（%s）。" % source)
        if self.var_remember.get():
            try:
                login.save_session(cookie, self.ent_uid.get().strip(), self.server_code())
                self.log("登录态已保存到 %s" % login.SESSION_FILE)
            except OSError as exc:
                self.log("保存登录态失败：%s" % exc)
        self.on_list_roles(silent=True)

    def on_use_cookie(self) -> None:
        cookie = self.txt_cookie.get("1.0", "end").strip().replace("\n", " ")
        if not cookie:
            self.say("提示", "请先粘贴 Cookie", warn=True)
            return
        self._after_login(cookie, "Cookie")

    def on_get_qr(self) -> None:
        self.on_open_qr_page()
        self.qr_stop.set()
        self.qr_stop = threading.Event()
        self.btn_qr.config(state="disabled")
        self.qr_status.config(text="正在获取二维码…", foreground="#666")

        def work():
            try:
                info = login.create_qr()
            except Exception as exc:
                self.root.after(0, lambda: self._qr_failed(str(exc)))
                return
            self.root.after(0, lambda: self._show_qr(info))

        self.in_thread(work)

    def on_open_qr_page(self) -> None:
        if getattr(self, "qr_url", None):
            webbrowser.open(self.qr_url)

    def _qr_failed(self, msg: str) -> None:
        self.btn_qr.config(state="normal")
        self.qr_status.config(text="获取二维码失败", foreground="#a33")
        self.say("获取二维码失败", msg, warn=True)

    def _show_qr(self, info: dict) -> None:
        self.qr_ticket = info["ticket"]
        self.qr_device = info["device_id"]
        self.qr_url = info["url"]
        try:
            import segno
            buf = io.BytesIO()
            segno.make(info["url"], error="l").save(buf, kind="png", scale=5, border=2)
            png = buf.getvalue()
            tmp = os.path.join(os.environ.get("TEMP") or ".", "yysp_qr.png")
            with open(tmp, "wb") as f:
                f.write(png)
            img = tk.PhotoImage(file=tmp)
            self.qr_label.config(image=img, text="")
            self.qr_label.image = img  # 防 GC
        except Exception as exc:
            self.qr_label.config(text="二维码渲染失败，请点「在浏览器打开登录页」\n(%s)" % exc)
        self.qr_status.config(text="请用米游社 App 扫码并确认…", foreground="#666")
        self.btn_qr.config(state="normal")
        self.in_thread(lambda: self._poll_qr(self.qr_ticket, self.qr_device, self.qr_stop))

    def _poll_qr(self, ticket: str, device: str, stop: threading.Event) -> None:
        deadline = time.time() + 180
        while not stop.is_set() and time.time() < deadline:
            time.sleep(2)
            try:
                res = login.query_qr(ticket, device)
            except login.LoginError as exc:
                self.root.after(0, lambda m=str(exc): self.qr_status.config(text=m, foreground="#a33"))
                return
            status, cookies = res["status"], res["cookies"]
            if status == "Scanned":
                self.root.after(0, lambda: self.qr_status.config(text="已扫描，请在手机上确认…", foreground="#666"))
            if status == "Confirmed":
                if not any(k.startswith(("ltuid", "account_id", "cookie_token", "stoken")) for k in cookies):
                    self.root.after(0, lambda: self.qr_status.config(
                        text="已确认，但未取到登录 Cookie，请改用 Cookie 粘贴方式", foreground="#a33"))
                    return
                cookie = core.cookies_to_header(cookies)
                self.root.after(0, lambda c=cookie: self._after_login(c, "扫码"))
                return
        self.root.after(0, lambda: self.qr_status.config(text="二维码已超时，请重新获取", foreground="#a33"))

    def on_clear_session(self) -> None:
        login.clear_session()
        self.cookie = ""
        self.qr_status.config(text="已清除登录态", foreground="#a33")
        self.log("已清除本机保存的登录态。")

    # ------------------------------------------------------------ 角色
    def on_list_roles(self, silent: bool = False) -> None:
        if not self.cookie:
            if not silent:
                self.say("提示", "请先扫码登录或粘贴 Cookie", warn=True)
            return

        def work():
            try:
                region = "os" if self.server_code().startswith("os") else "cn"
                roles = core.list_roles(self.cookie, region)
            except Exception as exc:
                if not silent:
                    self.root.after(0, lambda m=str(exc): self.say(
                        "列出角色失败", m + "\n\n（这不影响导出，直接手动填写 UID 即可）", warn=True))
                return
            if not roles:
                if not silent:
                    self.root.after(0, lambda: self.say("提示", "该账号下没有查询到原神角色", warn=True))
                return
            def apply():
                first = roles[0]
                self.ent_uid.delete(0, "end")
                self.ent_uid.insert(0, first["game_uid"])
                self.set_server_code(first["region"] or core.guess_server(first["game_uid"]))
                self.log("已自动填入角色：%s（UID %s / %s）"
                         % (first["nickname"], first["game_uid"], core.server_name(self.server_code())))
                if len(roles) > 1:
                    self.say("账号下共有 %d 个原神角色" % len(roles),
                             "\n".join("%s  %s  %s" % (r["nickname"], r["game_uid"], r["region"])
                                       for r in roles) + "\n\n已自动填入第一个，可在 UID 处改成其它角色。")
            self.root.after(0, apply)

        self.in_thread(work)

    def on_choose_dir(self) -> None:
        d = filedialog.askdirectory()
        if d:
            self.ent_out.delete(0, "end")
            self.ent_out.insert(0, d)

    # ------------------------------------------------------------ 导出
    def on_export(self) -> None:
        if self.busy:
            return
        if not self.cookie:
            self.say("提示", "请先扫码登录或粘贴 Cookie", warn=True)
            return
        uid = self.ent_uid.get().strip()
        if not uid.isdigit():
            self.say("提示", "请填写游戏 UID（纯数字，可在游戏内头像处查看）", warn=True)
            return
        server = self.server_code()
        out_dir = self.ent_out.get().strip() or "."
        self.busy = True
        self.btn_export.config(state="disabled")
        self.tree.delete(*self.tree.get_children())
        self.lbl_summary.config(text="导出中…")

        def work():
            try:
                res = core.export(self.cookie, uid, server, out_dir, log=self.log)
            except Exception as exc:
                msg = str(exc) if isinstance(exc, core.YyspError) else traceback.format_exc(limit=2)
                self.root.after(0, lambda m=msg: self._export_failed(m))
                return
            self.root.after(0, lambda r=res: self._export_done(r))

        self.in_thread(work)

    def _export_failed(self, msg: str) -> None:
        self.busy = False
        self.btn_export.config(state="normal")
        self.lbl_summary.config(text="导出失败")
        self.log("导出失败。")
        if "登录态" in msg:
            msg += ("\n\n建议：回到「① 扫码登录」重新获取二维码，或重新复制一份 Cookie"
                    "（需含 ltuid_v2 / ltoken_v2），并确认游戏内已开启战绩展示。")
        self.say("导出失败", msg, warn=True)

    def _export_done(self, res: dict) -> None:
        self.busy = False
        self.btn_export.config(state="normal")
        self.result = res
        for i, c in enumerate(res["cards"], 1):
            self.tree.insert("", "end", values=(
                i, c.get("name") or "?",
                "已获得" if c.get("is_unlock") else "未解锁",
                c.get("unlock_num") or 0))
        self.lbl_summary.config(text="已收集 %d / %d" % (res["unlocked"], res["total"]))
        self.log("导出完成：%s" % res["html_path"])
        self.say("导出完成",
                 "「月谕圣牌」%d / %d\n\nHTML：%s\nJSON：%s"
                 % (res["unlocked"], res["total"], res["html_path"], res["json_path"]))

    def on_open_html(self) -> None:
        if self.result:
            open_path(self.result["html_path"])

    def on_open_dir(self) -> None:
        d = self.ent_out.get().strip() or "."
        if os.path.isdir(d):
            open_path(d)


# ---------------------------------------------------------------- 无界面模式
def headless_selftest(logfile: str) -> int:
    lines: list[str] = []

    def w(msg: str) -> None:
        lines.append(str(msg))

    ok = True
    w("月谕圣牌导出器 自检 v%s" % core.VERSION)
    w("Python %s / frozen=%s" % (sys.version.split()[0], getattr(sys, "frozen", False)))

    # 1) 离线渲染管线
    try:
        fake_cards = [{"icon": "" if i > 12 else
                       "https://webstatic.mihoyo.com/app/community-game-records/images/paimeng@2x.dbab088b.png"
                       "?card=%02d" % i,
                       "name": "自检圣牌%02d" % i, "is_unlock": i <= 12,
                       "unlock_num": 2 if i in (3, 7) else (1 if i <= 12 else 0)}
                      for i in range(1, 23)]
        fake = {"retcode": 0, "message": "OK", "data": {
            "tarot_card_state": {"total_num": 22, "curr_num": 12, "list": fake_cards},
            "data": [{"stat": {"difficulty_id": 5, "tarot_finished_cnt": 2, "max_round_id": 10},
                      "schedule": {"schedule_id": 1}}]}}
        orig = core.fetch_role_combat
        core.fetch_role_combat = lambda *a, **k: fake
        out = os.path.join(os.environ.get("TEMP") or ".", "yysp_selftest_out")
        res = core.export("ltuid_v2=0;ltoken_v2=0", "888888888", "os_asia", out, log=w)
        core.fetch_role_combat = orig
        page = open(res["html_path"], encoding="utf-8").read()
        checks = [
            ("JSON 生成", os.path.exists(res["json_path"])),
            ("HTML 生成", os.path.exists(res["html_path"])),
            ("计数 12/22", res["unlocked"] == 12 and res["total"] == 22),
            ("未解锁 10 张", page.count('class="card locked"') == 10),
            ("重复角标 2 个", page.count('class="cnt"') == 2),
            ("图标已本地化", page.count("icons-888888888/") >= 12),
        ]
        for name, good in checks:
            w("  [%s] %s" % ("PASS" if good else "FAIL", name))
            ok = ok and good
    except Exception:
        ok = False
        w("  [FAIL] 渲染管线异常：\n" + traceback.format_exc())

    # 2) 官方战绩接口连通性（无 Cookie，应返回“请登录”）
    try:
        core.fetch_role_combat("ltuid_v2=0;ltoken_v2=0", "100000000", "cn_gf01")
        w("  [FAIL] 无 Cookie 竟然查询成功，预期应报登录态无效")
        ok = False
    except core.YyspError as exc:
        good = "10001" in str(exc) or "登录" in str(exc)
        w("  [%s] 战绩接口连通（%s）" % ("PASS" if good else "FAIL", exc))
        ok = ok and good
    except Exception as exc:
        w("  [FAIL] 战绩接口异常：%s" % exc)
        ok = False

    # 3) 扫码登录通道（生成二维码）
    try:
        info = login.create_qr()
        good = bool(info.get("ticket")) and bool(info.get("url"))
        w("  [%s] 扫码登录通道可用（ticket=%s…）" % ("PASS" if good else "FAIL", info.get("ticket", "")[:8]))
        ok = ok and good
    except Exception as exc:
        w("  [FAIL] 扫码登录通道异常：%s" % exc)
        ok = False

    w("")
    w("自检结果：%s" % ("全部通过" if ok else "存在失败项"))
    text = "\n".join(lines)
    try:
        with open(logfile, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass
    if sys.stdout:
        try:
            print(text)
        except Exception:
            pass
    return 0 if ok else 1


def headless_export(uid: str, cookie: str, server: str, out: str, logfile: str | None) -> int:
    lines: list[str] = []

    def w(msg: str) -> None:
        lines.append(str(msg))

    code = 0
    try:
        res = core.export(cookie, uid, server or core.guess_server(uid), out, log=w)
        w("导出完成：%s" % res["html_path"])
    except Exception as exc:
        code = 1
        if isinstance(exc, core.YyspError):
            w("导出失败：%s" % exc)
            w("提示：请重新扫码登录，或重新复制 Cookie（需含 ltuid_v2 / ltoken_v2），"
              "并确认游戏内【设置 → 其他 → 展示游戏内信息】为开启状态。")
        else:
            w("导出失败：\n" + traceback.format_exc())
    text = "\n".join(lines)
    if logfile:
        with open(logfile, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    if sys.stdout:
        print(text)
    return code


def headless_guitest(logfile: str) -> int:
    """在打包后的 exe 里验证图形界面自身能否构建（Tk / segno / 表格渲染）。"""
    lines: list[str] = []
    ok = True

    def w(msg: str) -> None:
        lines.append(str(msg))

    try:
        root = tk.Tk()
        root.withdraw()
        app = App(root)
        app.say = lambda *a, **k: None
        app.log = lambda *a, **k: None
        root.update()

        import segno
        buf = io.BytesIO()
        segno.make("https://user.mihoyo.com/login-platform/mobile.html?tk=guitest",
                   error="l").save(buf, kind="png", scale=4, border=2)
        tmp = os.path.join(os.environ.get("TEMP") or ".", "yysp_guitest_qr.png")
        with open(tmp, "wb") as f:
            f.write(buf.getvalue())
        img = tk.PhotoImage(file=tmp)
        checks = [("Tk 界面构建", True), ("segno 生成二维码 PNG", img.width() > 50)]
        root.withdraw()

        fake = {"uid": "888888888", "server": "cn_gf01", "total": 22, "unlocked": 12,
                "json_path": "", "html_path": "",
                "cards": [{"name": "自检%02d" % i, "is_unlock": i <= 12,
                           "unlock_num": 1 if i <= 12 else 0} for i in range(1, 23)]}
        app._export_done(fake)
        root.update()
        rows = app.tree.get_children()
        checks.append(("表格 22 行", len(rows) == 22))
        checks.append(("汇总标签", app.lbl_summary.cget("text") == "已收集 12 / 22"))
        root.destroy()
        for name, good in checks:
            w("  [%s] %s" % ("PASS" if good else "FAIL", name))
            ok = ok and good
    except Exception:
        ok = False
        w("  [FAIL] GUI 自检异常：\n" + traceback.format_exc())

    w("")
    w("GUI 自检结果：%s" % ("全部通过" if ok else "存在失败项"))
    text = "\n".join(lines)
    try:
        with open(logfile, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass
    if sys.stdout:
        try:
            print(text)
        except Exception:
            pass
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--selftest", metavar="LOGFILE", help="自检并把结果写入日志文件")
    ap.add_argument("--guitest", metavar="LOGFILE", help="界面自检（构建 Tk 界面并渲染二维码）")
    ap.add_argument("--uid")
    ap.add_argument("--cookie")
    ap.add_argument("--server", default="")
    ap.add_argument("--out", default="out")
    ap.add_argument("--log", dest="logfile")
    args = ap.parse_args()

    if args.selftest:
        return headless_selftest(args.selftest)
    if args.guitest:
        return headless_guitest(args.guitest)
    if args.uid and args.cookie:
        return headless_export(args.uid, args.cookie, args.server, args.out, args.logfile)

    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except Exception:
        pass
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
