import os
from playwright.sync_api import sync_playwright

CHART_DIR = "assets"
if not os.path.exists(CHART_DIR):
    os.makedirs(CHART_DIR)

def capture_tradingview_chart(tv_symbol, filename):
    """
    트레이딩뷰 심볼(예: 'NASDAQ:NVDA')을 받아 해당 차트 화면을 깔끔하게 스크린샷 캡처합니다.
    """
    filepath = os.path.join(CHART_DIR, filename)
    url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"
    
    print(f"[Playwright] 트레이딩뷰 차트 캡처 중 ({tv_symbol})...")
    
    try:
        with sync_playwright() as p:
            # 브라우저 실행 (헤드리스 모드)
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1200, "height": 800})
            page = context.new_page()
            
            # 페이지 이동 및 로딩 대기
            page.goto(url, timeout=60000)
            
            # 트레이딩뷰 차트 캔버스 또는 메인 워크스페이스가 로드될 때까지 대기
            # (광고나 쿠키팝업 등이 가릴 수 있으므로 3초 정도 여유 대기)
            page.wait_for_timeout(4000)
            
            # 차트 영역 선택자 지정 (트레이딩뷰 차트 메인 컨테이너 캡처)
            chart_element = page.locator(".chart-container")
            if chart_element.count() > 0:
                chart_element.first.screenshot(path=filepath)
            else:
                # 컨테이너를 못 찾을 경우 전체 페이지 중 지정 영역 캡처
                page.screenshot(path=filepath, clip={"x": 0, "y": 50, "width": 1200, "height": 750})
                
            browser.close()
            
        print(f"[캡처 성공] 트레이딩뷰 차트 저장 완료: {filepath}")
        return f"{CHART_DIR}/{filename}"
    except Exception as e:
        print(f"[캡처 오류] {tv_symbol} 캡처 실패: {e}")
        return None
