#!/usr/bin/env python3
"""
PDF 처리 모듈
- PDF 파일을 슬라이드 이미지로 변환
- PDF에서 텍스트 추출
"""

import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass


@dataclass
class SlideInfo:
    """슬라이드 정보"""
    page_num: int
    image_path: Path
    text: str


def process_pdf(pdf_path: Path, output_dir: Path, dpi: int = 150) -> list[SlideInfo]:
    """
    PDF 파일을 처리하여 슬라이드 이미지와 텍스트 추출
    
    Args:
        pdf_path: PDF 파일 경로
        output_dir: 출력 디렉토리 (slides 폴더가 생성됨)
        dpi: 이미지 해상도 (기본 150)
    
    Returns:
        SlideInfo 리스트
    """
    slides_dir = output_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    
    slides = []
    
    print(f"\n📄 PDF 처리 중: {pdf_path.name}")
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    print(f"   총 {total_pages}페이지")
    
    for page_num in range(total_pages):
        page = doc[page_num]
        
        # 이미지로 변환
        zoom = dpi / 72  # 72 DPI가 기본
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)
        
        # 이미지 저장
        image_filename = f"slide_{page_num + 1:03d}.png"
        image_path = slides_dir / image_filename
        pixmap.save(str(image_path))
        
        # 텍스트 추출
        text = page.get_text()
        
        slide = SlideInfo(
            page_num=page_num + 1,
            image_path=image_path,
            text=text.strip()
        )
        slides.append(slide)
        
        # 진행률 표시 (10페이지마다)
        if (page_num + 1) % 10 == 0 or page_num + 1 == total_pages:
            print(f"   → {page_num + 1}/{total_pages} 페이지 완료")
    
    doc.close()
    
    print(f"   ✅ 이미지 저장 위치: {slides_dir}")
    
    return slides


def process_multiple_pdfs(pdf_paths: list[Path], output_dir: Path, dpi: int = 150) -> list[SlideInfo]:
    """
    여러 PDF 파일을 순서대로 처리
    
    Args:
        pdf_paths: PDF 파일 경로 리스트 (순서대로 병합됨)
        output_dir: 출력 디렉토리
        dpi: 이미지 해상도
    
    Returns:
        전체 SlideInfo 리스트
    """
    all_slides = []
    slide_offset = 0
    
    for pdf_path in pdf_paths:
        slides = process_pdf(pdf_path, output_dir, dpi)
        
        # 슬라이드 번호 재조정 (여러 PDF 병합 시)
        for slide in slides:
            slide.page_num += slide_offset
            # 이미지 파일명도 재조정
            new_image_name = f"slide_{slide.page_num:03d}.png"
            new_image_path = slide.image_path.parent / new_image_name
            if slide.image_path != new_image_path:
                slide.image_path.rename(new_image_path)
                slide.image_path = new_image_path
        
        slide_offset += len(slides)
        all_slides.extend(slides)
    
    return all_slides


if __name__ == "__main__":
    # 테스트
    import sys
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
        output_dir = Path("output/test")
        slides = process_pdf(pdf_path, output_dir)
        print(f"\n총 {len(slides)}개 슬라이드 처리 완료")
