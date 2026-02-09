#!/usr/bin/env python3
"""
핵심 내용 정리 모듈 (Step 4)

- 슬라이드별 발화 내용 요약
- Q&A 섹션 추출
- Key Takeaways 생성
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
import anthropic


def load_env_file():
    """프로젝트 루트의 .env 파일에서 환경 변수 로드"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file()


@dataclass
class SlideSummary:
    """슬라이드 요약 정보"""
    slide_num: int
    key_points: list[str] = field(default_factory=list)
    is_qa: bool = False
    raw_content: str = ""


def summarize_slide(
    client: anthropic.Anthropic,
    slide_num: int,
    slide_text: str,
    utterances: list[dict]
) -> SlideSummary:
    """단일 슬라이드의 발화 내용 요약"""
    
    if not utterances:
        return SlideSummary(slide_num=slide_num, key_points=[], raw_content="")
    
    # 발화 내용 합치기
    utterance_text = "\n".join([
        f"[{u['speaker']}] {u['content']}"
        for u in utterances
    ])
    
    prompt = f"""당신은 강의 내용을 요약하는 전문가입니다.

다음은 슬라이드 {slide_num}번에서 강연자가 설명한 내용입니다.

## 슬라이드 텍스트 (있는 경우):
{slide_text[:500] if slide_text else "(없음)"}

## 강연 내용:
{utterance_text}

위 내용을 분석하여 다음 JSON 형식으로 응답해주세요:

{{
  "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...],
  "is_qa": true/false,
  "category": "lecture" | "qa" | "intro" | "tangent" | "technical_issue"
}}

규칙:
1. key_points: 강의의 핵심 내용만 추출 (최대 5개)
   - 잡담, 기술적 문제(화면 조정 등), 인사말은 제외
   - 학술적/기술적으로 중요한 내용만 포함
   - 각 포인트는 한 문장으로 명확하게
2. is_qa: 질문과 답변이 포함된 경우 true
3. category: 이 슬라이드 내용의 분류
   - lecture: 본 강의 내용
   - qa: 질의응답
   - intro: 소개/인사
   - tangent: 여담/잡담
   - technical_issue: 기술적 문제 해결"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text
        
        # JSON 파싱
        import re
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return SlideSummary(
                slide_num=slide_num,
                key_points=result.get("key_points", []),
                is_qa=result.get("is_qa", False),
                raw_content=utterance_text
            )
    except Exception as e:
        print(f"   ⚠️ 슬라이드 {slide_num} 요약 실패: {e}")
    
    return SlideSummary(slide_num=slide_num, raw_content=utterance_text)


def extract_qa_section(summaries: list[SlideSummary], matches: list[dict]) -> list[dict]:
    """Q&A 섹션 추출"""
    qa_items = []
    
    for summary, match in zip(summaries, matches):
        if summary.is_qa:
            # Q&A로 분류된 슬라이드에서 질문-답변 쌍 추출
            utterances = match.get("utterances", [])
            
            # 강연자가 아닌 사람의 발화 = 질문
            # 강연자의 발화 = 답변
            main_speaker = "이헌준"  # TODO: 메타데이터에서 가져오기
            
            current_q = None
            for u in utterances:
                if u["speaker"] != main_speaker and "?" in u["content"]:
                    current_q = u["content"]
                elif u["speaker"] == main_speaker and current_q:
                    qa_items.append({
                        "question": current_q,
                        "answer": u["content"][:500]  # 답변은 500자로 제한
                    })
                    current_q = None
    
    return qa_items


def generate_key_takeaways(
    client: anthropic.Anthropic,
    summaries: list[SlideSummary],
    metadata: dict
) -> list[str]:
    """전체 강의 내용 기반 Key Takeaways 생성"""
    
    # 모든 핵심 포인트 수집
    all_points = []
    for summary in summaries:
        all_points.extend(summary.key_points)
    
    if not all_points:
        return []
    
    points_text = "\n".join([f"- {p}" for p in all_points])
    
    prompt = f"""당신은 강의 내용을 종합하는 전문가입니다.

강의 제목: {metadata.get('lecture_name', '알 수 없음')}

다음은 강의에서 추출된 주요 포인트들입니다:

{points_text}

위 내용을 바탕으로 이 강의의 **Key Takeaways**를 3-5개 작성해주세요.

규칙:
1. 가장 중요하고 기억해야 할 핵심 내용만 선별
2. 각 takeaway는 한 문장으로 명확하게
3. 실무/학습에 적용 가능한 통찰 포함
4. JSON 배열 형식으로 응답: ["takeaway1", "takeaway2", ...]"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text
        
        # JSON 배열 파싱
        import re
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"   ⚠️ Key Takeaways 생성 실패: {e}")
    
    return []


def run_summarization(output_dir: Path) -> dict:
    """
    전체 요약 프로세스 실행
    """
    print("\n" + "=" * 70)
    print("🔄 Step 4: 핵심 내용 정리 시작")
    print("=" * 70)
    
    # 데이터 로드
    matches_path = output_dir / "slide_matches.json"
    metadata_path = output_dir / "metadata.json"
    slides_info_path = output_dir / "slides_info.json"
    
    with open(matches_path, 'r', encoding='utf-8') as f:
        matches = json.load(f)
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    with open(slides_info_path, 'r', encoding='utf-8') as f:
        slides_info = json.load(f)
    
    # API 클라이언트 초기화
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return {}
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # 4-1: 슬라이드별 요약
    print("\n[4-1] 슬라이드별 핵심 내용 추출")
    summaries = []
    total = len(matches)
    
    for i, match in enumerate(matches):
        slide_num = match["slide_num"]
        utterances = match.get("utterances", [])
        
        # 슬라이드 텍스트 찾기
        slide_text = ""
        for s in slides_info:
            if s["page_num"] == slide_num:
                slide_text = s.get("text_preview", "")
                break
        
        summary = summarize_slide(client, slide_num, slide_text, utterances)
        summaries.append(summary)
        
        if (i + 1) % 10 == 0 or i + 1 == total:
            print(f"   → {i + 1}/{total} 슬라이드 요약 완료")
    
    # 통계
    slides_with_content = sum(1 for s in summaries if s.key_points)
    qa_slides = sum(1 for s in summaries if s.is_qa)
    print(f"   ✅ 내용 있는 슬라이드: {slides_with_content}개")
    print(f"   ✅ Q&A 슬라이드: {qa_slides}개")
    
    # 4-2: Q&A 섹션 추출
    print("\n[4-2] Q&A 섹션 추출")
    qa_items = extract_qa_section(summaries, matches)
    print(f"   ✅ 추출된 Q&A: {len(qa_items)}개")
    
    # 4-3: Key Takeaways 생성
    print("\n[4-3] Key Takeaways 생성")
    key_takeaways = generate_key_takeaways(client, summaries, metadata)
    print(f"   ✅ Key Takeaways: {len(key_takeaways)}개")
    
    # 결과 저장
    result = {
        "metadata": metadata,
        "summaries": [
            {
                "slide_num": s.slide_num,
                "key_points": s.key_points,
                "is_qa": s.is_qa
            }
            for s in summaries
        ],
        "qa_section": qa_items,
        "key_takeaways": key_takeaways
    }
    
    result_path = output_dir / "lecture_summary.json"
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n   ✅ 요약 결과 저장: {result_path.name}")
    
    print("\n" + "=" * 70)
    print("🎉 Step 4 완료!")
    print("=" * 70)
    
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
        run_summarization(output_dir)
    else:
        print("Usage: python summarizer.py <output_dir>")
