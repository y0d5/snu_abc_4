#!/usr/bin/env python3
"""
슬라이드-STT 매칭 모듈

[v2] 슬라이딩 윈도우 방식:
  - STT를 10분 단위 청크로 분할
  - 각 청크를 슬라이드 윈도우(~15장)와 LLM으로 매칭
  - 이전 청크 결과를 기반으로 윈도우를 이동

[v1] 레거시 방식 (기존 데이터 호환):
  - 시간 기반 균등 분할 + LLM 검증
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

import os
import re
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


###############################################################################
# v2: 슬라이딩 윈도우 매칭 (새 방식)
###############################################################################

DEFAULT_LECTURE_MINUTES = 150   # 기본 강의 시간 (분)
CHUNK_MINUTES = 10             # 청크 단위 (분)
WINDOW_MULTIPLIER = 3          # 윈도우 크기 = 청크당 평균 슬라이드 × 이 배수
OVERLAP_BACK = 2               # 윈도우 시작 시 뒤로 겹치는 슬라이드 수


def sliding_window_matching(
    slides_info: list[dict],
    stt_data: dict,
    total_duration_seconds: int
) -> list[SlideMatch]:
    """
    슬라이딩 윈도우 방식의 슬라이드-STT 매칭

    1) 강의 시간 결정 (기본 150분, STT와 20% 이상 차이시 STT 기준)
    2) 슬라이드당 평균 시간 계산
    3) STT를 10분 청크로 분할
    4) 각 청크를 슬라이드 윈도우와 LLM으로 매칭
    5) 윈도우를 이동하며 반복
    """
    print("\n[3-1] 슬라이딩 윈도우 매칭 시작")

    num_slides = len(slides_info)
    utterances = stt_data.get("utterances", [])

    if not utterances or not num_slides:
        print("   ⚠️ 슬라이드 또는 발화 데이터가 없습니다.")
        return []

    # --- 강의 시간 결정 ---
    default_seconds = DEFAULT_LECTURE_MINUTES * 60
    stt_last_second = max(u["seconds"] for u in utterances)

    if total_duration_seconds > 0 and abs(total_duration_seconds - default_seconds) / default_seconds < 0.2:
        lecture_seconds = default_seconds
    elif total_duration_seconds > 0:
        lecture_seconds = total_duration_seconds
    else:
        lecture_seconds = stt_last_second if stt_last_second > 0 else default_seconds

    if stt_last_second > lecture_seconds:
        lecture_seconds = stt_last_second

    lecture_minutes = lecture_seconds / 60
    avg_sec_per_slide = lecture_seconds / num_slides
    avg_min_per_slide = avg_sec_per_slide / 60

    print(f"   📊 강의 시간: {lecture_minutes:.0f}분")
    print(f"   📊 슬라이드: {num_slides}장")
    print(f"   📊 슬라이드당 평균: {avg_min_per_slide:.1f}분")
    print(f"   📊 총 발화: {len(utterances)}개")

    # --- 청크 분할 ---
    chunk_seconds = CHUNK_MINUTES * 60
    slides_per_chunk = int(CHUNK_MINUTES / avg_min_per_slide) if avg_min_per_slide > 0 else 5
    window_size = max(slides_per_chunk * WINDOW_MULTIPLIER, 10)

    chunks = split_utterances_into_chunks(utterances, chunk_seconds)
    print(f"   📊 {CHUNK_MINUTES}분 청크: {len(chunks)}개, 윈도우 크기: {window_size}장")

    # --- 슬라이드 매칭 결과 초기화 ---
    matches = []
    for slide in slides_info:
        matches.append(SlideMatch(
            slide_num=slide["page_num"],
            slide_text=slide.get("text_preview", ""),
            utterances=[],
            confidence="unknown"
        ))

    # --- API 클라이언트 ---
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("   ⚠️ ANTHROPIC_API_KEY 없음 → 시간 기반 폴백")
        return _fallback_time_based(matches, utterances, num_slides, stt_last_second)

    client = anthropic.Anthropic(api_key=api_key)

    # --- 청크별 슬라이딩 윈도우 매칭 ---
    window_start = 0  # 0-based slide index

    for chunk_idx, chunk in enumerate(chunks):
        chunk_start_min = chunk["start_sec"] / 60
        chunk_end_min = chunk["end_sec"] / 60
        chunk_utterances = chunk["utterances"]

        if not chunk_utterances:
            continue

        # 윈도우 범위: 뒤로 OVERLAP_BACK만큼 여유, 앞으로 window_size
        win_start = max(0, window_start - OVERLAP_BACK)
        win_end = min(num_slides, window_start + window_size)

        # 마지막 청크라면 남은 슬라이드 전부 포함
        if chunk_idx == len(chunks) - 1:
            win_end = num_slides

        window_slides = slides_info[win_start:win_end]

        print(f"\n   🔄 청크 {chunk_idx + 1}/{len(chunks)} "
              f"({chunk_start_min:.0f}~{chunk_end_min:.0f}분) "
              f"→ 슬라이드 {win_start + 1}~{win_end}번")

        # LLM으로 청크 매칭
        try:
            chunk_result = llm_match_chunk(
                client, chunk_utterances, window_slides,
                win_start, chunk_start_min, chunk_end_min
            )
        except Exception as e:
            print(f"      ⚠️ LLM 매칭 실패: {e} → 균등 분할 폴백")
            chunk_result = _fallback_chunk(chunk_utterances, win_start, win_end)

        # 결과 반영
        last_matched_idx = win_start
        for mapping in chunk_result:
            slide_idx = mapping["slide_idx"]
            mapped_utterances = mapping["utterances"]

            if 0 <= slide_idx < num_slides:
                matches[slide_idx].utterances.extend(mapped_utterances)
                matches[slide_idx].confidence = mapping.get("confidence", "medium")
                matches[slide_idx].llm_verified = True
                if slide_idx > last_matched_idx:
                    last_matched_idx = slide_idx

        # 다음 윈도우 시작점
        window_start = last_matched_idx + 1
        if window_start >= num_slides:
            window_start = num_slides - 1

        print(f"      → 매칭 완료, 다음 윈도우 시작: 슬라이드 {window_start + 1}번")

    # 통계
    filled = sum(1 for m in matches if m.utterances)
    print(f"\n   ✅ 슬라이딩 윈도우 매칭 완료: {filled}/{num_slides} 슬라이드에 발화 배정")

    return matches


def split_utterances_into_chunks(
    utterances: list[dict],
    chunk_seconds: int
) -> list[dict]:
    """발화를 시간 기준으로 청크로 분할"""
    if not utterances:
        return []

    chunks = []
    current_chunk = {"start_sec": 0, "end_sec": chunk_seconds, "utterances": []}

    for u in utterances:
        sec = u.get("seconds", 0)
        while sec >= current_chunk["end_sec"]:
            chunks.append(current_chunk)
            new_start = current_chunk["end_sec"]
            current_chunk = {
                "start_sec": new_start,
                "end_sec": new_start + chunk_seconds,
                "utterances": []
            }
        current_chunk["utterances"].append(u)

    if current_chunk["utterances"]:
        chunks.append(current_chunk)

    return chunks


def llm_match_chunk(
    client: anthropic.Anthropic,
    chunk_utterances: list[dict],
    window_slides: list[dict],
    window_offset: int,
    chunk_start_min: float,
    chunk_end_min: float
) -> list[dict]:
    """
    LLM을 사용하여 10분 청크의 발화를 슬라이드 윈도우에 매칭

    Returns:
        list of {"slide_idx": int (0-based global), "utterances": [...], "confidence": str}
    """

    # 발화 내용 구성 (페이지 번호 힌트 포함)
    utterance_lines = []
    page_hints = []
    for i, u in enumerate(chunk_utterances):
        ts = u.get("timestamp", "")
        speaker = u.get("speaker", "")
        content = u.get("content", "")[:300]
        utterance_lines.append(f"[{ts}] {speaker}: {content}")
        if u.get("slide_num"):
            page_hints.append(f"  - [{ts}] 발화가 STT에서 슬라이드 {u['slide_num']}번으로 표시됨")
        if len(utterance_lines) >= 30:
            utterance_lines.append(f"... (외 {len(chunk_utterances) - 30}개 발화)")
            break

    utterance_text = "\n".join(utterance_lines)
    page_hint_text = ""
    if page_hints:
        page_hint_text = "\n## STT 페이지 번호 힌트 (우선 고려):\n" + "\n".join(page_hints) + "\n"

    # 슬라이드 윈도우 구성
    slide_lines = []
    for s in window_slides:
        pnum = s["page_num"]
        text = s.get("text_preview", "")[:300]
        slide_lines.append(f"### 슬라이드 {pnum}번\n{text if text else '(텍스트 없음)'}")

    slides_text = "\n\n".join(slide_lines)

    first_slide = window_slides[0]["page_num"]
    last_slide = window_slides[-1]["page_num"]

    prompt = f"""당신은 강의 슬라이드와 강연 녹취록(STT)을 매칭하는 전문가입니다.

