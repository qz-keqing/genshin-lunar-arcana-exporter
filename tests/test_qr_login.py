# -*- coding: utf-8 -*-
"""实测国服米游社扫码登录接口（createQRLogin / queryQRLoginStatus）。

只做“创建二维码 + 查询一次状态”，不涉及任何账号凭据；
用于验证 exe 的扫码登录通道在本机网络下可用。
"""
import json
import urllib.request
import uuid

CREATE = "https://passport-api.miyoushe.com/account/ma-cn-passport/web/createQRLogin"
QUERY = "https://passport-api.miyoushe.com/account/ma-cn-passport/web/queryQRLoginStatus"

device_id = str(uuid.uuid4())
headers = {
    "x-rpc-app_id": "bll8iq97cem8",
    "x-rpc-client_type": "4",
    "x-rpc-game_biz": "bbs_cn",
    "x-rpc-device_fp": "38d7fa104e5d7",
    "x-rpc-device_id": device_id,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Referer": "https://user.mihoyo.com/",
    "Origin": "https://user.mihoyo.com",
    "Content-Type": "application/json",
}


def post(url, payload=None, extra_headers=None):
    data = json.dumps(payload).encode() if payload is not None else b""
    req = urllib.request.Request(url, data=data, headers={**headers, **(extra_headers or {})}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        set_cookie = resp.headers.get_all("Set-Cookie") or []
    return body, set_cookie


print("device_id =", device_id)
created, _ = post(CREATE)
print("createQRLogin ->", json.dumps(created, ensure_ascii=False))

ticket = (created.get("data") or {}).get("ticket")
if not ticket:
    raise SystemExit("[x] 未拿到 ticket，扫码通道不可用")

status, set_cookie = post(QUERY, {"ticket": ticket})
print("queryQRLoginStatus ->", json.dumps(status, ensure_ascii=False))
print("Set-Cookie 条数 =", len(set_cookie), "（确认登录后这里会出现 ltoken_v2 / ltuid_v2 / cookie_token 等）")
print("[PASS] 扫码登录通道可用：二维码 URL =", (created.get("data") or {}).get("url"))
