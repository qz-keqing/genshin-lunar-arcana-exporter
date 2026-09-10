# -*- coding: utf-8 -*-
"""月谕圣牌导出 —— 核心逻辑（GUI 与命令行共用）

数据来源（原神官方战绩接口 role_combat）：
  国服   https://api-takumi-record.mihoyo.com/game_record/app/genshin/api/role_combat
  国际服 https://sg-public-api.hoyolab.com/event/game_record/genshin/api/role_combat
返回中 data.tarot_card_state 即「月谕圣牌」收藏（22 张，含 is_unlock / unlock_num）。
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.0"

# ---------------------------------------------------------------- 接口常量
CN_RECORD_URL = "https://api-takumi-record.mihoyo.com/game_record/app/genshin/api/role_combat"
OS_RECORD_URL = "https://sg-public-api.hoyolab.com/event/game_record/genshin/api/role_combat"
CN_ROLES_URL = "https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie?game_biz=hk4e_cn"
OS_ROLES_URL = "https://api-account-os.hoyolab.com/binding/api/getUserGameRolesByCookieToken?game_biz=hk4e_global"

CN_REFERER = "https://webstatic.mihoyo.com/app/community-game-records/"
OS_REFERER = "https://webstatic-sea.hoyolab.com/app/community-game-records-sea/"

CN_SALT_4X = "xV8v4Qu54lUKrEYFZkJhB8cuOh9Asafs"  # 米游社 web(client_type=5) DS2 用的 4X salt

SERVER_NAMES = {
    "cn_gf01": "国服·天空岛",
    "cn_qd01": "国服·世界树",
    "os_usa": "国际服·美服",
    "os_euro": "国际服·欧服",
    "os_asia": "国际服·亚服",
    "os_cht": "国际服·港澳台",
}

_SERVER_BY_FIRST_DIGIT = {
    "1": "cn_gf01", "2": "cn_gf01", "3": "cn_gf01", "4": "cn_gf01",
    "5": "cn_qd01",
    "6": "os_usa", "7": "os_euro", "8": "os_asia", "9": "os_cht",
}

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 常见返回码 -> 人话
RETCODE_HINTS = {
    10001: "登录态无效或已过期（Cookie 不对 / 已过期）",
    -100: "登录态无效或已过期（Cookie 不对 / 已过期）",
    -10001: "登录态无效或已过期（Cookie 不对 / 已过期）",
    -101: "账号或角色数据不可用（该 UID 可能不存在，或战绩未开启）",
    -110: "请求过于频繁，请稍后再试",
    -111: "该账号未绑定此角色",
    -114: "请先登录",
    10102: "该账号未绑定此角色，请确认 UID 与服务器",
}


class YyspError(Exception):
    """带用户可读信息的错误。"""


def server_name(server: str) -> str:
    return SERVER_NAMES.get(server, server)


def is_os_server(server: str) -> bool:
    return server.startswith("os")


def guess_server(uid: str) -> str:
    uid = (uid or "").strip()
    return _SERVER_BY_FIRST_DIGIT.get(uid[:1], "cn_gf01")


def retcode_hint(payload: dict) -> str:
    code = payload.get("retcode")
    msg = payload.get("message") or ""
    hint = RETCODE_HINTS.get(code)
    return "[%s] %s" % (code, hint or msg or "未知错误")


# ---------------------------------------------------------------- HTTP
def _ds2(query: str = "", body: str = "") -> str:
    """米游社 web 接口的 DS2 签名（部分老接口仍需要）。"""
    t = int(time.time())
    r = random.randint(100001, 200000)
    main = "salt=%s&t=%s&r=%s&b=%s&q=%s" % (CN_SALT_4X, t, r, body, query)
    digest = hashlib.md5(main.encode("utf-8")).hexdigest()
    return "%s,%s,%s" % (t, r, digest)


def record_headers(cookie: str, server: str) -> dict:
    is_os = is_os_server(server)
    return {
        "Cookie": cookie,
        "User-Agent": _UA + " miHoYoBBS/2.3.0",
        "Referer": OS_REFERER if is_os else CN_REFERER,
        "Origin": "https://webstatic-sea.hoyolab.com" if is_os else "https://webstatic.mihoyo.com",
        "x-rpc-app_version": "2.3.0",
        "x-rpc-client_type": "5",
        "x-rpc-language": "zh-cn",
        "Accept": "application/json, text/plain, */*",
    }


def _request(url: str, headers: dict, method: str = "GET", payload: dict | None = None,
             timeout: int = 30) -> tuple[dict, dict]:
    """返回 (json, cookies)。"""
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=ssl.create_default_context()) as resp:
            raw = resp.read().decode("utf-8", "replace")
            cookies = {}
            for c in (resp.headers.get_all("Set-Cookie") or []):
                part = c.split(";")[0]
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookies[k.strip()] = v.strip()
    except urllib.error.HTTPError as exc:
        raise YyspError("网络错误：HTTP %s %s" % (exc.code, exc.reason)) from exc
    except urllib.error.URLError as exc:
        raise YyspError("网络不通：%s（检查代理 / 防火墙）" % exc) from exc
    try:
        return json.loads(raw), cookies
    except json.JSONDecodeError as exc:
        raise YyspError("服务端返回的不是 JSON：%s" % raw[:200]) from exc


def cookies_to_header(cookies: dict) -> str:
    return "; ".join("%s=%s" % (k, v) for k, v in cookies.items() if v)


# ---------------------------------------------------------------- 业务
def list_roles(cookie: str, region: str = "cn") -> list[dict]:
    """列出该 Cookie 绑定的原神角色（尽力而为；失败时抛 YyspError，可忽略）。"""
    if region == "os":
        url = OS_ROLES_URL
        headers = {
            "Cookie": cookie, "User-Agent": _UA,
            "x-rpc-app_version": "1.5.0", "x-rpc-client_type": "4",
            "x-rpc-language": "zh-cn",
            "Referer": "https://www.hoyolab.com/",
            "Accept": "application/json",
        }
    else:
        query = "game_biz=hk4e_cn"
        url = CN_ROLES_URL
        headers = {
            "Cookie": cookie, "User-Agent": _UA,
            "x-rpc-app_version": "2.3.0", "x-rpc-client_type": "5",
            "DS": _ds2(query=query),
            "Referer": "https://user.mihoyo.com/",
            "Accept": "application/json",
        }
    payload, _ = _request(url, headers)
    if payload.get("retcode") != 0:
        raise YyspError("获取角色列表失败：" + retcode_hint(payload))
    roles = ((payload.get("data") or {}).get("list")) or []
    return [{
        "nickname": r.get("nickname") or "",
        "game_uid": str(r.get("game_uid") or r.get("uid") or ""),
        "region": r.get("region") or "",
        "level": r.get("level"),
        "region_name": r.get("region_name") or "",
    } for r in roles]


def fetch_role_combat(cookie: str, uid: str, server: str, need_detail: bool = True,
                      timeout: int = 30) -> dict:
    """调用官方战绩 role_combat 接口，返回原始 JSON。"""
    params = urllib.parse.urlencode({
        "role_id": str(uid).strip(),
        "server": server,
        "need_detail": "true" if need_detail else "false",
    })
    url = (OS_RECORD_URL if is_os_server(server) else CN_RECORD_URL) + "?" + params
    payload, _ = _request(url, record_headers(cookie, server), timeout=timeout)
    if payload.get("retcode") != 0:
        raise YyspError("查询失败：" + retcode_hint(payload))
    return payload


def extract_cards(payload: dict) -> tuple[dict, list, dict]:
    """从接口返回中取出 (圣牌收藏, 圣牌列表, 本期统计)。"""
    data = payload.get("data") or {}
    state = data.get("tarot_card_state") or {}
    if not state:
        raise YyspError("接口返回成功，但没有 tarot_card_state 字段。\n"
                        "可能原因：该账号尚未解锁幻想真境剧诗，或游戏内未开启战绩展示。")
    cards = state.get("list") or []
    stat = {}
    datas = data.get("data") or []
    if datas:
        stat = datas[0].get("stat") or {}
        stat["schedule"] = datas[0].get("schedule") or {}
    return state, cards, stat


def download_icons(cards: list, out_dir: str, referer: str, log=None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    mapping, by_url = {}, {}
    headers = {"User-Agent": _UA, "Referer": referer}
    for i, card in enumerate(cards, 1):
        url = (card.get("icon") or "").strip()
        if not url:
            continue
        if url in by_url:
            mapping[card.get("icon")] = by_url[url]
            continue
        if url.startswith("//"):
            url = "https:" + url
        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".png"
        name = "card-%02d%s" % (i, ext)
        path = os.path.join(out_dir, name)
        try:
            if not os.path.exists(path):
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30,
                                            context=ssl.create_default_context()) as r:
                    blob = r.read()
                with open(path, "wb") as f:
                    f.write(blob)
                time.sleep(0.2)
        except Exception as exc:  # 图标失败不影响主流程
            if log:
                log("  [warn] 地图标下载失败 %s (%s)" % (url, exc))
            continue
        by_url[url] = name
        mapping[card.get("icon")] = name
    return mapping


CSS = """
 body{margin:0;padding:28px;background:radial-gradient(circle at 50% 0%,#3a2a4d,#181423 60%);color:#f2ecff;
      font-family:"HYWenHei","Microsoft YaHei",system-ui,sans-serif}
 h1{margin:0 0 6px;font-size:26px;letter-spacing:2px}
 .meta{color:#b9aed0;font-size:13px;margin-bottom:18px;line-height:1.7}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:14px}
 .card{position:relative;border:1px solid #6f4f74;border-radius:12px;padding:10px;background:rgba(111,79,116,.35);
       text-align:center}
 .card img{width:100%;height:auto;border-radius:8px;display:block}
 .card .name{font-size:13px;margin-top:8px}
 .card .idx{position:absolute;right:8px;top:8px;font-size:11px;color:#cbb9e6;opacity:.8}
 .card .cnt{position:absolute;left:6px;top:-8px;background:#e8c477;color:#2b1f33;border-radius:8px;
            font-size:11px;padding:1px 6px;font-weight:700}
 .locked{filter:grayscale(1);opacity:.45}
 .placeholder{width:100%;aspect-ratio:1/1;border-radius:8px;background:#2c2436;display:flex;
              align-items:center;justify-content:center;font-size:34px;color:#6f5f88}
 .footer{margin-top:22px;color:#8e83a8;font-size:12px;line-height:1.7}
 @media print{body{background:#fff;color:#222}.card{background:#faf7ff;border-color:#ddd}.meta,.footer{color:#555}}
"""


def render_html(state: dict, cards: list, icons: dict, uid: str, server: str,
                stat: dict | None = None) -> str:
    total = state.get("total_num") or len(cards)
    unlocked = state.get("curr_num") or sum(1 for c in cards if c.get("is_unlock"))
    stat = stat or {}
    items = []
    for i, card in enumerate(cards, 1):
        name = card.get("name") or ("未解锁" if not card.get("is_unlock") else "第%d张" % i)
        is_unlock = bool(card.get("is_unlock"))
        cnt = card.get("unlock_num") or 0
        icon = icons.get(card.get("icon")) or (card.get("icon") or "")
        if icon and not icon.startswith(("http", "//", "data:")):
            icon = "icons-%s/%s" % (uid, icon)
        badge = '<span class="cnt">×%d</span>' % cnt if (is_unlock and cnt > 1) else ""
        img = ('<img src="%s" alt="%s" loading="lazy">' % (html.escape(icon), html.escape(name))
               if icon else '<div class="placeholder">?</div>')
        items.append('<div class="%s">%s%s<div class="name">%s</div><div class="idx">#%02d</div></div>'
                     % ("card" if is_unlock else "card locked", img, badge, html.escape(name), i))
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    extra = ""
    if stat:
        parts = []
        if stat.get("difficulty_id") is not None:
            parts.append("本期难度 ID：%s%s" % (stat["difficulty_id"],
                                               "（月谕模式）" if stat.get("difficulty_id") == 5 else ""))
        if stat.get("tarot_finished_cnt") is not None:
            parts.append("本期圣牌挑战完成：%s" % stat["tarot_finished_cnt"])
        if stat.get("max_round_id") is not None:
            parts.append("本期最高幕数：%s" % stat["max_round_id"])
        if parts:
            extra = "<br>" + " &nbsp;·&nbsp; ".join(parts)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>月谕圣牌收藏 {unlocked}/{total} - UID {html.escape(uid)}</title>
<style>
{CSS}
</style></head><body>
<h1>「月谕圣牌」收藏 {unlocked} / {total}</h1>
<div class="meta">UID {html.escape(uid)} &nbsp;·&nbsp; {html.escape(server_name(server))} &nbsp;·&nbsp;
导出时间 {ts} &nbsp;·&nbsp; 数据来源：原神官方战绩 role_combat 接口{extra}</div>
<div class="grid">
{chr(10).join(items)}
</div>
<div class="footer">共 {total} 张，已解锁 {unlocked} 张。带 ×N 角标表示持有重复张数（可用于与好友交换）。<br>
由「月谕圣牌导出器」从米游社/HoYoLAB 战绩接口导出，仅用于个人数据备份。</div>
</body></html>"""


def export(cookie: str, uid: str, server: str, out_dir: str, log=None,
           save_raw: bool = True, with_icons: bool = True) -> dict:
    """一站式导出：接口取数 -> JSON + 本地图标 + HTML。返回结果信息。"""
    def _log(msg):
        if log:
            log(msg)

    uid = str(uid).strip()
    server = server or guess_server(uid)
    _log("查询 UID %s（%s）…" % (uid, server_name(server)))
    payload = fetch_role_combat(cookie, uid, server)
    state, cards, stat = extract_cards(payload)
    total = state.get("total_num") or len(cards)
    unlocked = state.get("curr_num") or sum(1 for c in cards if c.get("is_unlock"))
    _log("「月谕圣牌」收藏：%d / %d 张" % (unlocked, total))

    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "lunar-arcana-%s.json" % uid)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"uid": uid, "server": server, "server_name": server_name(server),
                   "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "tarot_card_state": state, "stat": stat,
                   **({"raw": payload} if save_raw else {})}, f, ensure_ascii=False, indent=2)
    _log("JSON  -> %s" % json_path)

    icons = {}
    if with_icons:
        referer = OS_REFERER if is_os_server(server) else CN_REFERER
        icons = download_icons(cards, os.path.join(out_dir, "icons-%s" % uid), referer, log=_log)
        _log("图标  -> %d 个" % len(set(icons.values())))

    html_path = os.path.join(out_dir, "lunar-arcana-%s.html" % uid)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(state, cards, icons, uid, server, stat))
    _log("HTML  -> %s" % html_path)

    return {"uid": uid, "server": server, "state": state, "cards": cards, "stat": stat,
            "total": total, "unlocked": unlocked,
            "json_path": json_path, "html_path": html_path, "raw": payload}