아래는 강의의 **{chunk_start_min:.0f}분 ~ {chunk_end_min:.0f}분** 구간 발화 내용입니다.
이 발화들이 슬라이드 {first_slide}번 ~ {last_slide}번 중 어디에 해당하는지 매칭해주세요.
{page_hint_text}
## 발화 내용 ({chunk_start_min:.0f}~{chunk_end_min:.0f}분):
{utterance_text}

## 슬라이드 윈도우 ({first_slide}~{last_slide}번):
{slides_text}

## 매칭 규칙:
1. 발화 내용과 슬라이드 텍스트의 주제/키워드를 비교하여 매칭
2. STT에 페이지 번호가 표시된 경우 해당 정보를 우선 신뢰
3. 강의는 순서대로 진행되므로, 슬라이드 번호는 대체로 오름차순
4. 하나의 발화는 하나의 슬라이드에만 배정
5. 이 시간대에 해당하지 않는 슬라이드는 빈 배열로

JSON 배열로 답변해주세요. 이 시간대에서 실제로 다룬 슬라이드만 포함:
[
  {{
    "slide_num": 슬라이드 번호,
    "utterance_indices": [이 슬라이드에 해당하는 발화의 인덱스 (0부터 시작)],
    "confidence": "high" | "medium" | "low"
  }},
  ...
]"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text

    # JSON 배열 파싱
    try:
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            result_list = json.loads(json_match.group())
        else:
            print("      ⚠️ JSON 배열 파싱 실패")
            return _fallback_chunk(chunk_utterances, window_offset, window_offset + len(window_slides))
    except json.JSONDecodeError as e:
        print(f"      ⚠️ JSON 파싱 오류: {e}")
        return _fallback_chunk(chunk_utterances, window_offset, window_offset + len(window_slides))

    # 결과 변환
    mapped = []
    for item in result_list:
        slide_num = item.get("slide_num", 0)
        indices = item.get("utterance_indices", [])
        confidence = item.get("confidence", "medium")

        slide_idx = slide_num - 1  # 1-based → 0-based
        selected_utterances = []
        for idx in indices:
            if 0 <= idx < len(chunk_utterances):
                selected_utterances.append(chunk_utterances[idx])

        if selected_utterances:
            mapped.append({
                "slide_idx": slide_idx,
                "utterances": selected_utterances,
                "confidence": confidence
            })

    return mapped


