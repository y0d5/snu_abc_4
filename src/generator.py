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
    
    # 통계 출력
    print("\n" + "=" * 70)
    print("🎉 Step 5 완료!")
    print("=" * 70)
    print(f"📄 생성된 파일: {md_path}")
    print(f"📊 문서 통계:")
    print(f"   - 전체 라인 수: {len(md_lines)}")
    print(f"   - 슬라이드 수: {len(summaries)}")
    print(f"   - Q&A 수: {len(qa_section)}")
    print(f"   - Key Takeaways 수: {len(key_takeaways)}")
    print("=" * 70)
    
    return md_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
        generate_markdown(output_dir)
    else:
        print("Usage: python generator.py <output_dir>")
