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
    
    print("[Playwright] Finviz 섹터 맵 정밀 캡처 중...")
    try:
        with sync_playwright() as p:
            # 자동화 탐지 우회를 위한 브라우저 인자 설정
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1600,1000"
                ]
            )
            
            context = browser.new_context(
                viewport={"width": 1600, "height": 1000},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York"
            )
            
            page = context.new_page()
            
            # webdriver 감지 우회 스크립트 주입
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page.goto(url, timeout=60000)
            
            # 맵 로딩 및 보안 체크 대기
            page.wait_for_timeout(7000)
            
            # 화면을 가리는 투어 팝업창 등 제거 시도
            try:
                page.evaluate("""
                    const tourOverlays = document.querySelectorAll('.joyride-overlay, .joyride-tip__container, div[style*="z-index: 1000"]');
                    tourOverlays.forEach(el => el.remove());
                """)
                page.wait_for_timeout(1000)
            except:
                pass
            
            # #canvas-wrapper 요소만 정확히 타겟팅하여 캡처
            map_element = page.locator("#canvas-wrapper")
            
            if map_element.count() > 0:
                map_element.first.screenshot(path=filepath)
                print(f"[캡처 성공] Finviz 맵(#canvas-wrapper) 저장 완료: {filepath}")
            else:
                print("[경고] #canvas-wrapper 요소를 찾지 못해 전체 화면으로 대체 캡처합니다.")
                page.screenshot(path=filepath, clip={"x": 50, "y": 180, "width": 1500, "height": 800})

            browser.close()
            
        return f"{CHART_DIR}/{filename}"
    except Exception as e:
        print(f"[캡처 오류] Finviz 맵 캡처 실패: {e}")
        return None
