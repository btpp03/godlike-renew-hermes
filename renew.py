#!/usr/bin/env python3
"""Godlike Host 免费服自动续期 / 保活。

续期两条腿（实测 2026-10-26）：
  1) POST /servers/{uuid}/free-renewal/vote   {"type":"vote_listing"}  -> +3h，24h 冷却
  2) POST /servers/{uuid}/free-renewal/video/start {"initial_time":0} -> 拿 session uuid
     然后每 30s POST /servers/{uuid}/free-renewal/video/update-time
        {"renewal_uuid":..., "video_time_watched":N, "time_correction":0}
     客户端 UI 在 240s / 480s 两个里程碑结算（服务端校验心跳间隔 25~35s，别改这个节奏）
另外顺手 POST /servers/{uuid}/power {"signal":"start"}，服务器不是 running 时拉起。

环境变量：GODLIKE_EMAIL / GODLIKE_PASSWORD
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://panel.godlike.host/api/v2"
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://ultra.panel.godlike.host",
    "Referer": "https://ultra.panel.godlike.host/",
}
HEARTBEAT = 30          # 服务端要求 25~35s 之间
TARGET = int(os.environ.get("GODLIKE_WATCH_SECONDS", "240"))  # 240s -> +24h（服务端单次上限 300）
KEEP_HOURS = float(os.environ.get("GODLIKE_KEEP_HOURS", "30"))  # 剩余超过就不折腾（24h 叠加，默认基本每轮都试）


def call(path, method="GET", body=None, token=None):
    h = dict(HDRS)
    data = None
    if body is not None:
        h["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(API + path, data=data, method=method, headers=h)
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, "EXC %s" % e


def jload(out):
    try:
        return json.loads(out)
    except Exception:  # noqa: BLE001
        return {}


def login():
    st, out = call("/auth/login", "POST", {
        "user": os.environ["GODLIKE_EMAIL"],
        "password": os.environ["GODLIKE_PASSWORD"],
    })
    d = jload(out)
    tok = (d.get("data") or {}).get("token")
    if not tok:
        print("!! 登录失败", st, out[:300])
        sys.exit(1)
    print("登录 OK", os.environ["GODLIKE_EMAIL"])
    return tok


def server_detail(tok, uuid):
    st, out = call("/servers/%s" % uuid, token=tok)
    return (jload(out).get("data") or {})


def hours_left(free_timer):
    """free_timer 形如 '2026-10-26 10:57:39'（UTC）。"""
    if not free_timer:
        return -1.0
    try:
        ts = time.mktime(time.strptime(free_timer, "%Y-%m-%d %H:%M:%S")) - time.timezone
    except Exception:  # noqa: BLE001
        return -1.0
    return (ts - time.time()) / 3600.0


def do_vote(tok, uuid):
    st, out = call("/servers/%s/free-renewal/vote" % uuid, "POST", {"type": "vote_listing"}, tok)
    d = jload(out)
    if st == 200 and d.get("success"):
        print("  vote: %s | new_free_timer=%s" % (d.get("message"), d.get("new_free_timer")))
        return True
    print("  vote 失败", st, out[:200].replace("\n", " "))
    return False


def do_video(tok, uuid):
    st, out = call("/servers/%s/free-renewal/video/start" % uuid, "POST", {"initial_time": 0}, tok)
    d = jload(out)
    sid = d.get("uuid")
    if not (st == 200 and d.get("success") and sid):
        print("  video start 失败", st, out[:200].replace("\n", " "))
        return False
    print("  video session", sid, "id", d.get("renewal_id"))
    watched = 0
    ok = True
    while watched < TARGET:
        time.sleep(HEARTBEAT)
        watched += HEARTBEAT
        st, out = call("/servers/%s/free-renewal/video/update-time" % uuid, "POST", {
            "renewal_uuid": sid,
            "video_time_watched": watched,
            "time_correction": 0,
        }, tok)
        d = jload(out)
        if st != 200 or not d.get("success"):
            if "must not be greater than" in out:
                print("  update-time %ss 到上限，按完成处理" % watched)
                break
            print("  update-time %ss 失败" % watched, st, out[:200].replace("\n", " "))
            ok = False
            break
        nt = d.get("new_free_timer")
        print("  watched %3ss ok%s" % (watched, ("  -> free_timer " + nt) if nt else ""))
    return ok


def main():
    tok = login()
    st, out = call("/servers", token=tok)
    servers = jload(out).get("data") or []
    if not servers:
        print("没有服务器，退出")
        return
    for s in servers:
        uuid = s.get("uuid")
        d = server_detail(tok, uuid)
        left = hours_left(d.get("free_timer"))
        print("== %s (%s) free=%s 剩余 %.1fh  status=%s" % (
            d.get("name"), uuid[:8], d.get("free"), left, d.get("status")))
        if not d.get("free"):
            print("  非免费服，跳过")
            continue

        # 保活：没在跑就 start（suspended 会 400，正常打印出来）
        if d.get("can_be_started") and d.get("status") not in ("running", "starting"):
            st2, out2 = call("/servers/%s/power" % uuid, "POST", {"signal": "start"}, tok)
            print("  power start ->", st2, out2[:120].replace("\n", " "))

        if left > KEEP_HOURS:
            print("  剩余 %.1fh > %.0fh 阈值，本次不续期" % (left, KEEP_HOURS))
            continue

        st3, out3 = call("/servers/%s/free-renewal/status?type=vote_listing" % uuid, token=tok)
        can_vote = jload(out3).get("can_vote")
        print("  can_vote =", can_vote)
        if can_vote:
            do_vote(tok, uuid)

        st4, out4 = call("/servers/%s/free-renewal/video/status?type=youtube_iter1" % uuid, token=tok)
        vid = jload(out4)
        print("  can_watch =", vid.get("can_watch"), "next in", vid.get("time_until_next_video"))
        if vid.get("can_watch"):
            do_video(tok, uuid)

        print("  结束后剩余 %.1fh" % hours_left(server_detail(tok, uuid).get("free_timer")))


if __name__ == "__main__":
    main()
