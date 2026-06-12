"""
K-Text Clock — M5Stack CoreS3 텍스트 시계 (공개판)

매 분, 그 시각이 등장하는 한국 근대문학 문장을 화면에 표시한다.
서버가 필요 없다 — 데이터는 한문장 아카이브(GitHub Pages 정적 JSON)에서
직접 받고, 시각은 NTP로 동기화한다.

화면 레이아웃 (320×240):
  헤더:  시각(좌,주황) + "K-Text Clock"(우,회색)  Montserrat18  y=8
  본문:  6줄/페이지  AlibabaSansKR24 scale=1.0  y=42~177 (27px 간격)
  출처:  "— 작가, 「작품」" 한 줄  y=218 우측정렬 형광파랑
  긴 인용은 6줄 초과분을 10초마다 다음 페이지로 로테이션(잘라 버리지 않음).

데이터: https://github.com/parkds-claude/k-text-clock-web (CC BY 4.0)
모든 문장은 저작권 만료(Public Domain) 작품이며 출처가 함께 표시된다.
"""

import M5
from M5 import Widgets
import requests
import time
import wifi_event

# UIFlow 부팅 시 M5가 이미 초기화되어 있을 수 있음.
# 중복 호출은 USB 재열거를 유발하므로 미초기화 상태일 때만 호출.
try:
    Widgets.fillScreen(0x000000)  # 이미 초기화됐으면 성공
except Exception:
    M5.begin()

# ── 설정 ──────────────────────────────────────────────────────
DATA_BASE   = "https://parkds-claude.github.io/k-text-clock-web/data/times/"
TZ_OFFSET_H = 9          # 시간대 (KST = UTC+9). 다른 지역이면 이 값만 변경.
PAGE_SECS   = 10         # 6줄 초과 인용: N초마다 다음 페이지
MAX_LINES   = 6          # 한 페이지당 본문 줄 수
_MAX_TOTAL_LINES = 24    # 페이지네이션 안전 상한(=4페이지)
NTP_RESYNC_S = 6 * 3600  # NTP 재동기화 주기
LCD_BRIGHTNESS = 128     # 0~255

BG     = 0x000000
FG     = 0xffffff
DIM    = 0x888888
ORANGE = 0xff8c42  # 시계
CYAN   = 0x00e5ff  # 출처
ERR_C  = 0xff4444

F_HEAD = Widgets.FONTS.Montserrat18
F_BODY = Widgets.FONTS.AlibabaSansKR24
F_SMAL = Widgets.FONTS.Montserrat14

# 본문 픽셀 기반 줄바꿈 상수 (AlibabaSansKR24 scale=1.0 실측 비례값)
_BODY_KO  = 22   # 한글 1자
_BODY_SP  = 6    # 공백
_BODY_AS  = 12   # ASCII
_MAX_LINE = 300  # x=10 시작, 우측 10px 여백
_SRC_RIGHT = 310

BODY_Y = [42, 69, 96, 123, 150, 177]

for _b in (lambda: M5.Lcd.setBrightness(LCD_BRIGHTNESS),
           lambda: M5.Display.setBrightness(LCD_BRIGHTNESS)):
    try:
        _b(); break
    except Exception:
        pass

Widgets.fillScreen(BG)
lbl_error = Widgets.Label("", 10, 192, 1.0, ERR_C, BG, F_SMAL)

# ── 부팅 시 BtnA: Wi-Fi 설정 모드 ────────────────────────────
M5.Lcd.setFont(F_SMAL)
M5.Lcd.setTextSize(1.0)
M5.Lcd.setTextColor(DIM, BG)
M5.Lcd.drawString("BtnA: Wi-Fi setup", 10, 218)
_setup_deadline = time.ticks_add(time.ticks_ms(), 3000)
while time.ticks_diff(_setup_deadline, time.ticks_ms()) > 0:
    M5.update()
    if M5.BtnA.isPressed():
        M5.Lcd.fillRect(0, 210, 320, 32, BG)
        import wifi_setup
        wifi_setup.run(lcd=M5.Lcd)  # 저장 후 machine.soft_reset() 내부 호출
        break
    time.sleep_ms(50)
M5.Lcd.fillRect(0, 210, 320, 32, BG)

