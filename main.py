import matplotlib
matplotlib.use('Agg') # 화면 출력 없는 서버(CI/CD) 환경용 설정
import matplotlib.pyplot as plt

import os
import re
import time
import requests
import pandas as pd
import yfinance as yf
import mplfinance as mpf
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# GitHub Pages 기본 URL 설정 (본인 레포지토리 이름 확인)
GITHUB_PAGES_BASE_URL = "https://dhlee090512-arch.github.io/autoblog"

# 1. 환경변수 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

# 2. 외부 프롬프트 파일 로드 함수
def load_prompt(filename="prompt.txt"):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"{filename} 파일을 찾을 수 없습니다.")
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

# 3. 네이버/트레이딩뷰 스타일 (캔들+이평선+거래량+RSI) 차트 생성 함수
def safe_download_and_plot(ticker_symbol, title_prefix, filename):
    try:
        print(f"{ticker_symbol} 차트 데이터 다운로드 중...")
        df = yf.download(ticker_symbol, period="3mo", interval="1d", progress=False)
        if df.empty:
            print(f"{ticker_symbol} 데이터를 가져오지 못했습니다.")
            return None

        # yfinance 멀티인덱스 컬럼 구조 플랫화 및 데이터 타입 강제 변환
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()

        if df.empty or len(df) < 14:
            print(f"{ticker_symbol} 유효 데이터 부족.")
            return None

        # --- RSI(14) 보조지표 계산 ---
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # --- 네이버 증권 / 트레이딩뷰 룩앤필 색상 정의 ---
        mc = mpf.make_marketcolors(
            up='#e12343',      # 네이버 특유의 선명한 빨간 양봉
            down='#1763e0',    # 선명한 파란 음봉
            edge='inherit',
            wick='inherit',
            volume={'up': '#e12343', 'down': '#1763e0'}
        )

        style = mpf.make_mpf_style(
            marketcolors=mc,
            gridstyle=':',              # 연한 점선 그리드
            gridcolor='#e6e8eb',
            facecolor='#ffffff',        # 흰색 배경
            figcolor='#ffffff',
            y_on_right=True             # 트레이딩뷰/국내 증권사처럼 우측 가격 축
        )

        # --- 패널 구성 (패널 0: 캔들/이평선, 패널 1: 거래량, 패널 2: RSI) ---
        addplots = [
            mpf.make_addplot(df['RSI'], panel=2, color='#8e44ad', ylabel='RSI', secondary_y=False),
            mpf.make_addplot([70]*len(df), panel=2, color='#e74c3c', linestyle='--', width=0.8),
            mpf.make_addplot([30]*len(df), panel=2, color='#2980b9', linestyle='--', width=0.8),
        ]

        mpf.plot(
            df,
            type='candle',
            mav=(5, 20, 60),            # 5일, 20일, 60일 이동평균선
            volume=True,                # 거래량 패널
            addplot=addplots,
            panel_ratios=(5, 2, 2),     # 캔들:거래량:RSI 영역 비율
            title=f"\n{title_prefix} ({ticker_symbol})",
            style=style,
            savefig=filename,
            figratio=(12, 8),
            figscale=1.1
        )
        print(f"차트 이미지 생성 완료: {filename}")
        return filename
    except Exception as e:
        print(f"{ticker_symbol} 차트 생성 오류: {e}")
        return None

# 4. 대시보드 크롤링 함수
def fetch_dashboard_data(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.get_text(separator="\n", strip=True)

print("국장 및 미장 대시보드 데이터 수집 중...")
kr_raw = fetch_dashboard_data("https://dhlee090512-arch.github.io/report/index.html")
us_raw = fetch_dashboard_data("https://dhlee090512-arch.github.io/report/us_index.html")

# 5. Gemini API 호출
system_instruction = load_prompt("prompt.txt")
user_prompt = f"--- [국장 대시보드 Data] ---\n{kr_raw[:3500]}\n\n--- [미장 대시보드 Data] ---\n{us_raw[:3500]}"

max_retries = 3
retry_delay = 10  
response = None

for attempt in range(1, max_retries + 1):
    try:
        print(f"Gemini API 호출 중 (시도 {attempt}/{max_retries})...")
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.75,
            ),
        )
        break  
    except Exception as e:
        print(f"API 호출 실패 (에러: {e})")
        if attempt < max_retries:
            print(f"{retry_delay}초 후 재시도합니다...")
            time.sleep(retry_delay)
        else:
            raise RuntimeError("Gemini API 호출이 최대 재시도 횟수를 초과하여 실패했습니다.")

