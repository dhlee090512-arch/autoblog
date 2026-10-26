import os
import re
import time
import json
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
from PIL import Image  # 환율 및 Finviz 이미지를 Gemini에 전달하기 위한 라이브러리
from google import genai
from google.genai import types

from chart_capture import (
    capture_tradingview_chart,
    capture_fx_tradingview,
    capture_finviz_map
)

# 1. assets 폴더 초기화 (이전 잔여 이미지 완전 청소)
CHART_DIR = "assets"
if not os.path.exists(CHART_DIR):
    os.makedirs(CHART_DIR)
else:
    for f in os.listdir(CHART_DIR):
        file_path = os.path.join(CHART_DIR, f)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                print(f"[삭제 완료] 이전 잔여 파일 제거: {f}")
            except Exception as e:
                print(f"[삭제 실패 무시] {f}: {e}")

current_timestamp = int(time.time())

# 한국 시간(KST, UTC+9) 구하기
kst = timezone(timedelta(hours=9))
formatted_kst_time = datetime.now(kst).strftime("%Y년 %m월 %d일 %H:%M:%S (KST)")

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

# 3. 종목 히스토리 관리 (최근 5일간 다룬 종목 기록)
HISTORY_FILE = "stock_history.json"

def load_stock_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_stock_history(today_stocks):
    history = load_stock_history()
    today_str = datetime.now(kst).strftime("%Y-%m-%d")
    
    history = [h for h in history if h["date"] != today_str]
    history.append({"date": today_str, "stocks": today_stocks})
    history = history[-5:] # 최근 5일치만 유지
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# 최근 다뤘던 종목들 로드 및 블랙리스트 문자열 생성
history_data = load_stock_history()
recent_excluded_stocks = []
for h in history_data:
    recent_excluded_stocks.extend(h["stocks"])
recent_excluded_str = ", ".join(set(recent_excluded_stocks)) if recent_excluded_stocks else "없음"
print(f"[종목 중복 방지 블랙리스트] 최근 다룬 종목들: {recent_excluded_str}")

