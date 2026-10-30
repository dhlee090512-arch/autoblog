import os
import re
import time
import json
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup
from PIL import Image
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
current_dt = datetime.now(kst)
formatted_kst_time = current_dt.strftime("%Y년 %m월 %d일 %H:%M:%S (KST)")

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

# 3. 종목 히스토리 관리 (순수 티커/코드 중심으로 관리 및 오염 방지)
HISTORY_FILE = "stock_history.json"

def load_stock_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                cleaned_history = []
                for h in history:
                    # 10자 이내의 순수 티커/코드만 유효 데이터로 인정
                    valid_codes = [c for c in h.get("stocks", []) if len(c.strip()) < 10]
                    cleaned_history.append({"date": h["date"], "stocks": valid_codes})
                return cleaned_history
        except:
            return []
    return []

def save_stock_history(today_codes):
    history = load_stock_history()
    today_str = current_dt.strftime("%Y-%m-%d")
    
    history = [h for h in history if h["date"] != today_str]
    valid_today_codes = [c for c in today_codes if len(c.strip()) < 10]
    history.append({"date": today_str, "stocks": valid_today_codes})
    history = history[-5:] # 최근 5일치만 유지
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# 최근 다뤘던 티커/코드 불러오기
history_data = load_stock_history()
recent_excluded_codes = []
for h in history_data:
    recent_excluded_codes.extend(h.get("stocks", []))
recent_excluded_codes = list(set(recent_excluded_codes))
print(f"[종목 중복 방지] 최근 다뤘던 티커/코드 목록: {recent_excluded_codes if recent_excluded_codes else '없음'}")

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

    kr_matches = re.findall(r'([가-힣A-Za-z0-9&]+)\s*[\(\[\{](\d{6})[\)\]\}]', kr_raw_text)
    for name, code in kr_matches:
        clean_name = name.strip()
        if clean_name not in EXCLUDE_KEYWORDS and len(clean_name) > 1:
            key_id = f"KRX:{code}"
            extracted_stocks[key_id] = {
                "display_name": clean_name,
                "tv_symbol": key_id,
                "filename": f"chart_{code}.png",
                "tv_url_code": f"KRX-{code}",
                "code": code
            }

    us_matches = re.findall(r'([가-힣A-Za-z0-9&\s,.]+)\s*[\(\[\{]([A-Z]{2,5})[\)\]\}]', us_raw_text)
    for name, ticker in us_matches:
        clean_name = name.strip()
        if len(clean_name) > 30:
            continue
        key_id = f"NASDAQ:{ticker}"
        extracted_stocks[key_id] = {
            "display_name": clean_name,
            "tv_symbol": key_id,
            "filename": f"chart_{ticker}.png",
            "tv_url_code": f"NASDAQ-{ticker}",
            "code": ticker
        }

    print(f"[동적 종목 추출 완료] 총 {len(extracted_stocks)}개 연동됨")
    return kr_raw_text, us_raw_text, extracted_stocks

kr_url = "https://dhlee090512-arch.github.io/report/index.html"
us_url = "https://dhlee090512-arch.github.io/report/us_index.html"

kr_raw, us_raw, dynamic_stocks = fetch_dashboard_and_extract_stocks(kr_url, us_url)

# 5. 최근 다뤘던 티커/코드를 기준으로 대시보드 텍스트 원천 필터링
filtered_kr_raw = kr_raw
filtered_us_raw = us_raw

for code in recent_excluded_codes:
    if len(code.strip()) > 1:
        filtered_kr_raw = re.sub(rf'.*{re.escape(code)}.*', '', filtered_kr_raw, flags=re.IGNORECASE)
        filtered_us_raw = re.sub(rf'.*{re.escape(code)}.*', '', filtered_us_raw, flags=re.IGNORECASE)

print(f"[중복 방지] 대시보드 텍스트에서 최근 티커/코드 필터링 완료")

# 6. 미리보기/차트 사전 캡처
generated_charts_map = {}
for key_id, info in dynamic_stocks.items():
    res_path = capture_tradingview_chart(info["tv_symbol"], info["filename"])
    if res_path:
        tv_url = f"https://www.tradingview.com/symbols/{info['tv_url_code']}/"
        map_key = info["code"].upper()
        chart_data = {
            "path": res_path,
            "tv_url": tv_url,
            "display_name": info["display_name"]
        }
        generated_charts_map[map_key] = chart_data
        if ":" in info["tv_symbol"]:
            ticker_only = info["tv_symbol"].split(":")[1].upper()
            generated_charts_map[ticker_only] = chart_data

fx_path = capture_fx_tradingview("usdkrw_chart.png")
finviz_path = capture_finviz_map("finviz_map.png")

# 7. Gemini API 호출
system_instruction = load_prompt("prompt.txt")
user_prompt = f"""
--- [🚨 절대 준수해야 할 종목 선정 규칙] ---
1. 아래 대시보드 데이터는 최근 다뤘던 티커/코드들이 완전히 필터링(삭제)되어 제거된 상태입니다.
2. 데이터에 남아있는 신선한 종목들 중에서 특징주를 **반드시 국장(한국 주식) 2개, 미장(미국 주식) 2개, 총 4개**를 골라주세요.
3. 특징주 분석 파트의 소제목은 반드시 다음과 같이 [번호. 종목명 (티커 또는 6자리 코드)] 형태로 작성해 주세요. 
   (예시: 1. 삼성전자 (005930), 2. 애플 (AAPL))

--- [국장 대시보드 Data (필터링됨)] ---
{filtered_kr_raw[:3500]}

--- [미장 대시보드 Data (필터링됨)] ---
{filtered_us_raw[:3500]}

첨부된 [환율 차트 이미지]와 [Finviz 섹터 맵 이미지]를 직접 분석하여, 환율의 실제 움직임 추세와 업종별/테마별 강세·약세를 본문에 구체적으로 반영해 주세요.
"""

