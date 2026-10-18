# 10. HTML 미리보기 파일 생성 (줄바꿈 \n을 HTML <br> 태그로 변환하여 블로그 붙여넣기 완벽 지원)
html_body_formatted = formatted_body.replace("\n", "<br>")

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
        .content {{ background: #fafafa; padding: 25px; border-radius: 8px; font-size: 16px; word-break: break-all; border: 1px solid #eee; }}
        .img-box {{ margin: 25px 0; text-align: center; }}
        img {{ max-width: 100%; height: auto; border: 1px solid #e1e4e8; border-radius: 6px; display: block; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    </style>
</head>
<body>
    <div class="timestamp-badge">⏱️ 업데이트 시각: {formatted_kst_time}</div>
    <h1>📊 자동 생성 블로그 포스팅 미리보기</h1>
    <p>아래 제목과 본문을 드래그해서 그대로 블로그에 붙여넣으세요.</p>
    <hr>
    
    <h3>📌 포스팅 제목</h3>
    <div class="title-box">{post_title}</div>

    <h3>📝 본문 텍스트 (차트 및 거시경제 링크 포함)</h3>
    <div class="content">{html_body_formatted}</div>
</body>
</html>
"""
