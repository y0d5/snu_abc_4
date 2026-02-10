#!/usr/bin/env python3
"""
포인트 재배치 모듈
- 뒤 슬라이드부터 역순으로 검토
- 앞 슬라이드에 잘못 배치된 포인트를 적합한 슬라이드로 이동
"""

import json
import sys
from pathlib import Path
from anthropic import Anthropic

# 버퍼링 없이 즉시 출력
sys.stdout.reconfigure(line_buffering=True)

PROJECT_ROOT = Path(__file__).parent.parent


def load_env_file():
    """수동으로 .env 파일 로드"""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    import os
                    os.environ[key.strip()] = value.strip()


def load_data(output_dir):
    """강의 데이터 로드"""
    summary_path = output_dir / "lecture_summary.json"
    slides_path = output_dir / "slides_info.json"
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        summary_data = json.load(f)
    
    with open(slides_path, 'r', encoding='utf-8') as f:
        slides_info = json.load(f)
    
    return summary_data, slides_info


def save_data(output_dir, summary_data):
    """강의 데이터 저장"""
    summary_path = output_dir / "lecture_summary.json"
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)


def find_misplaced_points(client, slide_text, slide_num, earlier_slides_points):
    """
    현재 슬라이드 내용을 기준으로 앞 슬라이드에서 가져와야 할 포인트 찾기
    
    Args:
        client: Anthropic 클라이언트
        slide_text: 현재 슬라이드의 텍스트 (제목, 내용)
        slide_num: 현재 슬라이드 번호
        earlier_slides_points: 앞 슬라이드들의 포인트 목록 [{slide_num, point_idx, point_text}, ...]
    
    Returns:
        이동해야 할 포인트 목록 [{from_slide, point_idx, point_text}, ...]
    """
    if not earlier_slides_points:
        return []
    
    # 앞 슬라이드 포인트 목록 생성
    points_list = "\n".join([
        f"[슬라이드 {p['slide_num']}, 포인트 {p['point_idx']+1}] {p['point_text'][:200]}"
        for p in earlier_slides_points
    ])
    
    prompt = f"""당신은 강의 노트 정리 전문가입니다.

현재 슬라이드 {slide_num}의 내용:
---
{slide_text[:1000]}
---

아래는 이전 슬라이드들(1~{slide_num-1})에 배치된 포인트들입니다:
---
{points_list}
---

위 포인트들 중에서 "슬라이드 {slide_num}의 내용과 직접적으로 관련되어 있어서 슬라이드 {slide_num}으로 이동해야 할 포인트"가 있는지 확인하세요.

판단 기준:
1. 포인트가 현재 슬라이드의 주제/키워드와 명확히 일치하는 경우만 이동
2. 일반적인 도입부나 개요 설명은 이동하지 않음
3. 애매한 경우 이동하지 않음 (보수적으로 판단)

응답 형식 (JSON):
{{"move": [
  {{"from_slide": 슬라이드번호, "point_idx": 포인트인덱스(0부터), "reason": "이동 이유"}}
]}}

이동할 포인트가 없으면:
{{"move": []}}
"""
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result_text = response.content[0].text.strip()
        
        # JSON 추출
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result.get('move', [])
        
    except Exception as e:
        print(f"    ⚠️ LLM 오류: {e}")
    
    return []


def run_refinement(output_dir):
    """포인트 재배치 실행"""
    print("🔄 포인트 재배치 시작...")
    
    # API 키 로드
    load_env_file()
    import os
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    
    if not api_key:
        print("❌ ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return False
    
    client = Anthropic(api_key=api_key)
    
    # 데이터 로드
    output_path = Path(output_dir)
    summary_data, slides_info = load_data(output_path)
    
    summaries = summary_data['summaries']
    num_slides = len(summaries)
    
    print(f"  📊 총 {num_slides}개 슬라이드 분석")
    
    # 이동 기록
    movements = []
    
    # 뒤에서부터 역순으로 검토 (마지막 슬라이드부터)
    for slide_idx in range(num_slides - 1, 0, -1):  # 마지막 ~ 2번째 슬라이드
        slide_num = slide_idx + 1
        
        # 현재 슬라이드 텍스트
        slide_info = slides_info[slide_idx]
        slide_text = slide_info.get('text', '')
        
        if not slide_text.strip():
            continue
        
        # 앞 슬라이드들의 포인트 수집
        earlier_points = []
        for earlier_idx in range(slide_idx):
            points = summaries[earlier_idx].get('key_points', [])
            for point_idx, point_text in enumerate(points):
                if point_text.strip():
                    earlier_points.append({
                        'slide_num': earlier_idx + 1,
                        'point_idx': point_idx,
                        'point_text': point_text
                    })
        
        if not earlier_points:
            continue
        
        # 10개 슬라이드마다 진행 상황 출력
        if slide_num % 10 == 0 or slide_num == num_slides:
            print(f"  🔍 슬라이드 {slide_num}/{num_slides} 검토 중...")
        
        # LLM으로 잘못 배치된 포인트 찾기
        misplaced = find_misplaced_points(client, slide_text, slide_num, earlier_points)
        
        for item in misplaced:
            from_slide = item['from_slide']
            point_idx = item['point_idx']
            reason = item.get('reason', '')
            
            # 유효성 검사
            if from_slide < 1 or from_slide >= slide_num:
                continue
            
            from_idx = from_slide - 1
            from_points = summaries[from_idx].get('key_points', [])
            
            if point_idx < 0 or point_idx >= len(from_points):
                continue
            
            # 포인트 이동
            point_text = from_points[point_idx]
            
            # 원래 위치에서 제거
            summaries[from_idx]['key_points'].pop(point_idx)
            
            # 새 위치에 추가
            summaries[slide_idx]['key_points'].append(point_text)
            
            movements.append({
                'from': from_slide,
                'to': slide_num,
                'point': point_text[:50] + '...' if len(point_text) > 50 else point_text,
                'reason': reason
            })
            
            print(f"    ✅ 슬라이드 {from_slide} → {slide_num}: {point_text[:40]}...")
    
    # 결과 저장
    if movements:
        save_data(output_path, summary_data)
        print(f"\n✅ 완료: {len(movements)}개 포인트 재배치됨")
        
        # 이동 로그 저장
        log_path = output_path / "refinement_log.json"
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(movements, f, ensure_ascii=False, indent=2)
        print(f"  📝 로그 저장: {log_path.name}")
    else:
        print("\n✅ 완료: 재배치가 필요한 포인트가 없습니다.")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        # 가장 최근 output 폴더 찾기
        output_base = PROJECT_ROOT / "output"
        if output_base.exists():
            folders = sorted([f for f in output_base.iterdir() if f.is_dir()])
            if folders:
                output_dir = str(folders[-1])
            else:
                print("❌ output 폴더에 강의가 없습니다.")
                sys.exit(1)
        else:
            print("❌ output 폴더가 없습니다.")
            sys.exit(1)
    
    run_refinement(output_dir)
