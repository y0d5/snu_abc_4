#!/usr/bin/env python3
"""
슬라이드-STT 매칭 모듈 (하이브리드 방식)

1차: 시간 기반 균등 분할
2차: LLM 검증 및 조정
3차: 불확실한 부분 재매칭
"""

import sys
# 출력 버퍼링 비활성화
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

# .env 파일 로드
load_env_file()


@dataclass
class SlideMatch:
    """슬라이드-발화 매칭 결과"""
    slide_num: int
    slide_text: str
    utterances: list[dict] = field(default_factory=list)
    confidence: str = "unknown"  # high, medium, low, unknown
    llm_verified: bool = False
    notes: str = ""


def time_based_matching(
    slides_info: list[dict],
    stt_data: dict,
    total_duration_seconds: int
) -> list[SlideMatch]:
    """
    1차: 페이지 번호 우선, 없으면 시간 기반 균등 분할 매칭

    - STT에 slide_num(페이지 번호)이 있으면 해당 슬라이드에 직접 배정 (우선)
    - 없으면 기존처럼 시간대 기반으로 배정
    """
    print("\n[3-1] 슬라이드-STT 매칭 (페이지 번호 우선, 시간 기반 보조)")
    
    num_slides = len(slides_info)
    utterances = stt_data.get("utterances", [])
    
    if not utterances:
        print("   ⚠️ 발화 데이터가 없습니다.")
        return []
    
    # 페이지 번호가 있는 발화 수
    page_annotated = sum(1 for u in utterances if u.get("slide_num"))
    if page_annotated:
        print(f"   📌 페이지 번호가 있는 발화: {page_annotated}개 (우선 매칭)")
    
    # 마지막 발화 시간을 기준으로 (시간 기반 매칭용)
    last_utterance_time = max(u["seconds"] for u in utterances)
    time_per_slide = last_utterance_time / num_slides if num_slides else 1
    
    print(f"   총 슬라이드: {num_slides}개")
    print(f"   총 발화: {len(utterances)}개")
    print(f"   마지막 발화 시간: {last_utterance_time}초")
    
    # 슬라이드별 매칭 초기화
    matches = []
    for i, slide in enumerate(slides_info):
        match = SlideMatch(
            slide_num=slide["page_num"],
            slide_text=slide.get("text_preview", ""),
            utterances=[],
            confidence="unknown"
        )
        matches.append(match)
    
    # 각 발화를 슬라이드에 배정
    for utterance in utterances:
        slide_idx = None
        slide_num = utterance.get("slide_num")
        
        # 1) 페이지 번호가 있으면 해당 슬라이드에 배정 (1-based → 0-based)
        if slide_num is not None and 1 <= slide_num <= num_slides:
            slide_idx = slide_num - 1
        # 2) 없으면 시간 기반 배정
        if slide_idx is None:
            seconds = utterance["seconds"]
            slide_idx = min(int(seconds / time_per_slide), num_slides - 1) if num_slides else 0
        
        matches[slide_idx].utterances.append(utterance)
    
    # 통계 출력
    empty_slides = sum(1 for m in matches if len(m.utterances) == 0)
    print(f"   → 매칭 완료: {num_slides - empty_slides}개 슬라이드에 발화 배정")
    print(f"   → 발화 없는 슬라이드: {empty_slides}개")
    
    return matches


