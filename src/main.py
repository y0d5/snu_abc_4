#!/usr/bin/env python3
"""
강의 노트 자동 정리 프로그램
Step 1: 강의 선택
"""

import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class LectureFolder:
    """강의 폴더 정보를 담는 클래스"""
    path: Path
    name: str
    pdf_files: list[str]
    txt_files: list[str]
    
    @property
    def has_pdf(self) -> bool:
        return len(self.pdf_files) > 0
    
    @property
    def has_txt(self) -> bool:
        return len(self.txt_files) > 0
    
    @property
    def is_ready(self) -> bool:
        """PDF와 TXT 모두 있는지 확인"""
        return self.has_pdf and self.has_txt
    
    def status_str(self) -> str:
        """상태 문자열 반환"""
        pdf_status = f"PDF {len(self.pdf_files)}개" if self.has_pdf else "PDF 없음"
        txt_status = f"TXT {len(self.txt_files)}개" if self.has_txt else "TXT 없음"
        return f"[{pdf_status}, {txt_status}]"


def get_data_folder() -> Path:
    """data 폴더 경로 반환"""
    # 현재 스크립트 위치 기준으로 data 폴더 찾기
    script_dir = Path(__file__).parent.parent
    
    # 'data:' 폴더 (macOS에서 콜론이 붙은 경우)
    data_folder = script_dir / "data:"
    if data_folder.exists():
        return data_folder
    
    # 일반 'data' 폴더
    data_folder = script_dir / "data"
    if data_folder.exists():
        return data_folder
    
    raise FileNotFoundError("data 폴더를 찾을 수 없습니다.")


def scan_lecture_folders(data_folder: Path) -> list[LectureFolder]:
    """data 폴더 내 강의 폴더들을 스캔"""
    lectures = []
    
    for item in sorted(data_folder.iterdir()):
        if not item.is_dir():
            continue
        
        # 숨김 폴더 제외
        if item.name.startswith('.'):
            continue
        
        # PDF와 TXT 파일 찾기
        pdf_files = sorted([f.name for f in item.glob("*.pdf")])
        txt_files = sorted([f.name for f in item.glob("*.txt")])
        
        lecture = LectureFolder(
            path=item,
            name=item.name,
            pdf_files=pdf_files,
            txt_files=txt_files
        )
        lectures.append(lecture)
    
    return lectures


def display_lecture_list(lectures: list[LectureFolder]) -> None:
    """강의 목록을 화면에 표시"""
    print("\n" + "=" * 70)
    print("📚 강의 목록")
    print("=" * 70)
    
    ready_count = 0
    for idx, lecture in enumerate(lectures, 1):
        # 준비 완료된 강의는 다른 표시
        if lecture.is_ready:
            marker = "✅"
            ready_count += 1
        elif lecture.has_pdf:
            marker = "📄"
        else:
            marker = "⚠️"
        
        print(f"  {idx:2d}. {marker} {lecture.name}")
        print(f"      {lecture.status_str()}")
    
    print("-" * 70)
    print(f"총 {len(lectures)}개 강의 중 {ready_count}개 처리 가능 (PDF+TXT 보유)")
    print("=" * 70)


def select_lecture(lectures: list[LectureFolder]) -> LectureFolder | None:
    """사용자로부터 강의 선택 받기"""
    while True:
        print("\n처리할 강의 번호를 입력하세요 (0: 종료): ", end="")
        try:
            user_input = input().strip()
            
            if user_input == '0':
                print("프로그램을 종료합니다.")
                return None
            
            choice = int(user_input)
            
            if 1 <= choice <= len(lectures):
                selected = lectures[choice - 1]
                
                # PDF와 TXT 모두 있는지 확인
                if not selected.has_pdf:
                    print(f"⚠️  '{selected.name}' 폴더에 PDF 파일이 없습니다.")
                    continue
                
                if not selected.has_txt:
                    print(f"⚠️  '{selected.name}' 폴더에 TXT 파일이 없습니다.")
                    print("    STT 스크립트가 필요합니다. 다른 강의를 선택해주세요.")
                    continue
                
                return selected
            else:
                print(f"1부터 {len(lectures)} 사이의 번호를 입력해주세요.")
        
        except ValueError:
            print("올바른 숫자를 입력해주세요.")


def confirm_selection(lecture: LectureFolder) -> bool:
    """선택한 강의 확인"""
    print("\n" + "=" * 70)
    print("📋 선택한 강의 정보")
    print("=" * 70)
    print(f"  폴더명: {lecture.name}")
    print(f"  경로:   {lecture.path}")
    print()
    print("  PDF 파일:")
    for pdf in lecture.pdf_files:
        print(f"    - {pdf}")
    print()
    print("  TXT 파일 (STT 스크립트):")
    for txt in lecture.txt_files:
        print(f"    - {txt}")
    print("=" * 70)
    
    print("\n이 강의를 처리하시겠습니까? (y/n): ", end="")
    confirm = input().strip().lower()
    return confirm in ['y', 'yes', '예', 'ㅇ']


def main():
    """메인 함수"""
    print("\n🎓 강의 노트 자동 정리 프로그램")
    print("=" * 70)
    
    # Step 1-1: data 폴더 찾기
    try:
        data_folder = get_data_folder()
        print(f"📁 데이터 폴더: {data_folder}")
    except FileNotFoundError as e:
        print(f"❌ 오류: {e}")
        return
    
    # Step 1-2: 강의 폴더 스캔
    lectures = scan_lecture_folders(data_folder)
    
    if not lectures:
        print("❌ 강의 폴더가 없습니다.")
        return
    
    # Step 1-3: 강의 목록 표시
    display_lecture_list(lectures)
    
    # Step 1-4: 강의 선택
    selected = select_lecture(lectures)
    
    if selected is None:
        return
    
    # Step 1-5: 선택 확인
    if confirm_selection(selected):
        print("\n✅ 작업 대상 확정!")
        print(f"   → {selected.name}")
        
        # TODO: Step 2로 진행 (PDF/TXT 처리)
        print("\n[다음 단계: PDF 및 TXT 파일 처리]")
    else:
        print("\n취소되었습니다.")


if __name__ == "__main__":
    main()
