import os
from playwright.sync_api import sync_playwright

def capture_tradingview_chart(symbol: str, filename: str) -> str:
    """
    main.py와의 호환성을 유지하며, 
    국내/해외 종목에 맞춰 네이버 증권(또는 네이버페이 증권) 차트를 캡처합니다.
    """
    os.makedirs("assets", exist_ok=True)
    save_path = os.path.join("assets", filename)
    
    # 심볼 형태 분석 (예: 'KRX:005930' 또는 'NASDAQ:NVDA')
    market, code = symbol.split(":") if ":" in symbol else ("KRX", symbol)
    
    if market == "KRX":
        # 네이버 증권 국내 주식 차트 페이지 URL
        url = f"https://finance.naver.com/item/fchart.naver?code={code}"
    else:
        # 네이버페이 증권 모바일 웹을 활용한 해외 주식 차트 URL
        ticker = code
        url = f"https://m.stock.naver.com/world/stock/{ticker}/chart"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # 차트가 잘 보이도록 적절한 뷰포트 설정
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3500) # 차트 및 보조지표 렌더링 대기
            
            if market == "KRX":
                # 국내 증권 차트 영역 지정 캡처 시도 (실패 시 전체 화면 캡처)
                chart_element = page.locator("#chart_area")
                if chart_element.count() > 0:
                    chart_element.screenshot(path=save_path)
                else:
                    page.screenshot(path=save_path, full_page=False)
            else:
                # 해외 주식 모바일웹 페이지 캡처
                page.screenshot(path=save_path, full_page=False)
                
            browser.close()
            print(f"[네이버증권 캡처 성공] {filename}")
            return save_path
            
    except Exception as e:
        print(f"[네이버증권 캡처 실패] {symbol}: {e}")
        return None

def capture_fx_tradingview(filename: str) -> str:
    # 환율 차트 처리 (필요 시 네이버 환율 페이지 활용 가능)
    os.makedirs("assets", exist_ok=True)
    save_path = os.path.join("assets", filename)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            # 원달러 환율 페이지
            page.goto("https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW", timeout=30000)
            page.wait_for_timeout(2000)
            page.screenshot(path=save_path)
            browser.close()
            return save_path
    except Exception as e:
        print(f"환율 캡처 실패: {e}")
        return None

def capture_finviz_map(filename: str) -> str:
    # Finviz 섹터 맵은 기존 방식 유지
    os.makedirs("assets", exist_ok=True)
    save_path = os.path.join("assets", filename)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto("https://finviz.com/map.svg", timeout=30000)
            page.screenshot(path=save_path)
            browser.close()
            return save_path
    except Exception as e:
        print(f"Finviz 캡처 실패: {e}")
        return None
