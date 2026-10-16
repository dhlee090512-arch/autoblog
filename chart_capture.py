import os
from playwright.sync_api import sync_playwright

CHART_DIR = "assets"
if not os.path.exists(CHART_DIR):
    os.makedirs(CHART_DIR)

def capture_tradingview_chart(tv_symbol, filename):
    """
    트레이딩뷰 주식/지수 심볼을 캡처합니다.
    """
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
    """
    트레이딩뷰 환율 차트(SGX:KRW1!)를 캡처합니다.
    """
    filepath = os.path.join(CHART_DIR, filename)
    url = "https://kr.tradingview.com/chart/?symbol=SGX%3AKRW1%21"
    
    print("[Playwright] 트레이딩뷰 환율 차트 캡처 중...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1200, "height": 800})
            page = context.new_page()
            
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000) # 차트 렌더링 대기
            
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
    """
    Finviz 섹터 맵을 캡처합니다.
    """
    filepath = os.path.join(CHART_DIR, filename)
    url = "https://finviz.com/map?t=sec"
    
    print("[Playwright] Finviz 섹터 맵 캡처 중...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()
            
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000) # 맵 로딩 대기
            
            page.screenshot(path=filepath, full_page=True)
            browser.close()
            
        print(f"[캡처 성공] Finviz 맵 저장 완료: {filepath}")
        return f"{CHART_DIR}/{filename}"
    except Exception as e:
        print(f"[캡처 오류] Finviz 맵 캡처 실패: {e}")
        return None
