import os
import re
import time
import requests
import pandas as pd
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
    print("[청소 완료] 기존 구버전 차트 이미지들을 모두 정리했습니다.")

GITHUB_PAGES_BASE_URL = "https://dhlee090512-arch.github.io/autoblog/assets"
current_timestamp = int(time.time()) # 캐시 방지용 타임스탬프

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

# 3. 대시보드 크롤링 및 종목 정보 동적 추출 함수
def fetch_dashboard_and_extract_stocks(kr_url, us_url):
    """
    국장 및 미장 대시보드 페이지에서 텍스트와 종목 정보를 동적으로 추출합니다.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 국장 대시보드
    res_kr = requests.get(kr_url, headers=headers)
    res_kr.raise_for_status()
    soup_kr = BeautifulSoup(res_kr.text, 'html.parser')
    kr_raw_text = soup_kr.get_text(separator="\n", strip=True)
    
    # 미장 대시보드
    res_us = requests.get(us_url, headers=headers)
    res_us.raise_for_status()
    soup_us = BeautifulSoup(res_us.text, 'html.parser')
    us_raw_text = soup_us.get_text(separator="\n", strip=True)
    
    extracted_stocks = {}

    # HTML 태그 요소나 패턴 기반 종목 추출 (예: '종목명(코드)' 또는 테이블/카드 영역)
    # 1) 국장 6자리 숫 티커 패턴 추출
    kr_matches = re.findall(r'([가-힣A-Za-z0-9\s]+)[\s\(\[\{]*(\d{6})[\)\]\}]*', kr_raw_text)
    for name, code in kr_matches:
        clean_name = name.strip()
        if len(clean_name) > 1 and clean_name not in ["코스피", "코스닥"]:
            safe_fname = f"chart_{code}.png"
            extracted_stocks[clean_name] = (f"KRX:{code}", safe_fname, f"KRX-{code}")

    # 2) 미장 티커 패턴 추출 (대문자 알파벳 2~5자리)
    us_matches = re.findall(r'([가-힣A-Za-z0-9\s]+)[\s\(\[\{]+([A-Z]{2,5})[\)\]\}]+', us_raw_text)
    for name, ticker in us_matches:
        clean_name = name.strip()
        if len(clean_name) > 1 and clean_name not in ["USD", "KRW", "NYSE", "NASDAQ", "INDEX"]:
            safe_fname = f"chart_{ticker}.png"
            extracted_stocks[clean_name] = (f"NASDAQ:{ticker}", safe_fname, f"NASDAQ-{ticker}")

    print(f"[동적 종목 추출] 총 {len(extracted_stocks)}개 종목 파싱 완료: {list(extracted_stocks.keys())}")
    return kr_raw_text, us_raw_text, extracted_stocks

print("국장 및 미장 대시보드 데이터 수집 및 종목 동적 추출 중...")
kr_url = "https://dhlee090512-arch.github.io/report/index.html"
us_url = "https://dhlee090512-arch.github.io/report/us_index.html"

kr_raw, us_raw, dynamic_stocks = fetch_dashboard_and_extract_stocks(kr_url, us_url)

# 4. 동적으로 파싱된 종목들의 차트 캡처 수행
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

# 거시경제용 환율 차트 및 Finviz 맵 사전 캡처
fx_path = capture_fx_tradingview("usdkrw_chart.png")
finviz_path = capture_finviz_map("finviz_map.png")

# 5. Gemini API 호출 (폴백 모델 적용)
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

# 6. 제목 및 본문 파싱
post_title = "오늘의 경제 주요 흐름 및 특징주 분석"
body_text = raw_blog_text

lines = raw_blog_text.strip().split("\n")
for line in lines:
    if line.startswith("[제목]") or line.startswith("제목:"):
        post_title = re.sub(r"^\[제목\]\s*|^제목:\s*", "", line).strip()
        body_text = "\n".join([l for l in lines if l != line]).strip()
        break

formatted_body = body_text

# 7. [경제 이슈] 요청한 규격 구조 적용
if "[경제 이슈]" in formatted_body:
    fx_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/usdkrw_chart.png?t={current_timestamp}" alt="환율 차트"></div>' if fx_path else ""
    finviz_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/finviz_map.png?t={current_timestamp}" alt="Finviz 섹터 맵"></div>' if finviz_path else ""
    
    replacement_content = (
        "[경제 이슈]\n\n"
        "원화 M2 통화량) https://tradingeconomics.com/south-korea/money-supply-m2\n"
        "한국 경기선행지수 ) https://tradingeconomics.com/south-korea/leading-economic-index\n"
        "달러 M2 통화량) https://tradingeconomics.com/united-states/money-supply-m2\n"
        "미국 경기선행지수 ) https://tradingeconomics.com/united-states/leading-economic-index\n\n"
        "통화량과 경기선행지수는 위 사이트에서 확인 가능합니다. 꾸준히 우상향 추세인 것을 확인할 수 있습니다.\n\n"
        "원 달러 환율)\n"
        f"{fx_html}\n"
        "원 달러 환율은 현재 최근 n년 중 거의 최저 수준을 기록하고 있습니다.\n\n"
        f"{finviz_html}\n"
        "전반적인 테마 흐름을 확인하면 기술주들은 약세를 보이고 전통적인 소비재나 경기방어주들이 강세를 보이는 것을 확인할 수 있습니다.\n\n"
        "위 내용을 바탕으로 거시경제 상황을 정리하자면 국내 원화 통화량이나 경기선행지수는 꾸준히 우상향하고 있지만, 전반적인 시장 분위기는 단단하지 못한 모습입니다. 특히 미장 쪽은 인플레이션 우려가 다시 고개를 들고 있고, 월별 옵션 만기일 같은 파생상품 이슈까지 겹치면서 대형 기술주들이 조정을 세게 맞았거든요. 연준의 금리 인하 속도에 대한 불확실성도 커져서 투자심리가 살짝 위축된 상태입니다.\n\n"
        "이럴 때에는 무지성으로 추격 매수하기보다는 차트에서 바닥을 잘 다지거나 지지 라인을 지켜주는 종목 위주로 짧게 스윙 접근하는 게 유리한 것 같아요. 변동성이 워낙 크니까 위아래로 먹으려다가 쳐발리기보다는 손절가 잡고 철저하게 대응하는 트레이딩 관점이 안전할 것으로 보입니다."
    )
    formatted_body = formatted_body.replace("[경제 이슈]", replacement_content)

# 8. 동적으로 매칭된 종목 차트 및 트레이딩뷰 URL을 본문에 매칭 인라인 삽입
for stock_name, info in generated_charts_map.items():
    if stock_name in formatted_body:
        filename_only = os.path.basename(info["path"])
        link_text = f"\n{info['tv_url']}\n"
        stock_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{filename_only}?t={current_timestamp}" alt="{stock_name} 차트"></div>'
        
        pattern = rf"([^\n]*{stock_name}[^\n]*\n)"
        if re.search(pattern, formatted_body):
            formatted_body = re.sub(pattern, rf"\1{stock_html}{link_text}\n", formatted_body, count=1)
            print(f"[매칭 성공] 본문에 '{stock_name}' 차트 및 트레이딩뷰 URL 삽입 완료")

# 9. HTML 미리보기 파일 생성
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
