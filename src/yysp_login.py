# -*- coding: utf-8 -*-
"""米游社扫码登录（国服）+ 本机登录态存取。

流程（米哈游官方 Web 扫码登录）：
  1. POST createQRLogin        -> {url, ticket}   把 url 画成二维码
  2. 米游社 App 扫码确认
  3. POST queryQRLoginStatus   -> status=Confirmed 时，响应头 Set-Cookie 里带回
     ltuid_v2 / ltoken_v2 / cookie_token 等登录 Cookie

国际服(HoYoLAB)官方未公开同款扫码流程，请改用 Cookie 粘贴方式。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid

QR_CREATE_URL = "https://passport-api.miyoushe.com/account/ma-cn-passport/web/createQRLogin"
QR_QUERY_URL = "https://passport-api.miyoushe.com/account/ma-cn-passport/web/queryQRLoginStatus"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

SESSION_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                           "YueYuShengPai")
SESSION_FILE = os.path.join(SESSION_DIR, "session.json")


class LoginError(Exception):
    pass


def _qr_headers(device_id: str) -> dict:
    return {
        "x-rpc-app_id": "bll8iq97cem8",
        "x-rpc-client_type": "4",
        "x-rpc-game_biz": "bbs_cn",
        "x-rpc-device_fp": "38d7fa104e5d7",
        "x-rpc-device_id": device_id,
        "User-Agent": _UA,
        "Referer": "https://user.mihoyo.com/",
        "Origin": "https://user.mihoyo.com",
        "Content-Type": "application/json",
    }


def _post(url: str, payload: dict | None, headers: dict, timeout: int = 30):
    data = json.dumps(payload).encode("utf-8") if payload is not None else b""
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
            cookies = {}
            for c in (resp.headers.get_all("Set-Cookie") or []):
                part = c.split(";")[0]
                if "=" in part:
                    k, v = part.split("=", 1)
                    cookies[k.strip()] = v.strip()
            return body, cookies
    except urllib.error.HTTPError as exc:
        raise LoginError("网络错误：HTTP %s %s" % (exc.code, exc.reason)) from exc
    except urllib.error.URLError as exc:
        raise LoginError("网络不通：%s" % exc) from exc


def create_qr(device_id: str | None = None) -> dict:
    """生成登录二维码。返回 {ticket, url, device_id}。"""
    device_id = device_id or str(uuid.uuid4())
    body, _ = _post(QR_CREATE_URL, None, _qr_headers(device_id))
    if body.get("retcode") != 0 or not (body.get("data") or {}).get("ticket"):
        raise LoginError("获取二维码失败：[%s] %s" % (body.get("retcode"), body.get("message")))
    return {"ticket": body["data"]["ticket"], "url": body["data"]["url"], "device_id": device_id}


def query_qr(ticket: str, device_id: str) -> dict:
    """查询扫码状态。返回 {status, cookies}。

    status: Created / Scanned / Confirmed；出错时抛 LoginError（含“已过期/已取消”）。
    """
    body, cookies = _post(QR_QUERY_URL, {"ticket": ticket}, _qr_headers(device_id))
    code = body.get("retcode")
    if code == -3501:
        raise LoginError("二维码已失效，请重新获取")
    if code == -3505:
        raise LoginError("已取消扫码登录，请重新获取二维码")
    if code != 0 or not body.get("data"):
        raise LoginError("查询扫码状态失败：[%s] %s" % (code, body.get("message")))
    return {"status": body["data"].get("status"), "cookies": cookies,
            "user_info": body["data"].get("user_info")}


# ---------------------------------------------------------------- 本机登录态
def save_session(cookie: str, uid: str = "", server: str = "") -> str:
    os.makedirs(SESSION_DIR, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"cookie": cookie, "uid": uid, "server": server,
                   "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False)
    try:  # 尽量收紧权限（仅当前用户可读）
        os.chmod(SESSION_FILE, 0o600)
    except OSError:
        pass
    return SESSION_FILE


def load_session() -> dict:
    try:
        with open(SESSION_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def clear_session() -> None:
    try:
        os.remove(SESSION_FILE)
    except OSError:
        pass
