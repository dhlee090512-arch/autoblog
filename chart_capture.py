import os
from playwright.sync_api import sync_playwright

CHART_DIR = "assets"
if not os.path.exists(CHART_DIR):
    os.makedirs(CHART_DIR)

def capture_tradingview_chart(tv_symbol, filename):
    filepath = os.path.join(CHART_DIR, filename)
    url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"
    
    print(f"[Playwright] 트레이딩뷰 차트 캡처 중 ({tv_symbol})...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1200, "height": 800})
            page = context.new_page()
            
            page.goto(url, timeout=60000)
            page.wait_for_timeout(4000)
            
            chart_element = page.locator(".chart-container")
            if chart_element.count() > 0:
                chart_element.first.screenshot(path=filepath)
            else:
                page.screenshot(path=filepath, clip={"x": 0, "y": 50, "width": 1200, "height": 750})
                
            browser.close()
        print(f"[캡처 성공] 트레이딩뷰 차트 저장 완료: {filepath}")
        return f"{CHART_DIR}/{filename}"
    except Exception as e:
        print(f"[캡처 오류] {tv_symbol} 캡처 실패: {e}")
        return None

def capture_fx_tradingview(filename="usdkrw_chart.png"):
    filepath = os.path.join(CHART_DIR, filename)
    url = "https://kr.tradingview.com/chart/?symbol=FX_IDC%3AUSDKRW"
    
    print("[Playwright] 트레이딩뷰 환율 차트(USDKRW) 캡처 중...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1200, "height": 800})
            page = context.new_page()
            
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)
            
            chart_element = page.locator(".chart-container")
            if chart_element.count() > 0:
                chart_element.first.screenshot(path=filepath)
            else:
                page.screenshot(path=filepath, clip={"x": 0, "y": 50, "width": 1200, "height": 750})
                
            browser.close()
        print(f"[캡처 성공] 환율 차트 저장 완료: {filepath}")
        return f"{CHART_DIR}/{filename}"
    except Exception as e:
        print(f"[캡처 오류] 환율 차트 캡처 실패: {e}")
        return None

def capture_finviz_map(filename="finviz_map.png"):
    filepath = os.path.join(CHART_DIR, filename)
    url = "https://finviz.com/map?t=sec"
    
    print("[Playwright] Finviz 섹터 맵 보안 우회 캡처 중...")
    try:
        with sync_playwright() as p:
            # 자동화 탐지(Cloudflare 등) 우회를 위한 인자 설정
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1400,900"
                ]
            )
            
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York"
            )
            
            page = context.new_page()
            
            # webdriver 감지 우회 스크립트 주입
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page.goto(url, timeout=60000)
            page.wait_for_timeout(7000) # 보안 체크 및 맵 로딩 대기 시간 확보
            
            page.screenshot(path=filepath, full_page=True)
            browser.close()
            
        print(f"[캡처 성공] Finviz 맵 저장 완료: {filepath}")
        return f"{CHART_DIR}/{filename}"
    except Exception as e:
        print(f"[캡처 오류] Finviz 맵 캡처 실패: {e}")
        return None