raw_blog_text = response.text

# 6. 차트 생성
fx_chart = safe_download_and_plot("KRW=X", "USD/KRW Exchange Rate", "usdkrw_chart.png")
celtrion_chart = safe_download_and_plot("068270.KS", "Celltrion", "celtrion_chart.png")
bac_chart = safe_download_and_plot("BAC", "Bank of America", "bac_chart.png")

# 7. 제목 파싱 및 본문 중간중간에 차트 이미지 동적 매핑
post_title = "오늘의 경제 주요 흐름 및 특징주 분석"
body_text = raw_blog_text

lines = raw_blog_text.strip().split("\n")
for line in lines:
    if line.startswith("[제목]") or line.startswith("제목:"):
        post_title = re.sub(r"^\[제목\]\s*|^제목:\s*", "", line).strip()
        body_text = "\n".join([l for l in lines if l != line]).strip()
        break

# 태그 매핑
chart_imgs = {
    "fx": f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{fx_chart}" alt="환율 차트"></div>' if fx_chart else '',
    "celtrion": f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{celtrion_chart}" alt="셀트리온 차트"></div>' if celtrion_chart else '',
    "bac": f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{bac_chart}" alt="BAC 차트"></div>' if bac_chart else '',
}

# 텍스트 섹션 중간에 이미지 삽입
formatted_body = body_text

# [경제 이슈] 섹션 다음에 환율 차트 삽입
if "[경제 이슈]" in formatted_body and fx_chart:
    formatted_body = formatted_body.replace("[경제 이슈]", f"[경제 이슈]\n{chart_imgs['fx']}")

# 종목별 서술 다음에 해당 차트 삽입 (셀트리온, BAC 예시)
if "셀트리온" in formatted_body and celtrion_chart:
    # 셀트리온 문단 뒤쪽에 이미지 배치되도록 처리
    formatted_body = re.sub(r"(1\.\s*셀트리온[^\n]*\n)", r"\1" + chart_imgs['celtrion'] + "\n", formatted_body)

if ("Bank of America" in formatted_body or "BAC" in formatted_body) and bac_chart:
    formatted_body = re.sub(r"(\d+\.\s*(?:Bank of America|BAC)[^\n]*\n)", r"\1" + chart_imgs['bac'] + "\n", formatted_body)


# 8. HTML 미리보기 파일 생성
html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>{post_title}</title>
    <style>
        body {{ font-family: 'Apple SD Gothic Neo', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.7; color: #333; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; font-size: 24px; }}
        .title-box {{ background: #eef5ff; border-left: 5px solid #2b7de9; padding: 15px; margin-bottom: 25px; border-radius: 4px; font-size: 18px; font-weight: bold; color: #1a498b; }}
        .content {{ white-space: pre-wrap; background: #fafafa; padding: 25px; border-radius: 8px; font-size: 16px; word-break: break-all; border: 1px solid #eee; }}
        .img-box {{ margin: 20px 0; text-align: center; }}
        img {{ max-width: 100%; height: auto; border: 1px solid #e1e4e8; border-radius: 6px; display: block; margin: 0 auto; }}
    </style>
</head>
<body>
    <h1>📊 자동 생성 블로그 포스팅 미리보기</h1>
    <p>아래 제목과 본문을 드래그해서 그대로 블로그에 붙여넣으세요.</p>
    <hr>
    
    <h3>📌 포스팅 제목</h3>
    <div class="title-box">{post_title}</div>

    <h3>📝 본문 텍스트 (차트 포함)</h3>
    <div class="content">{formatted_body}</div>
</body>
</html>
"""

with open("blog_preview.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("blog_preview.html 파일 생성 완료!")
