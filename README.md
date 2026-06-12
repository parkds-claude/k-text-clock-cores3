# K-Text Clock for M5Stack CoreS3

> 매 분, 그 시각이 등장하는 한국 문학의 문장을 보여주는 책상 위 텍스트 시계.

`19:00` → *"저녁 일곱 시쯤 해서 하는 두 번째 세수는 손이 많이 간다."* — 이상, 「날개」

**서버가 필요 없습니다.** Wi-Fi만 연결하면 [한문장 아카이브](https://github.com/parkds-claude/k-text-clock-web)의
공개 데이터(GitHub Pages)에서 문장을 직접 받아 표시합니다. 시각은 NTP로 동기화합니다.

## 필요한 것

- [M5Stack CoreS3](https://shop.m5stack.com/products/m5stack-cores3-esp32s3-lotdevelopment-kit) 또는 CoreS3 SE — UIFlow 2.0 펌웨어 (출하 기본)
- 2.4GHz Wi-Fi
- 업로드용 컴퓨터 (macOS/Linux/Windows) + USB-C 케이블

## 설치

```bash
pip install mpremote
git clone https://github.com/parkds-claude/k-text-clock-cores3.git
cd k-text-clock-cores3
./scripts/push.sh
```

업로드 후 기기를 재시작(RST)하세요. UIFlow2 홈 화면이 나오면
런처에서 **k_text_clock**을 선택해 실행합니다.

> **Windows**: 포트 자동 탐지가 지원되지 않으므로 Git Bash에서
> `PORT=COM3 ./scripts/push.sh` 처럼 포트를 직접 지정하세요.

## Wi-Fi 설정 (코드 수정 불필요)

1. 부팅 직후 3초 안에 **BtnA를 길게 누르면** 설정 모드 진입
2. 폰 Wi-Fi에서 `K-Text-Clock` 네트워크에 접속
3. 브라우저에서 `192.168.4.1` 접속 → 주변 네트워크 선택 + 비밀번호 입력
4. 저장하면 기기가 재시작되고 자동 연결

설정은 기기의 `/wifi_config.json`에 저장됩니다. 이 레포 코드에는 어떤
네트워크 정보도 하드코딩되어 있지 않습니다.

> **주의**: 설정 모드의 `K-Text-Clock` AP는 암호 없이 열리며 비밀번호가
> 평문 HTTP로 전송됩니다. 카페 등 공공장소가 아닌 곳에서 설정하세요.

## 화면 구성

```
19:07              K-Text Clock      ← 시각(주황) / 브랜드
─────────────────────────────────
저녁 일곱 시쯤 해서 하는 두 번째
세수는 손이 많이 간다.              ← 본문 (최대 6줄/페이지,
                                      긴 문장은 10초마다 페이지 전환)
─────────────────────────────────
1/2            — 이상, 「날개」      ← 페이지 / 출처(형광파랑)
```

**모든 문장에는 출처(작가·작품)가 항상 함께 표시됩니다.**

## 설정 변경

[firmware/main.py](firmware/main.py) 상단 상수만 수정하면 됩니다:

| 상수 | 기본값 | 설명 |
|------|--------|------|
| `TZ_OFFSET_H` | `9` | 시간대 (KST=+9) |
| `LCD_BRIGHTNESS` | `128` | 화면 밝기 (0~255) |
| `PAGE_SECS` | `10` | 긴 문장 페이지 전환 간격(초) |
| `DATA_BASE` | 한문장 Pages URL | 데이터 출처 (자체 호스팅 시 변경) |

## 데이터 출처와 저작권

- 문장 데이터: [k-text-clock-web](https://github.com/parkds-claude/k-text-clock-web) — **CC BY 4.0**
- 수록 기준: **저자 사후 70년 이상 경과한 Public Domain 작품만** (대한민국 저작권법 기준)
- 원문 출처: 위키문헌(ko.wikisource.org) 등 — 항목별 출처 URL은 데이터 레포의
  `data/quotes_public.json` 각 항목 `source.url`에 기록
- 모든 문장은 화면에 작가·작품(`— 작가, 「작품」`)을 표기합니다
- 출처 오류·저작권 문의: [데이터 레포 Issues](https://github.com/parkds-claude/k-text-clock-web/issues)

## 문장 기여

읽던 책에서 시각이 등장하는 PD 문장을 발견하셨다면 —
[기여 가이드](https://github.com/parkds-claude/k-text-clock-web/blob/main/CONTRIBUTING.md)를 참고해 주세요.

## 라이선스

- 코드: [MIT](LICENSE)
- 문장 데이터: CC BY 4.0 (데이터 레포 참조)
