import matplotlib
matplotlib.use('Agg') # 서버 환경용 설정
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

GITHUB_PAGES_BASE_URL = "https://dhlee090512-arch.github.io/autoblog"

# 1. 환경변수 및 API 클라이언트 초기화
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")

client = genai.Client(api_key=GEMINI_API_KEY)

def load_prompt(filename="prompt.txt"):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"{filename} 파일을 찾을 수 없습니다.")
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

# 2. 환율 전용 순수 라인 차트 (제목 제거 버전)
def generate_fx_line_chart(ticker_symbol="KRW=X", filename="usdkrw_chart.png"):
    try:
        print("환율 차트 데이터 다운로드 중...")
        df = yf.download(ticker_symbol, period="1y", interval="1d", progress=False)
        if df.empty:
            print("환율 데이터를 가져오지 못했습니다.")
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        
        if 'Close' in df.columns:
            close_data = pd.to_numeric(df['Close'], errors='coerce').dropna()
        else:
            return None

        plt.figure(figsize=(10, 5))
        plt.plot(close_data.index, close_data.values, color='#2b7de9', linewidth=2, label='USD/KRW')
        plt.fill_between(close_data.index, close_data.values, close_data.min() * 0.95, color='#2b7de9', alpha=0.1)
        
        # 제목 코드 완전 제거
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        plt.savefig(filename, dpi=150)
        plt.close()
        
        print(f"환율 라인 차트 생성 완료: {filename}")
        return filename
    except Exception as e:
        print(f"환율 차트 생성 오류: {e}")
        return None

# 3. 종목별 4단 프로 차트 (캔들 + 이평선 + 거래량 + RSI + MACD)
def generate_stock_pro_chart(ticker_symbol, title_prefix, filename):
    try:
        print(f"{ticker_symbol} 프로 차트 데이터 다운로드 중...")
        df = yf.download(ticker_symbol, period="3mo", interval="1d", progress=False)
        if df.empty:
            print(f"{ticker_symbol} 데이터를 가져오지 못했습니다.")
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()

        if df.empty or len(df) < 26:
            print(f"{ticker_symbol} 유효 데이터 부족.")
            return None

        # --- 보조지표 계산 (RSI, MACD) ---
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        # 스타일 정의
        mc = mpf.make_marketcolors(
            up='#e12343', down='#1763e0',
            edge='inherit', wick='inherit',
            volume={'up': '#e12343', 'down': '#1763e0'}
        )
        style = mpf.make_mpf_style(
            marketcolors=mc, gridstyle=':', gridcolor='#e6e8eb',
            facecolor='#ffffff', figcolor='#ffffff', y_on_right=True
        )

        addplots = [
            mpf.make_addplot(df['RSI'], panel=2, color='#8e44ad', ylabel='RSI', secondary_y=False),
            mpf.make_addplot([70]*len(df), panel=2, color='#e74c3c', linestyle='--', width=0.8),
            mpf.make_addplot([30]*len(df), panel=2, color='#2980b9', linestyle='--', width=0.8),
            
            mpf.make_addplot(df['MACD'], panel=3, color='#2980b9', ylabel='MACD', secondary_y=False),
            mpf.make_addplot(df['MACD_Signal'], panel=3, color='#e67e22', secondary_y=False),
            mpf.make_addplot(df['MACD_Hist'], panel=3, type='bar', color='#27ae60', secondary_y=False),
        ]

        mpf.plot(
            df, type='candle', mav=(5, 20, 60),
            volume=True, addplot=addplots,
            panel_ratios=(4, 1.5, 1.5, 1.5),
            title=f"\n{title_prefix} ({ticker_symbol})",
            style=style, savefig=filename,
            figratio=(12, 9), figscale=1.0
        )
        print(f"프로 차트 이미지 생성 완료: {filename}")
        return filename
    except Exception as e:
        print(f"{ticker_symbol} 프로 차트 생성 오류: {e}")
        return None

# 4. 대시보드 데이터 수집
def fetch_dashboard_data(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.get_text(separator="\n", strip=True)

print("국장 및 미장 대시보드 데이터 수집 중...")
kr_raw = fetch_dashboard_data("https://dhlee090512-arch.github.io/report/index.html")
us_raw = fetch_dashboard_data("https://dhlee090512-arch.github.io/report/us_index.html")

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

# 7. 환율 차트 생성 (제목 제거됨)
fx_chart = generate_fx_line_chart("KRW=X", "usdkrw_chart.png")

# 8. 본문 내 '종목명 (코드/티커)' 패턴을 정규식으로 동적 추출
# 예: 셀트리온 (068270), NVIDIA (NVDA)
pattern = r'([가-힣A-Za-z\s]+)\s*\(([0-9A-Za-z.]+)\)'
matches = re.findall(pattern, body_text)

formatted_body = body_text

# [경제 이슈] 아래에 환율 차트 삽입
if "[경제 이슈]" in formatted_body and fx_chart:
    fx_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{fx_chart}" alt="환율 차트"></div>'
    formatted_body = formatted_body.replace("[경제 이슈]", f"[경제 이슈]\n{fx_html}")

# 추출된 종목 코드를 백그라운드에서 yfinance 형식으로 변환 후 차트 생성 및 인라인 삽입
seen_codes = set()
for name, code in matches:
    clean_name = name.strip()
    if not clean_name or clean_name in ["제목", "경제 이슈", "특징주"]:
        continue
    
    if code in seen_codes:
        continue
    seen_codes.add(code)

    # 6자리 숫자인 경우 코스피(.KS) 기본 적용, 알파벳 티커는 그대로 사용
    if code.isdigit() and len(code) == 6:
        yf_ticker = f"{code}.KS"
    else:
        yf_ticker = code

    filename = f"stock_{code.lower()}_chart.png"
    chart_file = generate_stock_pro_chart(yf_ticker, clean_name, filename)

    if chart_file:
        stock_html = f'<div class="img-box"><img src="{GITHUB_PAGES_BASE_URL}/{filename}" alt="{clean_name} 차트"></div>'
        target_str = f"{name}({code})"
        if target_str in formatted_body:
            formatted_body = formatted_body.replace(target_str, f"{target_str}\n{stock_html}")
        else:
            # 띄어쓰기가 포함된 경우 대비
            target_str_space = f"{name} ({code})"
            if target_str_space in formatted_body:
                formatted_body = formatted_body.replace(target_str_space, f"{target_str_space}\n{stock_html}")

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

    <h3>📝 본문 텍스트 (차트 포함)</h3>
    <div class="content">{formatted_body}</div>
</body>
</html>
"""

with open("blog_preview.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("blog_preview.html 파일 생성 완료!")
