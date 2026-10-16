import matplotlib
matplotlib.use('Agg') # 화면 출력 없는 서버(CI/CD) 환경용 설정
import matplotlib.pyplot as plt

import os
import time
import requests
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

# 3. 환율 차트 이미지 생성 함수
def generate_usd_krw_chart():
    chart_filename = "usdkrw_chart.png"
    try:
        print("원/달러 환율 차트 생성 중...")
        df = yf.download("KRW=X", period="3m", interval="1d")
        if df.empty:
            print("환율 데이터를 가져오지 못했습니다.")
            return None

        mc = mpf.make_marketcolors(up='red', down='blue', edge='inherit', wick='inherit', volume='in')
        style = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=False)

        mpf.plot(
            df,
            type='candle',
            mav=(20, 60),
            volume=True,
            title="\nUSD/KRW Exchange Rate (3 Months)",
            style=style,
            savefig=chart_filename,
            figratio=(12, 6),
            figscale=1.0
        )
        print(f"차트 이미지 생성 완료: {chart_filename}")
        return chart_filename
    except Exception as e:
        print(f"차트 생성 오류: {e}")
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

# 5. Gemini API 호출 (외부 prompt.txt 로드 및 재시도 로직)
system_instruction = load_prompt("prompt.txt")
user_prompt = f"--- [국장 대시보드 Data] ---\n{kr_raw[:3500]}\n\n--- [미장 대시보드 Data] ---\n{us_raw[:3500]}"

max_retries = 3
retry_delay = 10  # 실패 시 대기 시간 (초)
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
        break  # 성공 시 반복문 탈출
    except Exception as e:
        print(f"API 호출 실패 (에러: {e})")
        if attempt < max_retries:
            print(f"{retry_delay}초 후 재시도합니다...")
            time.sleep(retry_delay)
        else:
            raise RuntimeError("Gemini API 호출이 최대 재시도 횟수를 초과하여 실패했습니다.")

blog_text = response.text
chart_file = generate_usd_krw_chart()

# 6. HTML 미리보기 파일 생성 (GitHub Pages 전체 URL로 이미지 연결)
if chart_file:
    chart_img_url = f"{GITHUB_PAGES_BASE_URL}/{chart_file}"
    chart_img_html = f'<img src="{chart_img_url}" alt="환율 차트">'
else:
    chart_img_html = '<p>차트 이미지가 생성되지 않았습니다.</p>'

html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>오늘의 블로그 포스팅 초안</title>
    <style>
        body {{ font-family: 'Apple SD Gothic Neo', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; color: #333; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .content {{ white-space: pre-wrap; background: #f9f9f9; padding: 20px; border-radius: 8px; font-size: 16px; word-break: break-all; }}
        img {{ max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; border-radius: 4px; display: block; }}
    </style>
</head>
<body>
    <h1>📊 오늘의 자동 생성 블로그 포스팅 초안</h1>
    <p>이 페이지는 GitHub Actions에 의해 자동 생성되었습니다. 내용을 복사해서 블로그에 붙여넣으세요.</p>
    <hr>
    
    <h3>📈 환율 차트</h3>
    {chart_img_html}

    <h3>📝 본문 텍스트</h3>
    <div class="content">{blog_text}</div>
</body>
</html>
"""

with open("blog_preview.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("blog_preview.html 파일 생성 완료!")
