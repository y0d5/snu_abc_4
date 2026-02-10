#!/usr/bin/env python3
"""
마크다운 결과물 생성 모듈 (Step 5)

- 슬라이드 이미지 + 핵심 내용을 결합한 마크다운 생성
- Q&A 섹션 추가
- Key Takeaways 섹션 추가
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import json
import re
from pathlib import Path
from datetime import datetime


def parse_lecture_name(lecture_name: str) -> dict:
    """강의 폴더명에서 정보 추출"""
    # 예: "12-이헌준-Computing System for AI-260206"
    parts = lecture_name.split("-")
    
    if len(parts) >= 4:
        num = parts[0]
        speaker = parts[1]
        # 주제는 마지막 날짜 부분 제외하고 합치기
        date_str = parts[-1]
        topic = "-".join(parts[2:-1])
        
        # 날짜 파싱 (YYMMDD 형식)
        try:
            year = int("20" + date_str[:2])
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            date_formatted = f"{year}년 {month}월 {day}일"
        except:
            date_formatted = date_str
        
        return {
            "num": num,
            "speaker": speaker,
            "topic": topic,
            "date": date_formatted,
            "date_raw": date_str
        }
    
    return {
        "num": "",
        "speaker": "",
        "topic": lecture_name,
        "date": "",
        "date_raw": ""
    }


def generate_markdown(output_dir: Path) -> Path:
    """
    최종 마크다운 문서 생성
    """
    print("\n" + "=" * 70)
    print("🔄 Step 5: 마크다운 결과물 생성")
    print("=" * 70)
    
    # 데이터 로드
    summary_path = output_dir / "lecture_summary.json"
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        summary_data = json.load(f)
    
    metadata = summary_data["metadata"]
    summaries = summary_data["summaries"]
    qa_section = summary_data.get("qa_section", [])
    key_takeaways = summary_data.get("key_takeaways", [])
    
    # 강의 정보 파싱
    lecture_info = parse_lecture_name(metadata["lecture_name"])
    
    # 마크다운 생성
    md_lines = []
    
    # 헤더
    md_lines.append(f"# {lecture_info['topic']}")
    md_lines.append("")
    md_lines.append("## 강의 정보")
    md_lines.append("")
    md_lines.append(f"| 항목 | 내용 |")
    md_lines.append(f"|------|------|")
    md_lines.append(f"| **강연자** | {lecture_info['speaker']} |")
    md_lines.append(f"| **날짜** | {lecture_info['date']} |")
    md_lines.append(f"| **강의 시간** | {metadata.get('stt_duration', '알 수 없음')} |")
    md_lines.append(f"| **슬라이드 수** | {metadata.get('total_slides', 0)}장 |")
    md_lines.append("")
    
    # 목차
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 목차")
    md_lines.append("")
    md_lines.append("1. [슬라이드별 강의 내용](#슬라이드별-강의-내용)")
    md_lines.append("2. [Q&A](#qa)")
    md_lines.append("3. [Key Takeaways](#key-takeaways)")
    md_lines.append("")
    
    # 슬라이드별 내용
    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## 슬라이드별 강의 내용")
    md_lines.append("")
    
    print("\n[5-1] 슬라이드별 내용 작성")
    
    slides_dir = output_dir / "slides"
    
    for i, summary in enumerate(summaries):
        slide_num = summary["slide_num"]
        key_points = summary.get("key_points", [])
        
        # 슬라이드 섹션
        md_lines.append(f"### 슬라이드 {slide_num}")
        md_lines.append("")
        
        # 슬라이드 이미지 (상대 경로)
        image_name = f"slide_{slide_num:03d}.png"
        image_path = slides_dir / image_name
        
        if image_path.exists():
            md_lines.append(f"![슬라이드 {slide_num}](slides/{image_name})")
            md_lines.append("")
        
        # 핵심 내용
        if key_points:
            md_lines.append("**주요 내용:**")
            md_lines.append("")
            for point in key_points:
                md_lines.append(f"- {point}")
            md_lines.append("")
        else:
            md_lines.append("*(내용 없음)*")
            md_lines.append("")
        
        md_lines.append("---")
        md_lines.append("")
        
        if (i + 1) % 10 == 0:
            print(f"   → {i + 1}/{len(summaries)} 슬라이드 작성 완료")
    
    print(f"   ✅ {len(summaries)}개 슬라이드 작성 완료")
    
    # Q&A 섹션
    print("\n[5-2] Q&A 섹션 작성")
    md_lines.append("## Q&A")
    md_lines.append("")
    
    if qa_section:
        for i, qa in enumerate(qa_section, 1):
            question = qa.get("question", "")
            answer = qa.get("answer", "")
            
            md_lines.append(f"### Q{i}. {question[:100]}{'...' if len(question) > 100 else ''}")
            md_lines.append("")
            md_lines.append(f"**A:** {answer}")
            md_lines.append("")
        
        print(f"   ✅ {len(qa_section)}개 Q&A 작성 완료")
    else:
        md_lines.append("*(질의응답 내용 없음)*")
        md_lines.append("")
        print("   → Q&A 없음")
    
    md_lines.append("---")
    md_lines.append("")
    
    # Key Takeaways 섹션
    print("\n[5-3] Key Takeaways 섹션 작성")
    md_lines.append("## Key Takeaways")
    md_lines.append("")
    
    if key_takeaways:
        for i, takeaway in enumerate(key_takeaways, 1):
            md_lines.append(f"{i}. {takeaway}")
            md_lines.append("")
        
        print(f"   ✅ {len(key_takeaways)}개 Key Takeaways 작성 완료")
    else:
        md_lines.append("*(Key Takeaways 없음)*")
        md_lines.append("")
        print("   → Key Takeaways 없음")
    
    md_lines.append("---")
    md_lines.append("")
    
    # 푸터
    md_lines.append("## 문서 정보")
    md_lines.append("")
    md_lines.append(f"- 생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md_lines.append(f"- 원본 파일: {metadata.get('pdf_files', [])}")
    md_lines.append(f"- STT 파일: {metadata.get('txt_files', [])}")
    md_lines.append("")
    
    # 파일 저장
    md_content = "\n".join(md_lines)
    
    # 파일명 생성 (강의 주제 기반)
    safe_topic = re.sub(r'[^\w\s가-힣-]', '', lecture_info['topic'])
    safe_topic = safe_topic.replace(' ', '_')
    md_filename = f"{lecture_info['num']}-{safe_topic}-강의노트.md"
    
    md_path = output_dir / md_filename
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"\n   ✅ 마크다운 저장: {md_filename}")
    
    # HTML 생성
    print("\n[5-4] HTML 생성")
    html_filename = md_filename.replace('.md', '.html')
    html_path = output_dir / html_filename
    
    generate_html(output_dir, summaries, qa_section, key_takeaways, metadata, lecture_info, html_path)
    print(f"   ✅ HTML 저장: {html_filename}")
    
    # 통계 출력
    print("\n" + "=" * 70)
    print("🎉 Step 5 완료!")
    print("=" * 70)
    print(f"📄 생성된 파일: {md_path}")
    print(f"📄 생성된 파일: {html_path}")
    print(f"📊 문서 통계:")
    print(f"   - 전체 라인 수: {len(md_lines)}")
    print(f"   - 슬라이드 수: {len(summaries)}")
    print(f"   - Q&A 수: {len(qa_section)}")
    print(f"   - Key Takeaways 수: {len(key_takeaways)}")
    print("=" * 70)
    
    return md_path


def generate_html(output_dir, summaries, qa_section, key_takeaways, metadata, lecture_info, html_path):
    """HTML 파일 생성 (슬라이드 왼쪽, 포인트 오른쪽 레이아웃)"""
    import base64
    
    slides_dir = output_dir / "slides"
    
    # Base64로 이미지 인코딩
    def get_image_base64(img_path):
        if img_path.exists():
            with open(img_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        return None
    
    html_parts = []
    
    # HTML 헤더 (슬라이드 왼쪽 + 포인트 오른쪽 레이아웃)
    html_parts.append(f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{lecture_info['topic']} - 강의노트</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
            margin-bottom: 24px;
            border-radius: 12px;
        }}
        header h1 {{ font-size: 1.8em; margin-bottom: 8px; }}
        header .meta {{ opacity: 0.9; font-size: 0.95em; }}
        
        /* 슬라이드 섹션: 왼쪽 이미지 + 오른쪽 포인트 */
        .slide-section {{
            background: white;
            margin-bottom: 16px;
            border-radius: 10px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            overflow: hidden;
            display: flex;
            flex-direction: row;
            align-items: stretch;
        }}
        .slide-left {{
            flex: 0 0 320px;
            background: #f8f9fa;
            padding: 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            border-right: 1px solid #eee;
        }}
        .slide-num {{
            font-size: 0.85em;
            color: #888;
            margin-bottom: 8px;
            font-weight: 600;
        }}
        .slide-image {{
            width: 100%;
            max-width: 300px;
            border: 1px solid #ddd;
            border-radius: 6px;
        }}
        .slide-right {{
            flex: 1;
            padding: 16px 20px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .key-points {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .key-points li {{
            padding: 8px 12px;
            margin-bottom: 6px;
            background: #f8f9fa;
            border-left: 3px solid #667eea;
            border-radius: 4px;
            font-size: 0.95em;
            line-height: 1.5;
        }}
        .key-points li:last-child {{
            margin-bottom: 0;
        }}
        .no-points {{
            color: #999;
            font-style: italic;
            font-size: 0.9em;
        }}
        
        /* Q&A 섹션 */
        .qa-section, .takeaways-section {{
            background: white;
            padding: 24px;
            margin-bottom: 16px;
            border-radius: 10px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        }}
        .qa-section h2, .takeaways-section h2 {{
            color: #667eea;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid #eee;
            font-size: 1.3em;
        }}
        .qa-item {{
            margin-bottom: 16px;
            padding-bottom: 16px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .qa-item:last-child {{
            margin-bottom: 0;
            padding-bottom: 0;
            border-bottom: none;
        }}
        .qa-item .question {{
            font-weight: bold;
            color: #333;
            margin-bottom: 6px;
        }}
        .qa-item .answer {{
            padding-left: 16px;
            color: #555;
            border-left: 3px solid #764ba2;
        }}
        
        /* Key Takeaways */
        .takeaways-section ul {{
            list-style: none;
            padding: 0;
        }}
        .takeaways-section li {{
            padding: 10px 14px;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 6px;
            border-left: 3px solid #764ba2;
        }}
        .takeaways-section li:last-child {{
            margin-bottom: 0;
        }}
        
        footer {{
            text-align: center;
            padding: 16px;
            color: #999;
            font-size: 0.85em;
        }}
        
        /* 반응형: 작은 화면에서는 세로 배치 */
        @media (max-width: 768px) {{
            .slide-section {{
                flex-direction: column;
            }}
            .slide-left {{
                flex: none;
                border-right: none;
                border-bottom: 1px solid #eee;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{lecture_info['topic']}</h1>
            <div class="meta">
                강연자: {lecture_info['speaker']} | 날짜: {lecture_info['date']}
            </div>
        </header>
''')
    
    # 슬라이드 섹션 (왼쪽 이미지 + 오른쪽 포인트)
    for i, summary in enumerate(summaries):
        slide_num = summary.get('slide_num', i + 1)
        key_points = summary.get('key_points', [])
        
        # 슬라이드 이미지
        img_path = slides_dir / f"slide_{slide_num:03d}.png"
        img_base64 = get_image_base64(img_path)
        
        html_parts.append(f'''
        <div class="slide-section">
            <div class="slide-left">
                <div class="slide-num">슬라이드 {slide_num}</div>
''')
        
        if img_base64:
            html_parts.append(f'                <img src="data:image/png;base64,{img_base64}" class="slide-image" alt="슬라이드 {slide_num}">')
        
        html_parts.append('''            </div>
            <div class="slide-right">
''')
        
        if key_points:
            html_parts.append('                <ul class="key-points">')
            for point in key_points:
                html_parts.append(f'                    <li>{point}</li>')
            html_parts.append('                </ul>')
        else:
            html_parts.append('                <p class="no-points">(내용 없음)</p>')
        
        html_parts.append('''            </div>
        </div>
''')
    
    # Q&A 섹션
    if qa_section:
        html_parts.append('''
        <div class="qa-section">
            <h2>💬 Q&A</h2>
''')
        for qa in qa_section:
            html_parts.append(f'''            <div class="qa-item">
                <div class="question">Q: {qa.get('question', '')}</div>
                <div class="answer">A: {qa.get('answer', '')}</div>
            </div>
''')
        html_parts.append('        </div>')
    
    # Key Takeaways 섹션
    if key_takeaways:
        html_parts.append('''
        <div class="takeaways-section">
            <h2>📌 Key Takeaways</h2>
            <ul>
''')
        for takeaway in key_takeaways:
            html_parts.append(f'                <li>{takeaway}</li>')
        html_parts.append('''            </ul>
        </div>
''')
    
    # 푸터
    html_parts.append(f'''
        <footer>
            생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 자동 생성된 강의노트
        </footer>
    </div>
</body>
</html>
''')
    
    html_content = ''.join(html_parts)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
        generate_markdown(output_dir)
    else:
        print("Usage: python generator.py <output_dir>")