def _fallback_time_based(
    matches: list[SlideMatch],
    utterances: list[dict],
    num_slides: int,
    stt_last_second: float
) -> list[SlideMatch]:
    """API 키 없을 때 시간 기반 균등 분할 폴백"""
    time_per_slide = stt_last_second / num_slides if num_slides else 1
    for u in utterances:
        sec = u.get("seconds", 0)
        idx = min(int(sec / time_per_slide), num_slides - 1)
        matches[idx].utterances.append(u)
    return matches


def _fallback_chunk(
    chunk_utterances: list[dict],
    win_start: int,
    win_end: int
) -> list[dict]:
    """LLM 실패 시 청크 내 발화를 윈도우에 균등 분할"""
    window_size = win_end - win_start
    if window_size <= 0:
        return []

    result = []
    per_slide = max(1, len(chunk_utterances) // window_size)

    for i in range(window_size):
        start = i * per_slide
        end = start + per_slide if i < window_size - 1 else len(chunk_utterances)
        selected = chunk_utterances[start:end]
        if selected:
            result.append({
                "slide_idx": win_start + i,
                "utterances": selected,
                "confidence": "low"
            })

    return result


###############################################################################
# 메인 실행
###############################################################################

def run_matching(output_dir: Path) -> list[SlideMatch]:
    """
    전체 매칭 프로세스 실행 (v2: 슬라이딩 윈도우)
    """
    print("\n" + "=" * 70)
    print("🔄 Step 3: 슬라이드-STT 매칭 시작 (슬라이딩 윈도우)")
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
    mins = re.search(r'(\d+)분', duration_str)
    secs = re.search(r'(\d+)초', duration_str)
    total_seconds = (int(mins.group(1)) * 60 if mins else 0) + (int(secs.group(1)) if secs else 0)
    
    # 슬라이딩 윈도우 매칭 (v2)
    matches = sliding_window_matching(slides_info, stt_data, total_seconds)
    
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
    filled = sum(1 for m in matches if m.utterances)
    
    print("\n" + "-" * 70)
    print("📊 매칭 결과 요약")
    print("-" * 70)
    print(f"   발화 배정 슬라이드:     {filled}/{len(matches)}개")
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