lbl_error.setText("Wi-Fi...")
_wifi = wifi_event.connect(timeout_ms=12000)
if not _wifi["ok"]:
    lbl_error.setText("Wi-Fi fail — hold BtnA at boot to set up")
    time.sleep(5)
lbl_error.setText("")

# ── NTP 시각 동기화 ───────────────────────────────────────────
_ntp_ok = False
_last_ntp_ms = 0


def ntp_sync():
    """RTC를 UTC로 설정. 실패해도 조용히 넘어가고 다음 주기에 재시도."""
    global _ntp_ok, _last_ntp_ms
    try:
        import ntptime
        ntptime.settime()
        _ntp_ok = True
    except Exception:
        pass
    _last_ntp_ms = time.ticks_ms()


def local_hm():
    """(HH, MM) 현지 시각. NTP 미동기화면 None."""
    if not _ntp_ok:
        return None
    t = time.time() + TZ_OFFSET_H * 3600
    lt = time.localtime(t)
    return lt[3], lt[4]


def clock_str():
    hm = local_hm()
    return "--:--" if hm is None else "{:02d}:{:02d}".format(hm[0], hm[1])


# ── 픽셀 기반 한글 줄바꿈 ──────────────────────────────────────

def _cpx(c):
    if ord(c) > 0x7F:
        return _BODY_KO
    if c == ' ':
        return _BODY_SP
    return _BODY_AS


def _wpx(word):
    return sum(_cpx(c) for c in word)


def wrap_ko(text):
    """본문 줄바꿈. 전체 줄을 반환(페이지네이션이 6줄씩 분할)."""
    if not text:
        return [""]
    text = text.replace('\n', ' ').replace('\r', ' ')
    words = text.split()
    lines = []
    cur = ""
    cur_px = 0

    def flush():
        nonlocal cur, cur_px
        if cur:
            lines.append(cur)
        cur = ""
        cur_px = 0

    def force_split(word):
        nonlocal cur, cur_px
        while word and len(lines) < _MAX_TOTAL_LINES:
            chunk = ""
            cpx = 0
            for c in word:
                cp = _cpx(c)
                if cpx + cp > _MAX_LINE:
                    break
                chunk += c
                cpx += cp
            if not chunk:
                break
            if len(lines) < _MAX_TOTAL_LINES - 1:
                lines.append(chunk)
                word = word[len(chunk):]
            else:
                cur = chunk
                cur_px = cpx
                return
        cur = ""
        cur_px = 0

    for word in words:
        if len(lines) >= _MAX_TOTAL_LINES:
            break
        wpx = _wpx(word)
        if not cur:
            if wpx > _MAX_LINE:
                force_split(word)
            else:
                cur = word
                cur_px = wpx
        else:
            if cur_px + _BODY_SP + wpx <= _MAX_LINE:
                cur += " " + word
                cur_px += _BODY_SP + wpx
            else:
                flush()
                if len(lines) >= _MAX_TOTAL_LINES:
                    break
                if wpx > _MAX_LINE:
                    force_split(word)
                else:
                    cur = word
                    cur_px = wpx

    if cur and len(lines) < _MAX_TOTAL_LINES:
        lines.append(cur)
    return lines or [""]


def _paginate(lines):
    pages = []
    for i in range(0, len(lines), MAX_LINES):
        pg = lines[i:i + MAX_LINES]
        while len(pg) < MAX_LINES:
            pg.append("")
        pages.append(pg)
    return pages or [[""] * MAX_LINES]


# ── 렌더링 (직접 LCD — 위젯 잔상 없음) ────────────────────────
_src_text = ""
_src_x = 10
_pages = [["" for _ in range(MAX_LINES)]]
_page_idx = 0
_last_page_ms = 0

PAGE_IND_W = 58  # 좌하단 페이지 표시(2/3) 전용 폭


def _draw_header(time_str):
    M5.Lcd.fillRect(0, 0, 320, 35, BG)
    M5.Lcd.setFont(F_HEAD)
    M5.Lcd.setTextSize(1.0)
    M5.Lcd.setTextColor(ORANGE, BG)
    M5.Lcd.drawString(time_str, 10, 8)
    M5.Lcd.setTextColor(DIM, BG)
    M5.Lcd.drawString("K-Text Clock", 200, 8)


