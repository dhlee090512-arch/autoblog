import os
import re
import time
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

from chart_capture import (
    capture_tradingview_chart,
    capture_fx_tradingview,
    capture_finviz_map
)

# 1. 차트 전용 폴더(assets) 관리 및 기존 파일 일괄 청소
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
    print("[청소 완료] 기존 구버전 차트 이미지들을 정리했습니다.")

GITHUB_PAGES_BASE_URL = "https://dhlee090512-arch.github.io/autoblog/assets"
current_timestamp = int(time.time()) # 캐시 방지용 타임스탬프

# 2. API 클라이언트 초기화
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

def load_prompt(filename="prompt.txt"):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"{filename} 파일을 찾을 수 없습니다.")
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

# 3. 대시보드 크롤링 및 종목 정보 동적 추출
def fetch_dashboard_and_extract_stocks(kr_url, us_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    EXCLUDE_KEYWORDS = {
        "코스피", "코스닥", "USD", "KRW", "NYSE", "NASDAQ", "INDEX",
        "S&P500", "나스닥", "다우존스", "환율", "변동성", "상승률", "하락률"
    }

    res_kr = requests.get(kr_url, headers=headers)
    res_kr.raise_for_status()
    soup_kr = BeautifulSoup(res_kr.text, 'html.parser')
    kr_raw_text = soup_kr.get_text(separator="\n", strip=True)

    res_us = requests.get(us_url, headers=headers)
    res_us.raise_for_status()
    soup_us = BeautifulSoup(res_us.text, 'html.parser')
    us_raw_text = soup_us.get_text(separator="\n", strip=True)

    extracted_stocks = {}

    # 국장 종목 (6자리 코드)
    kr_matches = re.findall(r'([가-힣A-Za-z0-9&]+)\s*[\(\[\{](\d{6})[\)\]\}]', kr_raw_text)
    for name, code in kr_matches:
        clean_name = name.strip()
        if clean_name not in EXCLUDE_KEYWORDS and len(clean_name) > 1:
            extracted_stocks[clean_name] = (f"KRX:{code}", f"chart_{code}.png", f"KRX-{code}")

    # 미장 종목 (2~5자리 티커)
    us_matches = re.findall(r'([가-힣A-Za-z0-9&]+)\s*[\(\[\{]([A-Z]{2,5})[\)\]\}]', us_raw_text)
    for name, ticker in us_matches:
        clean_name = name.strip()
        if clean_name not in EXCLUDE_KEYWORDS and len(clean_name) > 1:
            extracted_stocks[clean_name] = (f"NASDAQ:{ticker}", f"chart_{ticker}.png", f"NASDAQ-{ticker}")

    print(f"[동적 종목 추출] 총 {len(extracted_stocks)}개 파싱: {list(extracted_stocks.keys())}")
    return kr_raw_text, us_raw_text, extracted_stocks

kr_url = "https://dhlee090512-arch.github.io/report/index.html"
us_url = "https://dhlee090512-arch.github.io/report/us_index.html"

kr_raw, us_raw, dynamic_stocks = fetch_dashboard_and_extract_stocks(kr_url, us_url)

# 4. 차트 및 에셋 사전 캡처
generated_charts_map = {}
for stock_name, info in dynamic_stocks.items():
    tv_symbol, fname, tv_url_code = info
    res_path = capture_tradingview_chart(tv_symbol, fname)
    if res_path:
        tv_url = f"https://www.tradingview.com/symbols/{tv_url_code}/"
        generated_charts_map[stock_name] = {
            "path": res_path,
            "tv_url": tv_url
        }

fx_path = capture_fx_tradingview("usdkrw_chart.png")
finviz_path = capture_finviz_map("finviz_map.png")

# 5. Gemini API 호출
system_instruction = load_prompt("prompt.txt")
user_prompt = f"--- [국장 대시보드 Data] ---\n{kr_raw[:3500]}\n\n--- [미장 대시보드 Data] ---\n{us_raw[:3500]}"

models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
response = None

for model_name in models_to_try:
    print(f"[{model_name}] 호출 중...")
    try:
        response = client.models.generate_content(
            model=model_name, contents=user_prompt,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.75),
        )
        if response and response.text:
            break
    except Exception as e:
        print(f"호출 에러: {e}")

if not response:
    raise RuntimeError("Gemini API 호출에 실패했습니다.")

blog_text = response.text

# 6. 제목 및 본문 분리
post_title = "오늘의 경제 주요 흐름 및 특징주 분석"
lines = blog_text.strip().split("\n")
for line in lines:
    if line.startswith("[제목]") or line.startswith("제목:"):
        post_title = re.sub(r"^\[제목\]\s*|^제목:\s*", "", line).strip()
        blog_text = "\n".join([l for l in lines if l != line]).strip()
        break

formatted_body = blog_text

# 7. 플레이스홀더 치환 (사진 및 링크)

# (1) 환율 및 Finviz 플레이스홀더 치환
fx_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/usdkrw_chart.png?t={current_timestamp}" alt="환율 차트"></div>' if fx_path else ""
finviz_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/finviz_map.png?t={current_timestamp}" alt="Finviz 섹터 맵"></div>' if finviz_path else ""

formatted_body = re.sub(r'\(환율 사진\)', fx_html, formatted_body)
formatted_body = re.sub(r'\(finviz 사진\)', finviz_html, formatted_body)

# (2) 각 종목별 (종목 차트), (종목 트레이딩뷰 url) 플레이스홀더 치환
for stock_name, info in generated_charts_map.items():
    if stock_name in formatted_body:
        filename_only = os.path.basename(info["path"])
        stock_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{filename_only}?t={current_timestamp}" alt="{stock_name} 차트"></div>'
        tv_url_text = info["tv_url"]

        # 종목 섹션 블록을 찾아서 해당 플레이스홀더 치환
        # 종목명 뒤 나오는 첫 번째 (종목 차트)와 (종목 트레이딩뷰 url) 변경
        pattern = rf"({re.escape(stock_name)}[\s\S]*?)(?=\n\n\d+\.|\n\n\[|$)"
        def replace_stock_placeholders(match):
            block = match.group(1)
            block = re.sub(r'\(종목 차트\)', stock_html, block, count=1)
            block = re.sub(r'\(종목 트레이딩뷰 url\)', tv_url_text, block, count=1)
            return block

        formatted_body = re.sub(pattern, replace_stock_placeholders, formatted_body, count=1)

# 만약 Gemini가 플레이스홀더를 안 적고 누락했을 경우를 대비한 안전 치환 (종목명 바로 아래에 치환)
for stock_name, info in generated_charts_map.items():
    if stock_name in formatted_body and "(종목 차트)" not in formatted_body:
        filename_only = os.path.basename(info["path"])
        stock_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{filename_only}?t={current_timestamp}" alt="{stock_name} 차트"></div>'
        tv_url_text = info["tv_url"]
        
        # 종목 제목 바로 뒤에 이미지와 URL 삽입
        pattern = rf"([^\n]*{re.escape(stock_name)}[^\n]*\n)"
        formatted_body = re.sub(pattern, rf"\1{stock_html}\n{tv_url_text}\n", formatted_body, count=1)

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

print("blog_preview.html 생성 완료!")