# 4. 대시보드 크롤링 및 종목 동적 추출
def fetch_dashboard_and_extract_stocks(kr_url, us_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    
    EXCLUDE_KEYWORDS = {
        "코스피", "코스닥", "USD", "KRW", "NYSE", "NASDAQ", "INDEX",
        "S&P500", "나스닥", "다우존스", "환율", "변동성", "상승률", "하락률",
        "CPI", "CLI", "POC", "PPI", "FOMC", "FED", "GDP", "PCE", "ECB", "BOJ",
        "DXY", "VIX", "WTI", "BRENT", "GOLD", "US10Y", "US02Y"
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
            extracted_stocks[clean_name] = {
                "tv_symbol": f"KRX:{code}",
                "filename": f"chart_{code}.png",
                "tv_url_code": f"KRX-{code}",
                "aliases": [clean_name.lower(), code.lower()]
            }

    # 미장 종목
    us_matches = re.findall(r'([가-힣A-Za-z0-9&\s,.]+)\s*[\(\[\{]([A-Z]{2,5})[\)\]\}]', us_raw_text)
    for name, ticker in us_matches:
        clean_name = name.strip()
        base_name = re.sub(r',?\s*(Inc\.?|Corp\.?|Co\.?|Ltd\.?)$', '', clean_name, flags=re.IGNORECASE).strip()
        extracted_stocks[clean_name] = {
            "tv_symbol": f"NASDAQ:{ticker}",
            "filename": f"chart_{ticker}.png",
            "tv_url_code": f"NASDAQ-{ticker}",
            "aliases": [
                clean_name.lower(),
                base_name.lower(),
                ticker.lower(),
                clean_name.replace(" ", "").lower(),
                base_name.replace(" ", "").lower()
            ]
        }

    print(f"[동적 종목 추출 완료] 총 {len(extracted_stocks)}개: {list(extracted_stocks.keys())}")
    return kr_raw_text, us_raw_text, extracted_stocks

kr_url = "https://dhlee090512-arch.github.io/report/index.html"
us_url = "https://dhlee090512-arch.github.io/report/us_index.html"

kr_raw, us_raw, dynamic_stocks = fetch_dashboard_and_extract_stocks(kr_url, us_url)

# 5. 차트 및 에셋 사전 캡처
generated_charts_map = {}
for stock_key, info in dynamic_stocks.items():
    res_path = capture_tradingview_chart(info["tv_symbol"], info["filename"])
    if res_path:
        tv_url = f"https://www.tradingview.com/symbols/{info['tv_url_code']}/"
        generated_charts_map[stock_key] = {
            "path": res_path,
            "tv_url": tv_url,
            "aliases": info["aliases"]
        }

fx_path = capture_fx_tradingview("usdkrw_chart.png")
finviz_path = capture_finviz_map("finviz_map.png")

# 6. Gemini API 호출 (강력한 종목 블랙리스트 규칙 및 멀티모달 이미지 페이로드 구성)
system_instruction = load_prompt("prompt.txt")
user_prompt = f"""
--- [🚨 절대 준수해야 할 종목 선정 규칙] ---
1. 아래 **[선정 금지 종목 리스트]**에 있는 종목들은 **최근 5일 동안 이미 다뤘던 종목들**입니다. 이번 포스팅에서는 **이 종목들을 절대로 다시 선정하면 안 됩니다.**
2. 반드시 국장/미장 대시보드 데이터에 있는 위 리스트에 없는 완전히 새로운 종목들 중에서 특징주를 골라주세요.

- 🚫 **선정 금지 종목 리스트**: [{recent_excluded_str}]

--- [국장 대시보드 Data] ---
{kr_raw[:3500]}

--- [미장 대시보드 Data] ---
{us_raw[:3500]}

첨부된 [환율 차트 이미지]와 [Finviz 섹터 맵 이미지]를 직접 분석하여, 환율의 실제 움직임 추세와 업종별/테마별 강세·약세를 본문에 구체적으로 반영해 주세요.
"""

contents_payload = [user_prompt]

# 환율 이미지 첨부
if fx_path and os.path.exists(fx_path):
    try:
        fx_img = Image.open(fx_path)
        contents_payload.append(fx_img)
        print("[Gemini] 환율 차트 이미지 멀티모달 입력 준비 완료")
    except Exception as e:
        print(f"[경고] 환율 이미지 로드 실패: {e}")

# Finviz 맵 이미지 첨부
if finviz_path and os.path.exists(finviz_path):
    try:
        finviz_img = Image.open(finviz_path)
        contents_payload.append(finviz_img)
        print("[Gemini] Finviz 맵 이미지 멀티모달 입력 준비 완료")
    except Exception as e:
        print(f"[경고] Finviz 이미지 로드 실패: {e}")

models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
response = None

for model_name in models_to_try:
    print(f"[{model_name}] 호출 중...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents_payload,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.75
            ),
        )
        if response and response.text:
            break
    except Exception as e:
        print(f"호출 에러: {e}")

if not response:
    raise RuntimeError("Gemini API 호출에 실패했습니다.")

blog_text = response.text

# 7. 제목 및 본문 분리
post_title = "오늘의 경제 주요 흐름 및 특징주 분석"
lines = blog_text.strip().split("\n")
for line in lines:
    if line.startswith("[제목]") or line.startswith("제목:"):
        post_title = re.sub(r"^\[제목\]\s*|^제목:\s*", "", line).strip()
        blog_text = "\n".join([l for l in lines if l != line]).strip()
        break

formatted_body = blog_text

# 8. 이미지 HTML 상대 경로(`assets/...`) 적용 및 주입
fx_html = f'<div class="img-box"><img src="assets/usdkrw_chart.png?t={current_timestamp}" alt="환율 차트"></div>' if fx_path else ""
finviz_html = f'<div class="img-box"><img src="assets/finviz_map.png?t={current_timestamp}" alt="Finviz 섹터 맵"></div>' if finviz_path else ""

if "[경제 이슈]" in formatted_body:
    formatted_body = re.sub(r'\(환율\s*사진\)', fx_html, formatted_body, flags=re.IGNORECASE)
    formatted_body = re.sub(r'\(finviz\s*사진\)', finviz_html, formatted_body, flags=re.IGNORECASE)

    if fx_html and fx_html not in formatted_body:
        if "우상향 추세입니다" in formatted_body:
            formatted_body = re.sub(r'([^\n]*우상향 추세입니다[^\n]*\n)', rf'\1\n{fx_html}\n', formatted_body, count=1)
        elif "환율" in formatted_body:
            formatted_body = re.sub(r'([^\n]*환율[^\n]*\n)', rf'{fx_html}\n\1', formatted_body, count=1)

    if finviz_html and finviz_html not in formatted_body:
        if "전반적인 테마" in formatted_body:
            formatted_body = re.sub(r'([^\n]*전반적인 테마[^\n]*\n)', rf'{finviz_html}\n\1', formatted_body, count=1)
        elif "기술주" in formatted_body:
            formatted_body = re.sub(r'([^\n]*기술주[^\n]*\n)', rf'{finviz_html}\n\1', formatted_body, count=1)

# 9. [특징주 분석] 소제목 블록 단위 격리 치환 및 오늘 다룬 종목 추출
today_selected_stocks = []

if "[특징주 분석]" in formatted_body:
    main_parts = formatted_body.split("[특징주 분석]")
    intro_text = main_parts[0]
    feature_text = "[특징주 분석]" + main_parts[1]
    
    feature_lines = feature_text.split("\n")
    heading_indices = []
    for idx, line in enumerate(feature_lines):
        if re.match(r'^\d+\.\s+', line.strip()):
            heading_indices.append(idx)
            
    new_feature_blocks = []
    if heading_indices:
        new_feature_blocks.append("\n".join(feature_lines[:heading_indices[0]]))
        
        for i in range(len(heading_indices)):
            start_idx = heading_indices[i]
            end_idx = heading_indices[i+1] if i + 1 < len(heading_indices) else len(feature_lines)
            
            block_lines = feature_lines[start_idx:end_idx]
            block_text = "\n".join(block_lines)
            
            heading_line = block_lines[0].strip()
            stock_name_raw = re.sub(r'^\d+\.\s+', '', heading_line).strip()
            
            for stock_key in dynamic_stocks.keys():
                if stock_key.lower() in stock_name_raw.lower() or stock_name_raw.lower() in stock_key.lower():
                    if stock_key not in today_selected_stocks:
                        today_selected_stocks.append(stock_key)
            
            search_term = stock_name_raw.lower()
            clean_search = re.sub(r',?\s*(Inc\.?|Corp\.?|Co\.?|Ltd\.?)$', '', search_term).strip()
            
            matched_info = None
            for stock_key, info in generated_charts_map.items():
                sk_lower = stock_key.lower()
                if sk_lower in clean_search or clean_search in sk_lower or clean_search in sk_lower.replace(" ", ""):
                    matched_info = info
                    break
                for alias in info["aliases"]:
                    if alias in clean_search or clean_search in alias:
                        matched_info = info
                        break
                if matched_info:
                    break
            
            if matched_info:
                filename_only = os.path.basename(matched_info["path"])
                stock_html = f'<div class="img-box"><img src="assets/{filename_only}?t={current_timestamp}" alt="{stock_name_raw} 차트"></div>'
                tv_url_text = matched_info["tv_url"]
                
                block_text = block_text.replace("(종목 차트)", stock_html)
                block_text = block_text.replace("(종목 트레이딩뷰 url)", tv_url_text)
            
            new_feature_blocks.append(block_text)
            
        feature_text = "\n".join(new_feature_blocks)
        formatted_body = intro_text + feature_text

# 히스토리 저장
save_stock_history(today_selected_stocks)
print(f"[종목 히스토리 저장 완료] 오늘 다룬 종목: {today_selected_stocks}")

# 10. HTML 미리보기 파일 생성
html_body_formatted = formatted_body.replace("\n", "<br>")
json_safe_clipboard_text = json.dumps(formatted_body)

html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>{post_title}</title>
    <style>
        body {{ font-family: 'Apple SD Gothic Neo', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.7; color: #333; }}
        .timestamp-badge {{ background: #f1f3f5; color: #495057; font-size: 13px; padding: 6px 12px; border-radius: 20px; display: inline-block; margin-bottom: 15px; font-weight: bold; border: 1px solid #dee2e6; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; font-size: 24px; margin-top: 10px; }}
        .title-box {{ background: #eef5ff; border-left: 5px solid #2b7de9; padding: 15px; margin-bottom: 25px; border-radius: 4px; font-size: 18px; font-weight: bold; color: #1a498b; }}
        .content-container {{ position: relative; }}
        .copy-btn {{ position: absolute; top: 15px; right: 15px; background: #2b7de9; color: white; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: background 0.2s; }}
        .copy-btn:hover {{ background: #1a5bb8; }}
        .content {{ background: #fafafa; padding: 25px; padding-top: 55px; border-radius: 8px; font-size: 16px; word-break: break-all; border: 1px solid #eee; }}
        .img-box {{ margin: 25px 0; text-align: center; }}
        img {{ max-width: 100%; height: auto; border: 1px solid #e1e4e8; border-radius: 6px; display: block; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    </style>
</head>
<body>
    <div class="timestamp-badge">⏱️ 업데이트 시각: {formatted_kst_time}</div>
    <h1>📊 자동 생성 블로그 포스팅 미리보기</h1>
    <p>우측 상단의 <b>[본문 복사]</b> 버튼을 누른 뒤 블로그 에디터에 붙여넣으세요!</p>
    <hr>
    
    <h3>📌 포스팅 제목</h3>
    <div class="title-box">{post_title}</div>

    <h3>📝 본문 텍스트 (차트 및 거시경제 링크 포함)</h3>
    <div class="content-container">
        <button class="copy-btn" onclick="copyContent()">📋 본문 복사</button>
        <div class="content" id="blog-content">{html_body_formatted}</div>
    </div>

    <script>
        function copyContent() {{
            const textToCopy = {json_safe_clipboard_text};
            navigator.clipboard.writeText(textToCopy).then(() => {{
                const btn = document.querySelector('.copy-btn');
                btn.innerText = '✅ 복사 완료!';
                btn.style.background = '#2b8a3e';
                setTimeout(() => {{
                    btn.innerText = '📋 본문 복사';
                    btn.style.background = '#2b7de9';
                }}, 2000);
            }}).catch(err => {{
                alert('복사 실패: ' + err);
            }});
        }}
    </script>
</body>
</html>
"""

with open("blog_preview.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("blog_preview.html 생성 완료!")
