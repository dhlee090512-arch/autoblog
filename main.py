# 5. Gemini API 호출 (지수 백오프 + 폴백 모델 로직 적용)
system_instruction = load_prompt("prompt.txt")
user_prompt = f"--- [국장 대시보드 Data] ---\n{kr_raw[:3500]}\n\n--- [미장 대시보드 Data] ---\n{us_raw[:3500]}"

# 주 모델과 폴백(백업) 모델 목록
models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
response = None

for model_name in models_to_try:
    print(f"[{model_name}] 모델로 시도 시작...")
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Gemini API 호출 중 ({model_name} - 시도 {attempt}/{max_retries})...")
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.75,
                ),
            )
            print(f"[{model_name}] 호출 성공!")
            break  # 호출 성공 시 안쪽 loop 탈출
        except Exception as e:
            print(f"API 호출 실패 (에러: {e})")
            if attempt < max_retries:
                retry_delay = attempt * 15  # 15초, 30초, 45초로 지수 대기
                print(f"{retry_delay}초 후 재시도합니다...")
                time.sleep(retry_delay)
            else:
                print(f"[{model_name}] 모델 최대 재시도 초과. 다음 백업 모델로 전환합니다.")

    if response:
        break  # 성공했으면 전체 모델 시도 탈출

if not response:
    raise RuntimeError("모든 Gemini 모델 및 재시도가 실패했습니다. 잠시 후 다시 실행해 주세요.")

raw_blog_text = response.text
