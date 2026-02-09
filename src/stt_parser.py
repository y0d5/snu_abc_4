#!/usr/bin/env python3
"""
STT 스크립트 파싱 모듈
- 클로바 노트 STT 형식 파싱
- 여러 파일 병합
- 화자/시간/내용 분리
"""

import re
from pathlib import Path
from dataclasses import dataclass, asdict
import json


@dataclass
class Utterance:
    """발화 정보"""
    speaker: str
    timestamp: str  # "MM:SS" 형식
    seconds: int    # 초 단위 변환값
    content: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class STTDocument:
    """파싱된 STT 문서"""
    title: str
    date: str
    duration: str
    participants: list[str]
    utterances: list[Utterance]
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "date": self.date,
            "duration": self.duration,
            "participants": self.participants,
            "utterances": [u.to_dict() for u in self.utterances]
        }
    
    def total_seconds(self) -> int:
        """전체 녹음 시간(초)"""
        if self.utterances:
            return max(u.seconds for u in self.utterances)
        return 0


def parse_timestamp(timestamp: str) -> int:
    """타임스탬프를 초 단위로 변환"""
    parts = timestamp.split(":")
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), int(parts[1])
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    return 0


def parse_stt_file(file_path: Path) -> STTDocument:
    """
    단일 STT 파일 파싱
    
    클로바 노트 형식:
    - 첫 줄: 제목
    - 메타데이터: 날짜, 시간, 참여자
    - 발화: "{화자} {MM:SS}" 다음 줄에 내용
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    
    # 제목 (첫 줄)
    title = lines[0].strip() if lines else ""
    
    # 메타데이터 파싱
    date = ""
    duration = ""
    
    # 날짜/시간 패턴: "2026.02.06 금 오후 6:02 ・ 94분 3초"
    date_pattern = r'(\d{4}\.\d{2}\.\d{2})\s+\S+\s+\S+\s+\d+:\d+\s+・\s+(.+)'
    
    for line in lines[1:20]:  # 상단 메타데이터 영역만 검색
        date_match = re.search(date_pattern, line)
        if date_match:
            date = date_match.group(1)
            duration = date_match.group(2)
            break
    
    # 발화 파싱
    utterances = []
    participants = []  # 발화에서 추출
    
    # 발화 패턴: "화자명 MM:SS" 또는 "화자명 HH:MM:SS"
    utterance_pattern = r'^(.+?)\s+(\d{1,2}:\d{2}(?::\d{2})?)$'
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        match = re.match(utterance_pattern, line)
        if match:
            speaker = match.group(1).strip()
            timestamp = match.group(2)
            
            # 다음 줄들이 내용
            content_lines = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                # 빈 줄이거나 다음 발화 시작이면 중단
                if not next_line or re.match(utterance_pattern, next_line):
                    break
                content_lines.append(next_line)
                i += 1
            
            content = ' '.join(content_lines)
            
            if content:  # 내용이 있는 경우만 추가
                utterance = Utterance(
                    speaker=speaker,
                    timestamp=timestamp,
                    seconds=parse_timestamp(timestamp),
                    content=content
                )
                utterances.append(utterance)
                
                # 화자 목록 업데이트 (발화에서 추출)
                if speaker not in participants:
                    participants.append(speaker)
        else:
            i += 1
    
    return STTDocument(
        title=title,
        date=date,
        duration=duration,
        participants=participants,
        utterances=utterances
    )


def merge_stt_files(file_paths: list[Path]) -> STTDocument:
    """
    여러 STT 파일을 시간순으로 병합
    
    Args:
        file_paths: STT 파일 경로 리스트 (파일명 순서대로 정렬되어 있어야 함)
    
    Returns:
        병합된 STTDocument
    """
    if not file_paths:
        raise ValueError("파일 목록이 비어있습니다.")
    
    # 첫 번째 파일 파싱
    merged = parse_stt_file(file_paths[0])
    
    if len(file_paths) == 1:
        return merged
    
    print(f"\n📝 STT 파일 병합 중...")
    print(f"   파일 1: {file_paths[0].name} ({len(merged.utterances)}개 발화)")
    
    # 나머지 파일들 병합
    time_offset = merged.total_seconds()
    
    for idx, file_path in enumerate(file_paths[1:], 2):
        doc = parse_stt_file(file_path)
        print(f"   파일 {idx}: {file_path.name} ({len(doc.utterances)}개 발화)")
        
        # 시간 오프셋 적용
        for utterance in doc.utterances:
            utterance.seconds += time_offset
            # 타임스탬프도 재계산
            mins, secs = divmod(utterance.seconds, 60)
            utterance.timestamp = f"{mins}:{secs:02d}"
        
        # 병합
        merged.utterances.extend(doc.utterances)
        
        # 참여자 병합
        for p in doc.participants:
            if p not in merged.participants:
                merged.participants.append(p)
        
        # 다음 파일을 위한 오프셋 업데이트
        time_offset = merged.total_seconds()
    
    print(f"   ✅ 총 {len(merged.utterances)}개 발화 병합 완료")
    
    return merged


def save_parsed_stt(doc: STTDocument, output_path: Path) -> None:
    """파싱된 STT를 JSON으로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(doc.to_dict(), f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ STT 저장 위치: {output_path}")


def load_parsed_stt(json_path: Path) -> STTDocument:
    """저장된 JSON에서 STTDocument 로드"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    utterances = [
        Utterance(**u) for u in data['utterances']
    ]
    
    return STTDocument(
        title=data['title'],
        date=data['date'],
        duration=data['duration'],
        participants=data['participants'],
        utterances=utterances
    )


if __name__ == "__main__":
    # 테스트
    import sys
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        doc = parse_stt_file(file_path)
        print(f"\n제목: {doc.title}")
        print(f"날짜: {doc.date}")
        print(f"길이: {doc.duration}")
        print(f"참여자: {doc.participants}")
        print(f"발화 수: {len(doc.utterances)}")
        
        if doc.utterances:
            print(f"\n첫 발화:")
            u = doc.utterances[0]
            print(f"  [{u.timestamp}] {u.speaker}: {u.content[:50]}...")
