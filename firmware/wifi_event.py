"""WiFi 자동 연결 — scan 먼저 + 등록된 SSID 중 in-range만 시도.

연결 순서:
1. wifi_config.json 에 저장된 SSID를 우선순위대로 시도 (AP 포털로 등록한 네트워크)
2. 이미 연결돼 있으면 그대로 사용
3. scan 결과에 없는 SSID는 건너뜀 (없는 네트워크에 timeout 낭비 방지)

wifi_config.json 형식: [{"ssid": "...", "password": "..."}, ...]
  - 부팅 시 BtnA를 누르고 있으면 AP 포털(wifi_setup.py)이 자동 생성
"""

import network
import json
import time

CFG_FILE = "/wifi_config.json"


def _load_config_networks():
    try:
        with open(CFG_FILE) as f:
            entries = json.load(f)
        return [(e["ssid"], e.get("password", "")) for e in entries if e.get("ssid")]
    except Exception:
        return []


def connect(timeout_ms=8000):
    combined = _load_config_networks()

    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    # 0) 이미 연결돼 있으면 그대로 사용
    if sta.isconnected():
        cfg = sta.ifconfig()
        return {"ssid": sta.config("essid"), "ok": True, "ip": cfg[0], "cached": True}

    if not combined:
        return {"ssid": None, "ok": False,
                "err": "no saved network — hold BtnA at boot"}

    # 1) scan으로 주변 SSID 파악 (실패 시 None → 전체 시도)
    seen = None
    try:
        seen = {n[0].decode("utf-8", "ignore").strip() for n in sta.scan()}
    except Exception:
        pass

    last_err = "no network in range"

    # 2) in-range 등록 SSID를 우선순위대로 시도
    for ssid, pw in combined:
        if seen is not None and ssid not in seen:
            continue
        try:
            sta.connect(ssid, pw)
            deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                if sta.isconnected():
                    cfg = sta.ifconfig()
                    return {"ssid": ssid, "ok": True, "ip": cfg[0]}
                time.sleep_ms(200)
            last_err = "timeout: " + ssid
        except Exception as e:
            last_err = str(e)

    # 3) scan이 비었거나 전부 실패 → scan 무시하고 한 바퀴 더
    if seen is not None:
        for ssid, pw in combined:
            if ssid in seen:
                continue  # 이미 시도함
            try:
                sta.connect(ssid, pw)
                deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
                while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                    if sta.isconnected():
                        cfg = sta.ifconfig()
                        return {"ssid": ssid, "ok": True, "ip": cfg[0]}
                    time.sleep_ms(200)
                last_err = "timeout: " + ssid
            except Exception as e:
                last_err = str(e)

    return {"ssid": None, "ok": False, "err": last_err}