def llm_verify_matches(
    matches: list[SlideMatch],
    batch_size: int = 5
) -> list[SlideMatch]:
    """
    2차: LLM을 사용하여 매칭 검증 및 조정
    
    슬라이드 텍스트와 배정된 발화 내용을 비교하여 일치 여부 확인
    """
    print("\n[3-2] LLM 검증 시작")
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("   ⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        print("   → .env 파일에 API 키를 설정해주세요.")
        print("   → LLM 검증을 건너뜁니다.")
        return matches
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # 발화가 있는 슬라이드만 검증
    slides_to_verify = [m for m in matches if m.utterances]
    total = len(slides_to_verify)
    
    print(f"   검증 대상: {total}개 슬라이드")
    
    verified_count = 0
    adjusted_count = 0
    
    # 배치 단위로 처리
    for i in range(0, total, batch_size):
        batch = slides_to_verify[i:i+batch_size]
        
        for match in batch:
            try:
                result = verify_single_match(client, match, matches)
                if result["verified"]:
                    match.confidence = "high"
                    match.llm_verified = True
                    verified_count += 1
                else:
                    match.confidence = result.get("confidence", "low")
                    match.notes = result.get("notes", "")
                    if result.get("adjusted"):
                        adjusted_count += 1
            except Exception as e:
                print(f"   ⚠️ 슬라이드 {match.slide_num} 검증 실패: {e}")
                match.confidence = "unknown"
        
        print(f"   → {min(i + batch_size, total)}/{total} 검증 완료")
    
    print(f"   ✅ 검증 완료: {verified_count}개 일치, {adjusted_count}개 조정됨")
    
    return matches


def verify_single_match(
    client: anthropic.Anthropic,
    match: SlideMatch,
    all_matches: list[SlideMatch]
) -> dict:
    """단일 슬라이드-발화 매칭 검증"""
    
    # 발화 내용 요약 (페이지 번호 힌트 포함)
    utterance_lines = []
    page_hint_utterances = []
    for u in match.utterances[:5]:  # 최대 5개만
        line = f"[{u['timestamp']}] {u['speaker']}: {u['content'][:200]}"
        utterance_lines.append(line)
        if u.get("slide_num"):
            page_hint_utterances.append(f"  - {u['timestamp']} 발화: 원본 STT에서 슬라이드 {u['slide_num']}번으로 표시됨")
    utterance_text = "\n".join(utterance_lines)
    page_hint_block = ""
    if page_hint_utterances:
        page_hint_block = "\n## STT 페이지 번호 정보 (우선 고려):\n" + "\n".join(page_hint_utterances) + "\n"
    
    # 인접 슬라이드 정보
    slide_idx = match.slide_num - 1
    prev_slide_text = all_matches[slide_idx - 1].slide_text if slide_idx > 0 else ""
    next_slide_text = all_matches[slide_idx + 1].slide_text if slide_idx < len(all_matches) - 1 else ""
    
    prompt = f"""당신은 강의 슬라이드와 강연 내용을 매칭하는 전문가입니다.

현재 슬라이드 {match.slide_num}번에 다음 발화들이 배정되어 있습니다.{page_hint_block}

## 슬라이드 {match.slide_num} 텍스트:
{match.slide_text[:500] if match.slide_text else "(텍스트 없음)"}

## 배정된 발화 내용:
{utterance_text}

## 이전 슬라이드 ({match.slide_num - 1}번) 텍스트:
{prev_slide_text[:200] if prev_slide_text else "(없음)"}

## 다음 슬라이드 ({match.slide_num + 1}번) 텍스트:
{next_slide_text[:200] if next_slide_text else "(없음)"}
{"\n**STT에 페이지 번호가 표시된 발화는 원본 녹음에서 해당 슬라이드로 기록된 것이므로, 그 정보를 우선적으로 신뢰해주세요.**" if page_hint_utterances else ""}

이 발화들이 현재 슬라이드에 적절하게 매칭되었는지 판단해주세요.

JSON 형식으로 답변해주세요:
{{
  "match_quality": "good" | "partial" | "poor",
  "confidence": "high" | "medium" | "low",
  "reasoning": "판단 이유 (한 문장)",
  "suggested_slide": 현재 슬라이드가 적절하면 {match.slide_num}, 아니면 더 적절한 슬라이드 번호
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # 응답 파싱
    response_text = response.content[0].text
    
    try:
        # JSON 추출
        import re
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            
            verified = result.get("match_quality") in ["good", "partial"]
            return {
                "verified": verified,
                "confidence": result.get("confidence", "medium"),
                "notes": result.get("reasoning", ""),
                "adjusted": result.get("suggested_slide") != match.slide_num
            }
    except json.JSONDecodeError:
        pass
    
    return {"verified": False, "confidence": "unknown", "notes": "파싱 실패"}


def refine_uncertain_matches(matches: list[SlideMatch]) -> list[SlideMatch]:
    """
    3차: 불확실한 매칭 재조정
    
    confidence가 low인 매칭들을 인접 슬라이드와 비교하여 재조정
    """
    print("\n[3-3] 불확실한 매칭 재조정")
    
    uncertain = [m for m in matches if m.confidence == "low"]
    
    if not uncertain:
        print("   → 재조정이 필요한 슬라이드가 없습니다.")
        return matches
    
    print(f"   재조정 대상: {len(uncertain)}개 슬라이드")
    
    # 간단한 휴리스틱: 발화 내용에 슬라이드 키워드가 포함되어 있는지 확인
    adjusted_count = 0
    
    for match in uncertain:
        # 현재 슬라이드의 키워드
        current_keywords = set(match.slide_text.lower().split()) if match.slide_text else set()
        
        # 발화 내용의 키워드
        utterance_text = " ".join([u["content"] for u in match.utterances])
        utterance_keywords = set(utterance_text.lower().split())
        
        # 키워드 겹침 정도 계산
        if current_keywords:
            overlap = len(current_keywords & utterance_keywords) / len(current_keywords)
            if overlap > 0.1:  # 10% 이상 겹치면 적절한 것으로 판단
                match.confidence = "medium"
                match.notes += " (키워드 매칭으로 조정)"
                adjusted_count += 1
    
    print(f"   ✅ {adjusted_count}개 슬라이드 confidence 조정됨")
    
    return matches


def run_matching(output_dir: Path) -> list[SlideMatch]:
    """
    전체 매칭 프로세스 실행
    """
    print("\n" + "=" * 70)
    print("🔄 Step 3: 슬라이드-STT 매칭 시작")
    print("=" * 70)
    
    # 데이터 로드
    slides_info_path = output_dir / "slides_info.json"
    stt_path = output_dir / "stt_parsed.json"
    metadata_path = output_dir / "metadata.json"
    
    with open(slides_info_path, 'r', encoding='utf-8') as f:
        slides_info = json.load(f)
    
    with open(stt_path, 'r', encoding='utf-8') as f:
        stt_data = json.load(f)
    
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # STT duration 파싱 (예: "94분 3초")
    duration_str = metadata.get("stt_duration", "0분")
    import re
    mins = re.search(r'(\d+)분', duration_str)
    secs = re.search(r'(\d+)초', duration_str)
    total_seconds = (int(mins.group(1)) * 60 if mins else 0) + (int(secs.group(1)) if secs else 0)
    
    # 1차: 시간 기반 매칭
    matches = time_based_matching(slides_info, stt_data, total_seconds)
    
    # 2차: LLM 검증
    matches = llm_verify_matches(matches)
    
    # 3차: 불확실한 매칭 재조정
    matches = refine_uncertain_matches(matches)
    
    # 결과 저장
    result_path = output_dir / "slide_matches.json"
    result_data = [
        {
            "slide_num": m.slide_num,
            "utterance_count": len(m.utterances),
            "confidence": m.confidence,
            "llm_verified": m.llm_verified,
            "notes": m.notes,
            "utterances": m.utterances
        }
        for m in matches
    ]
    
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n   ✅ 매칭 결과 저장: {result_path.name}")
    
    # 통계
    high_conf = sum(1 for m in matches if m.confidence == "high")
    medium_conf = sum(1 for m in matches if m.confidence == "medium")
    low_conf = sum(1 for m in matches if m.confidence == "low")
    
    print("\n" + "-" * 70)
    print("📊 매칭 결과 요약")
    print("-" * 70)
    print(f"   높은 신뢰도 (high):   {high_conf}개")
    print(f"   중간 신뢰도 (medium): {medium_conf}개")
    print(f"   낮은 신뢰도 (low):    {low_conf}개")
    print("=" * 70)
    
    return matches


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
        run_matching(output_dir)
    else:
        print("Usage: python matcher.py <output_dir>")
