import os
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# 1. Gemini API 클라이언트 설정 (GitHub Secrets에 저장된 키를 사용)
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

client = genai.Client(api_key=api_key)

# 2. 대시보드 크롤링 함수
def fetch_dashboard_data(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.get_text(separator="\n", strip=True)

# 3. 데이터 수집
print("국장 및 미장 대시보드 데이터 수집 중...")
kr_dashboard_url = "https://dhlee090512-arch.github.io/report/index.html"
us_dashboard_url = "https://dhlee090512-arch.github.io/report/us_index.html"

kr_raw_data = fetch_dashboard_data(kr_dashboard_url)
us_raw_data = fetch_dashboard_data(us_dashboard_url)

# 4. 프롬프트 정의
system_instruction = """
너는 개인 주식/트레이딩 블로거야.
입력된 국장/미장 대시보드 데이터 및 환율/매크로 브리핑을 바탕으로 블로그 포스팅 초안을 작성해줘.

[작성 지침 및 톤앤매너]
1. 주식 커뮤니티나 개인 트레이더 블로그에서 쓰는 담백하고 솔직한 구어체 및 어휘를 쓸 것.
   (예: "나락가면서", "짧게 먹는게", "손익비가 좋아보이는데", "슬퍼서 안가져올 수도 있습니다 ㅜ", "씁쓸하네요", "끗")
2. AI 특유의 뻔한 인사말("안녕하세요! 오늘은~")이나 딱딱한 서술어, 상투적인 비유는 절대 쓰지 말 것.
3. 소제목 구획은 [환율], [특징주] 형태로 나눌 것.
4. [환율] 파트는 수집된 매크로 지표/뉴스 데이터를 기반으로 최근 저점 수준, 연준/외환당국 동향, 중단기 상방 가능성 및 대응 방향(무지성 진입 금지, 수급/자리 위주 접근)을 정리할 것.
5. [특징주] 파트는 국장과 미장 대시보드에서 각각 추천 상위 종목을 2개씩 선정하여 총 4개 내외로 구성할 것.
   - 각 종목별로 거래량, RSI, 수급/뉴스 포인트, 그리고 구체적인 눌림목 타점/가격 수치를 직관적이고 가볍게 풀어서 쓸 것.
6. 글 마무리는 시장 상황에 대한 짧은 한 줄 총평과 위트 있는 사담, 그리고 반드시 "끗"으로 끝낼 것.
"""

user_prompt = f"""
다음은 오늘 대시보드에서 수집된 국장 및 미장 데이터입니다. 
이 데이터를 바탕으로 지침에 맞춰 블로그 포스팅을 작성해줘.

---
[국장 대시보드 데이터]
{kr_raw_data[:4000]}

---
[미장 대시보드 데이터]
{us_raw_data[:4000]}
"""

# 5. Gemini API 호출
print("Gemini API 호출하여 블로그 글 생성 중...")
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=user_prompt,
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.75,
    ),
)

print("\n================ [생성된 블로그 포스팅] ================\n")
print(response.text)