def _draw_body(lines):
    M5.Lcd.fillRect(0, 35, 320, 175, BG)
    M5.Lcd.setFont(F_BODY)
    M5.Lcd.setTextSize(1.0)
    M5.Lcd.setTextColor(FG, BG)
    for i, line in enumerate(lines):
        if line:
            M5.Lcd.drawString(line, 10, BODY_Y[i])


def _draw_page_indicator(clear=True):
    if clear:
        M5.Lcd.fillRect(0, 210, PAGE_IND_W, 32, BG)
    if len(_pages) > 1:
        M5.Lcd.setFont(F_SMAL)
        M5.Lcd.setTextSize(1.0)
        M5.Lcd.setTextColor(DIM, BG)
        M5.Lcd.drawString("%d/%d" % (_page_idx + 1, len(_pages)), 10, 222)


def _draw_source():
    M5.Lcd.fillRect(0, 210, 320, 32, BG)
    _draw_page_indicator(clear=False)
    if not _src_text:
        return
    M5.Lcd.setFont(F_BODY)
    M5.Lcd.setTextSize(0.75)
    M5.Lcd.setTextColor(CYAN, BG)
    M5.Lcd.drawString(_src_text, _src_x, 218)


def update_display(entry):
    """슬롯 JSON 항목 {text_ko, display_source, ...} 하나를 화면에 반영."""
    global _src_text, _src_x, _pages, _page_idx, _last_page_ms

    _pages = _paginate(wrap_ko(entry.get("text_ko") or ""))
    _page_idx = 0
    _last_page_ms = time.ticks_ms()
    _draw_body(_pages[0])

    # 출처는 항상 표시 — 모든 문장은 PD 작품이며 작가·작품을 밝힌다.
    _src_text = (entry.get("display_source") or "").strip()[:40]
    M5.Lcd.setFont(F_BODY)
    M5.Lcd.setTextSize(0.75)
    src_w = M5.Lcd.textWidth(_src_text)
    left = PAGE_IND_W if len(_pages) > 1 else 10
    _src_x = max(left, _SRC_RIGHT - src_w)
    _draw_source()

    lbl_error.setText("")


# ── 데이터 fetch ──────────────────────────────────────────────

def fetch_minute(h, m):
    """해당 분의 슬롯 JSON에서 첫 항목 반환. 실패 시 None."""
    url = "{}{:02d}_{:02d}.json".format(DATA_BASE, h, m)
    resp = None
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            return data[0] if data else None  # 빈 슬롯 — 직전 문장 유지
        lbl_error.setText("HTTP " + str(resp.status_code))
    except Exception as e:
        lbl_error.setText(str(e)[:38])
    finally:
        # MicroPython은 소켓을 GC가 즉시 회수하지 않음 — 누수 시 ENOMEM
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
    return None


# ── 메인 루프 ──────────────────────────────────────────────────
ntp_sync()
_last_shown_minute = None   # "HH:MM" — 분이 바뀔 때만 fetch
_last_clock_str = None      # 깜박임 방지: 표시 시각이 바뀔 때만 헤더 재렌더

while True:
    ticks = time.ticks_ms()
    M5.update()

    # NTP: 미동기화면 1분마다, 동기화 후엔 6시간마다 재시도
    retry_ms = 60 * 1000 if not _ntp_ok else NTP_RESYNC_S * 1000
    if time.ticks_diff(ticks, _last_ntp_ms) >= retry_ms:
        ntp_sync()

    cs = clock_str()
    if cs != _last_clock_str:
        _draw_header(cs)
        _last_clock_str = cs

    hm = local_hm()
    if hm is not None and cs != _last_shown_minute:
        entry = fetch_minute(hm[0], hm[1])
        if entry:
            update_display(entry)
        _last_shown_minute = cs

    # 긴 인용: 페이지가 2개 이상이면 PAGE_SECS마다 다음 페이지로
    if len(_pages) > 1 and \
            time.ticks_diff(ticks, _last_page_ms) >= PAGE_SECS * 1000:
        _page_idx = (_page_idx + 1) % len(_pages)
        _draw_body(_pages[_page_idx])
        _draw_page_indicator()
        _last_page_ms = ticks

    time.sleep_ms(500)
