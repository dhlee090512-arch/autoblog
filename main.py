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
        raise FileNotFoundError(f"{filename} 파일을 찾을 수 없습니다. 레포지토리에 prompt.txt가 있는지 확인해 주세요.")
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

# 3. 데이터 타입 오류 방지 및 안전한 차트 생성 헬퍼 함수
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

        if df.empty:
            print(f"{ticker_symbol} 유효한 수치 데이터가 없습니다.")
            return None

        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit', volume='in')
        style = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=False)

        mpf.plot(
            df,
            type='candle',
            mav=(20, 60),
            volume=True,
            title=f"\n{title_prefix} ({ticker_symbol})",
            style=style,
            savefig=filename,
            figratio=(12, 6),
            figscale=1.0
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

# 6. 제목 및 본문 파싱 로직
post_title = "오늘의 블로그 포스팅"
body_text = raw_blog_text

lines = raw_blog_text.strip().split("\n")
for line in lines:
    if line.startswith("[제목]") or line.startswith("제목:"):
        post_title = re.sub(r"^\[제목\]\s*|^제목:\s*", "", line).strip()
        body_text = "\n".join([l for l in lines if l != line]).strip()
        break

# 7. 환율 및 특징주 차트 이미지 다운로드
charts = {}
fx_chart = safe_download_and_plot("KRW=X", "USD/KRW Exchange Rate", "usdkrw_chart.png")
if fx_chart:
    charts["환율 차트"] = fx_chart

celtrion_chart = safe_download_and_plot("068270.KS", "Celltrion", "celtrion_chart.png")
if celtrion_chart:
    charts["셀트리온 차트"] = celtrion_chart

bac_chart = safe_download_and_plot("BAC", "Bank of America", "bac_chart.png")
if bac_chart:
    charts["Bank of America 차트"] = bac_chart

# 8. HTML 미리보기 파일 생성
charts_html = ""
for title, filename in charts.items():
    img_url = f"{GITHUB_PAGES_BASE_URL}/{filename}"
    charts_html += f"""
    <div class="chart-box">
        <h3>📈 {title}</h3>
        <img src="{img_url}" alt="{title}">
    </div>
    """

if not charts_html:
    charts_html = '<p>생성된 차트가 없습니다.</p>'

html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>{post_title}</title>
    <style>
        body {{ font-family: 'Apple SD Gothic Neo', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; color: #333; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; font-size: 24px; }}
        .title-box {{ background: #eef5ff; border-left: 5px solid #2b7de9; padding: 15px; margin-bottom: 25px; border-radius: 4px; font-size: 18px; font-weight: bold; color: #1a498b; }}
        .content {{ white-space: pre-wrap; background: #f9f9f9; padding: 20px; border-radius: 8px; font-size: 16px; word-break: break-all; margin-bottom: 30px; }}
        .chart-box {{ margin: 30px 0; padding: 15px; border: 1px solid #e1e4e8; border-radius: 8px; background: #fff; }}
        img {{ max-width: 100%; height: auto; display: block; margin: 0 auto; }}
    </style>
</head>
<body>
    <h1>📊 자동 생성 블로그 포스팅 미리보기</h1>
    <p>아래 제목과 본문 텍스트를 복사해서 블로그에 올려주세요.</p>
    <hr>
    
    <h3>📌 포스팅 제목</h3>
    <div class="title-box">{post_title}</div>

    <h3>📝 본문 텍스트</h3>
    <div class="content">{body_text}</div>

    <hr>
    <h2>📊 분석 차트 모음</h2>
    {charts_html}
</body>
</html>
"""

with open("blog_preview.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("blog_preview.html 파일 생성 완료!")
