#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""月谕圣牌 一键导出（命令行版，核心逻辑见 yysp_core.py）

  python export-lunar-arcana.py --cookie "ltuid_v2=...;ltoken_v2=..." --uid 123456789
  set YYSP_COOKIE=ltuid_v2=...;ltoken_v2=...     &  python export-lunar-arcana.py --uid 123456789

输出：out/lunar-arcana-<uid>.json、out/lunar-arcana-<uid>.html、out/icons-<uid>/
数据来源：原神官方战绩接口 role_combat › tarot_card_state
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import yysp_core as core

LOGIN_HINT = """
[!] {msg}
    请登录米游社(https://www.miyoushe.com/) 或 HoYoLAB(https://www.hoyolab.com/)，
    从浏览器 F12 → Network → 任意 api-takumi-record / sg-public-api 请求的
    Request Headers 复制完整 Cookie（至少 ltuid_v2 / ltoken_v2），
    并确认游戏内【设置 → 其他 → 展示游戏内信息/战绩】为开启状态。
    或者直接用图形界面版： python yysp_gui.py  （支持米游社 App 扫码登录）
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="导出原神「月谕圣牌」收藏（官方战绩接口）")
    ap.add_argument("--cookie", default=os.environ.get("YYSP_COOKIE", ""),
                    help="米游社/HoYoLAB 的 Cookie（也可用环境变量 YYSP_COOKIE）")
    ap.add_argument("--uid", required=True, help="游戏 UID，例如 123456789")
    ap.add_argument("--server", default="", help="cn_gf01/cn_qd01/os_usa/os_euro/os_asia/os_cht，默认按 UID 首位推断")
    ap.add_argument("--out", default="out", help="输出目录，默认 out")
    ap.add_argument("--no-icons", action="store_true", help="不下载圣牌图标")
    ap.add_argument("--raw", action="store_true", help="打印接口原始 JSON")
    ap.add_argument("--timeout", type=int, default=30, help="请求超时秒数")
    args = ap.parse_args()

    if not args.cookie:
        print(LOGIN_HINT.format(msg="缺少 Cookie"))
        return 2

    server = args.server or core.guess_server(args.uid)
    try:
        if args.raw:
            payload = core.fetch_role_combat(args.cookie, args.uid, server, timeout=args.timeout)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        res = core.export(args.cookie, args.uid, server, args.out,
                          log=lambda m: print("[*] " + m, flush=True),
                          with_icons=not args.no_icons)
    except core.YyspError as exc:
        print(LOGIN_HINT.format(msg=exc))
        return 2

    print("\n===== 「月谕圣牌」收藏 %d / %d =====" % (res["unlocked"], res["total"]))
    for i, c in enumerate(res["cards"], 1):
        if c.get("is_unlock"):
            cnt = c.get("unlock_num") or 0
            print("  #%02d  %-12s 已获得%s" % (i, c.get("name") or "?", " ×%d" % cnt if cnt > 1 else ""))
        else:
            print("  #%02d  %-12s 未解锁" % (i, c.get("name") or "?"))
    print("\n[+] JSON -> %s\n[+] HTML -> %s" % (res["json_path"], res["html_path"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
