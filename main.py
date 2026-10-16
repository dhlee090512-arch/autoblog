import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# 캡처 모듈 임포트
from chart_capture import (
    capture_tradingview_chart,
    capture_fx_tradingview,
    capture_finviz_map
)

# 1. 차트 전용 폴더(assets) 관리 및 초기화
CHART_DIR = "assets"
if not os.path.exists(CHART_DIR):
    os.makedirs(CHART_DIR)
else:
    for f in os.listdir(CHART_DIR):
        if f.endswith(".png"):
            try:
                os.remove(os.path.join(CHART_DIR, f))
            except Exception as e:
                print(f"[파일 삭제 오류 무시] {f}: {e}")
    print("[청소 완료] 기존 구버전 차트 이미지들을 모두 정리했습니다.")

GITHUB_PAGES_BASE_URL = "https://dhlee090512-arch.github.io/autoblog/assets"

# 2. 환경변수 및 API 클라이언트 초기화
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

def load_prompt(filename="prompt.txt"):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"{filename} 파일을 찾을 수 없습니다.")
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

# 5. 대시보드 데이터 수집
def fetch_dashboard_data(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.get_text(separator="\n", strip=True)

print("국장 및 미장 대시보드 데이터 수집 중...")
kr_raw = fetch_dashboard_data("https://dhlee090512-arch.github.io/report/index.html")
us_raw = fetch_dashboard_data("https://dhlee090512-arch.github.io/report/us_index.html")

# 6. [선행 작업] 주요 모니터링 대상 종목
predefined_stocks = {
    "셀트리온": ("KRX:068270", "celtrion_chart.png", "068270"),
    "LG에너지솔루션": ("KRX:373220", "lg_energy_chart.png", "373220"),
    "Bank of America": ("NYSE:BAC", "bac_chart.png", "BAC"),
    "NVIDIA": ("NASDAQ:NVDA", "nvidia_chart.png", "NVDA"),
    "Tesla": ("NASDAQ:TSLA", "tesla_chart.png", "TSLA"),
    "두산에너빌리티": ("KRX:034020", "doosan_chart.png", "034020")
}

generated_charts_map = {}
for stock_name, info in predefined_stocks.items():
    tv_symbol, fname, naver_code = info
    res_path = capture_tradingview_chart(tv_symbol, fname)
    if res_path:
        naver_url = f"https://finance.naver.com/item/main.naver?code={naver_code}" if not naver_code.isalpha() else f"https://finance.naver.com/us/main.nhn?code={naver_code}"
        generated_charts_map[stock_name] = {
            "path": res_path,
            "naver_url": naver_url
        }

# 경제 이슈용 환율 차트 및 Finviz 맵 사전 캡처
fx_path = capture_fx_tradingview("usdkrw_chart.png")
finviz_path = capture_finviz_map("finviz_map.png")

# 7. Gemini API 호출 (폴백 모델 적용)
system_instruction = load_prompt("prompt.txt")
user_prompt = f"--- [국장 대시보드 Data] ---\n{kr_raw[:3500]}\n\n--- [미장 대시보드 Data] ---\n{us_raw[:3500]}"

models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
response = None

for model_name in models_to_try:
    print(f"[{model_name}] 모델로 시도 시작...")
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Gemini API 호출 중 ({model_name} - 시도 {attempt}/{max_retries})...")
            response = client.models.generate_content(
                model=model_name, contents=user_prompt,
                config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.75),
            )
            print(f"[{model_name}] 호출 성공!")
            break
        except Exception as e:
            print(f"API 호출 실패 (에러: {e})")
            if attempt < max_retries:
                time.sleep(attempt * 15)
            else:
                print(f"[{model_name}] 최대 재시도 초과. 백업 모델로 전환합니다.")
    if response:
        break

if not response:
    raise RuntimeError("모든 Gemini 모델 및 재시도가 실패했습니다.")

raw_blog_text = response.text

# 8. 제목 및 본문 파싱
post_title = "오늘의 경제 주요 흐름 및 특징주 분석"
body_text = raw_blog_text

lines = raw_blog_text.strip().split("\n")
for line in lines:
    if line.startswith("[제목]") or line.startswith("제목:"):
        post_title = re.sub(r"^\[제목\]\s*|^제목:\s*", "", line).strip()
        body_text = "\n".join([l for l in lines if l != line]).strip()
        break

formatted_body = body_text

# 9. [경제 이슈] 아래에 M2, 경기선행지수 링크, 환율 차트 및 Finviz 맵 인라인 삽입
if "[경제 이슈]" in formatted_body:
    macro_links = (
        "원화 M2 통화량) https://tradingeconomics.com/south-korea/money-supply-m2\n"
        "한국 경기선행지수 ) https://tradingeconomics.com/south-korea/leading-economic-index\n"
        "달러 M2 통화량) https://tradingeconomics.com/united-states/money-supply-m2\n"
        "미국 경기선행지수 ) https://tradingeconomics.com/united-states/leading-economic-index\n"
    )
    
    fx_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/usdkrw_chart.png" alt="환율 차트"></div>' if fx_path else ""
    finviz_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/finviz_map.png" alt="Finviz 섹터 맵"></div>' if finviz_path else ""
    
    replacement_content = f"[경제 이슈]\n{macro_links}\n{fx_html}\n{finviz_html}"
    formatted_body = formatted_body.replace("[경제 이슈]", replacement_content)

# 10. 사전에 생성된 종목 차트들과 네이버 증권 링크 URL을 본문 속 키워드 위치에 매칭하여 인라인 삽입
for stock_name, info in generated_charts_map.items():
    if stock_name in formatted_body:
        filename_only = os.path.basename(info["path"])
        link_text = f"\n👉 네이버 증권 링크: {info['naver_url']}\n"
        stock_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{filename_only}" alt="{stock_name} 차트"></div>'
        
        pattern = rf"([^\n]*{stock_name}[^\n]*\n)"
        if re.search(pattern, formatted_body):
            formatted_body = re.sub(pattern, rf"\1{stock_html}{link_text}\n", formatted_body, count=1)
            print(f"[매칭 성공] 본문에 '{stock_name}' 차트 및 네이버 증권 URL 삽입 완료")

# 11. HTML 미리보기 파일 생성
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
        .img-box {{ margin: 25px 0; text-align: center; }}
        img {{ max-width: 100%; height: auto; border: 1px solid #e1e4e8; border-radius: 6px; display: block; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    </style>
</head>
<body>
    <h1>📊 자동 생성 블로그 포스팅 미리보기</h1>
    <p>아래 제목과 본문을 드래그해서 그대로 블로그에 붙여넣으세요.</p>
    <hr>
    
    <h3>📌 포스팅 제목</h3>
    <div class="title-box">{post_title}</div>

    <h3>📝 본문 텍스트 (차트 및 거시경제 링크 포함)</h3>
    <div class="content">{formatted_body}</div>
</body>
</html>
"""

with open("blog_preview.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("blog_preview.html 파일 생성 완료!")
