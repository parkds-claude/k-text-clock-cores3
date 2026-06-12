"""AP 모드 Wi-Fi 설정 포털 — CoreS3 Lite용

사용법:
  부팅 시 BtnA를 누르고 있으면 이 모듈이 실행된다.
  폰 Wi-Fi에서 'K-Text-Clock' 접속 → 브라우저 192.168.4.1 자동 오픈
  SSID 선택 + 비밀번호 입력 → 저장 → 기기 재시작
"""

import network
import socket
import json
import time
import machine

AP_SSID  = "K-Text-Clock"
CFG_FILE = "/wifi_config.json"


def _scan_ssids():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        nets = sta.scan()
    except Exception:
        return []
    seen = {}
    for n in nets:
        try:
            s = n[0].decode("utf-8", "ignore").strip()
            rssi = n[3]
        except Exception:
            continue
        if s and s not in seen:
            seen[s] = rssi
    return sorted(seen.keys(), key=lambda x: -seen[x])


def _url_decode(s):
    s = s.replace("+", " ")
    out = []
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            try:
                out.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
                continue
            except Exception:
                pass
        out.append(s[i])
        i += 1
    return "".join(out)


def _parse_form(body):
    params = {}
    for part in body.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[_url_decode(k)] = _url_decode(v)
    return params


def _build_page(ssids):
    opts = "\n".join(
        '<label><input type="radio" name="ssid" value="{s}"> {s}</label><br>'.format(s=s)
        for s in ssids
    ) or '<p style="color:#aaa">주변 네트워크 없음</p>'
    return (
        "<!DOCTYPE html><html><head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>"
        "body{font-family:sans-serif;margin:20px;background:#111;color:#eee}"
        "h2{color:#ff8c42}"
        "label{display:block;margin:8px 0;font-size:17px}"
        "input[type=text]{width:100%;padding:10px;margin:8px 0;font-size:16px;"
        "background:#222;color:#fff;border:1px solid #555;border-radius:5px}"
        "button{width:100%;padding:14px;background:#ff8c42;color:#000;"
        "font-size:18px;font-weight:bold;border:none;border-radius:6px;margin-top:16px}"
        "</style></head><body>"
        "<h2>K-Text Clock Wi-Fi 설정</h2>"
        '<form method="POST" action="/">'
        + opts
        + '<br><input type="text" name="password" placeholder="비밀번호 (오픈네트워크면 빈칸)" autocomplete="off">'
        "<button>저장 후 연결</button></form>"
        "</body></html>"
    ).encode("utf-8")


def _build_ok_page(ssid):
    return (
        "<!DOCTYPE html><html><head>"
        '<meta charset="utf-8">'
        "<style>body{font-family:sans-serif;margin:20px;background:#111;color:#eee}"
        "h2{color:#00e5ff}</style></head><body>"
        "<h2>저장 완료</h2>"
        "<p><b>{ssid}</b> 저장됐습니다.<br>기기가 재시작됩니다.</p>"
        "</body></html>".format(ssid=ssid)
    ).encode("utf-8")


def _send(conn, body, status=b"200 OK"):
    header = (
        b"HTTP/1.1 " + status + b"\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n\r\n"
    )
    conn.send(header + body)


def _recv_request(conn):
    req = b""
    conn.settimeout(5)
    try:
        while True:
            chunk = conn.recv(512)
            if not chunk:
                break
            req += chunk
            if b"\r\n\r\n" not in req:
                continue
            if not req.startswith(b"POST"):
                break
            hdr_end = req.index(b"\r\n\r\n") + 4
            cl = 0
            for line in req[:hdr_end].split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    try:
                        cl = int(line.split(b":", 1)[1].strip())
                    except Exception:
                        pass
            if len(req) - hdr_end >= cl:
                break
    except Exception:
        pass
    return req.decode("utf-8", "ignore")


def _show(lcd, line1, line2=""):
    if lcd is None:
        return
    lcd.fillScreen(0x000000)
    lcd.setTextColor(0x00e5ff, 0x000000)
    lcd.setTextSize(1.2)
    lcd.drawString(line1, 10, 70)
    if line2:
        lcd.setTextColor(0xffffff, 0x000000)
        lcd.setTextSize(1.0)
        lcd.drawString(line2, 10, 105)


def run(lcd=None):
    _show(lcd, "Wi-Fi 설정 모드", "AP 시작 중...")

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password="", authmode=0)  # open
    time.sleep(1)

    _show(lcd, "AP: " + AP_SSID, "192.168.4.1 접속하세요")

    ssids = _scan_ssids()
    if lcd:
        lcd.setTextColor(0x888888, 0x000000)
        lcd.setTextSize(0.9)
        lcd.drawString("{n}개 네트워크 발견".format(n=len(ssids)), 10, 135)

    page_html = _build_page(ssids)

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 80))
    srv.listen(3)
    srv.settimeout(180)  # 3분 타임아웃

    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            break

        req_str = _recv_request(conn)

        if req_str.startswith("POST") and "\r\n\r\n" in req_str:
            body = req_str.split("\r\n\r\n", 1)[1]
            params = _parse_form(body)
            ssid_val = params.get("ssid", "").strip()
            pw_val   = params.get("password", "").strip()

            if ssid_val:
                try:
                    with open(CFG_FILE) as f:
                        existing = json.load(f)
                except Exception:
                    existing = []
                existing = [e for e in existing if e.get("ssid") != ssid_val]
                existing.insert(0, {"ssid": ssid_val, "password": pw_val})
                with open(CFG_FILE, "w") as f:
                    json.dump(existing, f)

                _send(conn, _build_ok_page(ssid_val))
                conn.close()
                _show(lcd, "저장 완료!", ssid_val[:22])
                time.sleep(2)
                srv.close()
                ap.active(False)
                machine.soft_reset()
                return

        _send(conn, page_html)
        conn.close()

    srv.close()
    ap.active(False)
