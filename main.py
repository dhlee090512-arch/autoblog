import matplotlib
matplotlib.use('Agg') # 화면 출력 없는 서버 환경용 설정
import matplotlib.pyplot as plt

import os
import time
import requests
import yfinance as yf
import mplfinance as mpf
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# 1. 환경변수 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

# 2. 환율 차트 이미지 생성 함수
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

# 3. 대시보드 크롤링 함수
def fetch_dashboard_data(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.get_text(separator="\n", strip=True)

print("국장 및 미장 대시보드 데이터 수집 중...")
kr_raw = fetch_dashboard_data("https://dhlee090512-arch.github.io/report/index.html")
us_raw = fetch_dashboard_data("https://dhlee090512-arch.github.io/report/us_index.html")

# 4. Gemini API 호출 (재시도 로직 포함)
system_instruction = """
너는 개인 주식/트레이딩 블로거야.
입력된 국장/미장 대시보드 데이터 및 환율/매크로 브리핑을 바탕으로 블로그 포스팅 초안을 작성해줘.

[작성 지침 및 톤앤매너]
1. 주식 커뮤니티나 개인 트레이더 블로그에서 쓰는 담백하고 솔직한 구어체 및 어휘를 쓸 것.
   (예: "나락가면서", "짧게 먹는게", "손익비가 좋아보이는데", "슬퍼서 안가져올 수도 있습니다 ㅜ", "씁쓸하네요", "끗")
2. AI 특유의 뻔한 인사말이나 딱딱한 서술어, 상투적인 비유는 절대 쓰지 말 것.
3. 소제목 구획은 [환율], [특징주] 형태로 나눌 것.
4. [환율] 파트는 수집된 매크로 지표/뉴스 데이터를 기반으로 최근 저점 수준, 연준/외환당국 동향, 중단기 상방 가능성 및 대응 방향을 정리할 것.
5. [특징주] 파트는 국장과 미장 대시보드에서 각각 추천 상위 종목을 2개씩 선정하여 총 4개 내외로 구성할 것.
6. 각 종목별로 거래량, RSI, 수급/뉴스 포인트, 그리고 구체적인 눌림목 타점/가격 수치를 직관적이고 가볍게 풀어서 쓸 것.
7. 글 마무리는 시장 상황에 대한 짧은 한 줄 총평과 위트 있는 사담, 그리고 반드시 "끗"으로 끝낼 것.
"""

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

# 5. HTML 미리보기 파일 생성
chart_img_html = f'<img src="{chart_file}" alt="환율 차트">' if chart_file else ''

html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>오늘의 블로그 포스팅 초안</title>
    <style>
        body {{ font-family: 'Apple SD Gothic Neo', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; color: #333; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .content {{ white-space: pre-wrap; background: #f9f9f9; padding: 20px; border-radius: 8px; font-size: 16px; word-break: break-all; }}
        img {{ max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; border-radius: 4px; }}
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