contents_payload = [user_prompt]

if fx_path and os.path.exists(fx_path):
    try:
        contents_payload.append(Image.open(fx_path))
        print("[Gemini] 환율 차트 이미지 멀티모달 입력 준비 완료")
    except Exception as e:
        print(f"[경고] 환율 이미지 로드 실패: {e}")

if finviz_path and os.path.exists(finviz_path):
    try:
        contents_payload.append(Image.open(finviz_path))
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

# 8. 거시경제 이슈 파트 이미지 HTML 치환
fx_html = f'<div class="img-box"><img src="assets/usdkrw_chart.png?t={current_timestamp}" alt="환율 차트"></div>' if fx_path else ""
finviz_html = f'<div class="img-box"><img src="assets/finviz_map.png?t={current_timestamp}" alt="Finviz 섹터 맵"></div>' if finviz_path else ""

formatted_body = blog_text
if "[경제 이슈]" in formatted_body:
    formatted_body = re.sub(r'\(환율\s*사진\)', fx_html, formatted_body, flags=re.IGNORECASE)
    formatted_body = re.sub(r'\(finviz\s*사진\)', finviz_html, formatted_body, flags=re.IGNORECASE)

    if fx_html and fx_html not in formatted_body:
        formatted_body = re.sub(r'([^\n]*환율[^\n]*\n)', rf'{fx_html}\n\1', formatted_body, count=1)
    if finviz_html and finviz_html not in formatted_body:
        formatted_body = re.sub(r'([^\n]*기술주[^\n]*\n)', rf'{finviz_html}\n\1', formatted_body, count=1)

# 9. [특징주 분석] 티커/코드 기반 정밀 매칭 및 실시간 동적 캡처 방어 로직
today_selected_stock_names = []
today_selected_codes = []

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
            
            # 소제목 괄호 안의 티커 또는 국장 코드 추출
            code_match = re.search(r'\(([A-Z0-9]{2,6})\)', heading_line)
            extracted_code = code_match.group(1).upper() if code_match else None
            
            clean_name_match = re.sub(r'^\d+\.\s+', '', heading_line).strip()
            clean_display_name = re.sub(r'\s*[\(\[\{].*?[\)\]\}]', '', clean_name_match).strip()
            
            if clean_display_name:
                today_selected_stock_names.append(clean_display_name)
            if extracted_code:
                today_selected_codes.append(extracted_code)
            
            matched_info = generated_charts_map.get(extracted_code) if extracted_code else None
            
            # [방어 로직] 사전 캡처 목록에 없지만 티커가 감지된 경우 실시간 즉시 캡처 실행
            if not matched_info and extracted_code:
                print(f"[실시간 동적 캡처] 사전 목록에 없는 종목 발견: {clean_display_name} ({extracted_code}) -> 즉시 캡처 시도")
                if len(extracted_code) == 6 and extracted_code.isdigit():
                    tv_sym = f"KRX:{extracted_code}"
                    fname = f"chart_{extracted_code}.png"
                    t_url_code = f"KRX-{extracted_code}"
                else:
                    tv_sym = f"NASDAQ:{extracted_code}"
                    fname = f"chart_{extracted_code}.png"
                    t_url_code = f"NASDAQ-{extracted_code}"
                
                res_path = capture_tradingview_chart(tv_sym, fname)
                if res_path:
                    tv_url = f"https://www.tradingview.com/symbols/{t_url_code}/"
                    matched_info = {
                        "path": res_path,
                        "tv_url": tv_url,
                        "display_name": clean_display_name
                    }
                    generated_charts_map[extracted_code] = matched_info

            if matched_info:
                filename_only = os.path.basename(matched_info["path"])
                stock_html = f'<div class="img-box"><img src="assets/{filename_only}?t={current_timestamp}" alt="{clean_display_name} 차트"></div>'
                tv_url_text = matched_info["tv_url"]
                
                block_text = block_text.replace("(종목 차트)", stock_html)
                block_text = block_text.replace("(종목 트레이딩뷰 url)", tv_url_text)
                print(f"[매칭 성공] '{clean_display_name}' (코드: {extracted_code}) -> 차트 주입 완료")
            else:
                print(f"[매칭 경고] '{heading_line}'에서 유효한 티커/코드를 찾지 못했거나 캡처 매핑에 실패했습니다.")
            
            new_feature_blocks.append(block_text)
            
        feature_text = "\n".join(new_feature_blocks)
        formatted_body = intro_text + feature_text

# 10. 고정 양식 제목 강제 조립 ([월] [일] 경제 주요 흐름 및 특징주 분석 - [종목들])
current_month = current_dt.month
current_day = current_dt.day

if today_selected_stock_names:
    stocks_joined = ", ".join(today_selected_stock_names)
else:
    stocks_joined = "주요 특징주"

post_title = f"{current_month}월 {current_day}일 경제 주요 흐름 및 특징주 분석 - {stocks_joined}"
print(f"[TITLE 확정] {post_title}")

# 11. 히스토리에 순수 티커/코드만 저장
save_stock_history(today_selected_codes)
print(f"[종목 히스토리 저장 완료] 오늘 저장된 티커/코드: {today_selected_codes}")

# 12. HTML 미리보기 파일 생성
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
