#!/usr/bin/env python3
"""
강의 노트 배포 스크립트
- output 폴더의 강의 노트를 docs 폴더로 복사
- 인덱스 페이지 자동 생성
- Netlify 배포 (또는 로컬 폴더 내보내기)
"""

import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import re

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
SITE_DIR = PROJECT_ROOT / "docs"


def get_lecture_info(folder_name):
    """폴더명에서 강의 정보 추출"""
    # 형식: 번호-강사-주제-날짜 (예: 12-이헌준-Computing System for AI-260206)
    parts = folder_name.split("-")
    if len(parts) >= 4:
        num = parts[0]
        speaker = parts[1]
        topic = "-".join(parts[2:-1])
        date_str = parts[-1]
        
        # 날짜 포맷팅 (260206 -> 2026.02.06)
        if len(date_str) == 6:
            formatted_date = f"20{date_str[:2]}.{date_str[2:4]}.{date_str[4:]}"
        else:
            formatted_date = date_str
        
        return {
            "num": num,
            "speaker": speaker,
            "topic": topic,
            "date": formatted_date,
            "folder": folder_name
        }
    return None


def copy_lecture_to_site(lecture_folder):
    """강의 폴더를 site로 복사 (HTML과 슬라이드만, PNG→JPEG 압축)"""
    src_dir = OUTPUT_DIR / lecture_folder
    dest_dir = SITE_DIR / lecture_folder
    
    # 기존 폴더 삭제
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # HTML 파일 복사 (이미지 경로 .png → .jpg 치환)
    for html_file in src_dir.glob("*.html"):
        content = html_file.read_text(encoding='utf-8')
        content = content.replace('.png"', '.jpg"').replace(".png'", ".jpg'")
        (dest_dir / html_file.name).write_text(content, encoding='utf-8')
    
    # slides 폴더 복사 (PNG → JPEG 압축 변환)
    slides_src = src_dir / "slides"
    if slides_src.exists():
        slides_dest = dest_dir / "slides"
        slides_dest.mkdir(parents=True, exist_ok=True)
        compress_slides_to_jpeg(slides_src, slides_dest)
    
    return dest_dir


def compress_slides_to_jpeg(src_dir, dest_dir, quality=82, max_width=1280):
    """슬라이드 PNG 이미지를 JPEG로 압축 변환 (GitHub 파일 크기 제한 대응)"""
    try:
        from PIL import Image as PILImage
    except ImportError:
        print("   ⚠️ Pillow 미설치 - PNG 원본 복사")
        shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
        return
    
    png_files = sorted(src_dir.glob("*.png"))
    total = len(png_files)
    
    for i, png_path in enumerate(png_files):
        jpg_name = png_path.stem + ".jpg"
        jpg_path = dest_dir / jpg_name
        
        try:
            img = PILImage.open(png_path)
            
            # RGBA → RGB 변환 (JPEG는 알파 채널 미지원)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = PILImage.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 너무 큰 이미지는 리사이즈
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), PILImage.LANCZOS)
            
            img.save(jpg_path, 'JPEG', quality=quality, optimize=True)
            
        except Exception as e:
            # 변환 실패 시 원본 PNG 복사
            print(f"   ⚠️ {png_path.name} 변환 실패: {e}, 원본 복사")
            shutil.copy2(png_path, dest_dir / png_path.name)
        
        if (i + 1) % 20 == 0 or (i + 1) == total:
            print(f"   → 슬라이드 압축: {i + 1}/{total}")
    
    print(f"   ✅ {total}개 슬라이드 JPEG 압축 완료")


def generate_index_page():
    """인덱스 페이지 생성"""
    lectures = []
    
    # 모든 강의 폴더 스캔
    if OUTPUT_DIR.exists():
        for folder in sorted(OUTPUT_DIR.iterdir()):
            if folder.is_dir():
                # HTML 파일 찾기
                html_files = list(folder.glob("*.html"))
                if html_files:
                    info = get_lecture_info(folder.name)
                    if info:
                        info["html_file"] = html_files[0].name
                        lectures.append(info)
    
    # 최신순 정렬 (번호 내림차순)
    lectures.sort(key=lambda x: int(x["num"]) if x["num"].isdigit() else 0, reverse=True)
    
    # HTML 생성 (심플한 학교 스타일)
    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>서울대학교 빅데이터 AI CEO 과정 4기 - 강의 노트</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Malgun Gothic', '맑은 고딕', sans-serif;
            background: #f0f0f0;
            min-height: 100vh;
            padding: 40px 20px;
            color: #333;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #003366;
        }}
        header h1 {{
            font-size: 1.6em;
            color: #003366;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        header p {{
            font-size: 0.95em;
            color: #666;
        }}
        .lecture-list {{
            background: white;
            border: 1px solid #ddd;
        }}
        .lecture-item {{
            display: block;
            padding: 16px 20px;
            border-bottom: 1px solid #eee;
            text-decoration: none;
            color: inherit;
            transition: background 0.15s;
        }}
        .lecture-item:last-child {{
            border-bottom: none;
        }}
        .lecture-item:hover {{
            background: #f8f8f8;
        }}
        .lecture-info {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .lecture-title {{
            font-size: 1em;
            color: #003366;
        }}
        .lecture-title:hover {{
            text-decoration: underline;
        }}
        .lecture-meta {{
            font-size: 0.85em;
            color: #888;
        }}
        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            color: #666;
        }}
        .copyright-notice {{
            font-size: 0.8em;
            color: #666;
            line-height: 1.5;
            margin-top: 12px;
            padding: 12px 16px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        footer {{
            text-align: center;
            margin-top: 30px;
            color: #999;
            font-size: 0.8em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>서울대학교 빅데이터 AI CEO 과정 4기 - 강의 노트</h1>
            <p class="copyright-notice">본 웹페이지의 모든 강의 자료 및 요약본은 서울대 빅데이터 AI CEO 과정(SNU ABC) 4기의 소중한 학술 자산입니다. 교수님들의 지적 재산권 보호를 위해 외부 유출 및 무단 전재를 엄격히 금지합니다.</p>
        </header>
        
        <div class="lecture-list">
'''
    
    if lectures:
        for lecture in lectures:
            html += f'''            <a href="{lecture['folder']}/{lecture['html_file']}" class="lecture-item">
                <div class="lecture-info">
                    <span class="lecture-title">{lecture['num']}. {lecture['topic']} - {lecture['speaker']}</span>
                    <span class="lecture-meta">{lecture['date']}</span>
                </div>
            </a>
'''
    else:
        html += '''            <div class="empty-state">
                <p>아직 등록된 강의 노트가 없습니다.</p>
            </div>
'''
    
    html += f'''        </div>
        
        <footer>
            마지막 업데이트: {datetime.now().strftime('%Y.%m.%d %H:%M')}
        </footer>
    </div>
</body>
</html>
'''
    
    return html


def deploy_to_site():
    """전체 배포 프로세스 (docs 폴더 생성)"""
    print("🚀 강의 노트 배포 준비 시작...")
    
    # docs 폴더 생성
    SITE_DIR.mkdir(exist_ok=True)
    
    # 각 강의 폴더 복사
    lecture_count = 0
    if OUTPUT_DIR.exists():
        for folder in OUTPUT_DIR.iterdir():
            if folder.is_dir() and list(folder.glob("*.html")):
                print(f"  📁 {folder.name} 복사 중...")
                copy_lecture_to_site(folder.name)
                lecture_count += 1
    
    # 인덱스 페이지 생성
    print("  📄 인덱스 페이지 생성 중...")
    index_html = generate_index_page()
    (SITE_DIR / "index.html").write_text(index_html, encoding='utf-8')
    
    print(f"✅ {lecture_count}개 강의 노트 준비 완료!")
    print(f"📂 배포 폴더: {SITE_DIR}")
    return lecture_count


def netlify_deploy(production=False):
    """Netlify 배포"""
    print("\n📤 Netlify에 배포 중...")
    
    try:
        # netlify-cli 설치 확인
        result = subprocess.run(
            ["which", "netlify"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("⚠️  Netlify CLI가 설치되어 있지 않습니다.")
            print("   설치: npm install -g netlify-cli")
            print("   로그인: netlify login")
            return False
        
        # 배포 명령어
        cmd = ["netlify", "deploy", "--dir", str(SITE_DIR)]
        if production:
            cmd.append("--prod")
            print("   🔴 프로덕션 배포")
        else:
            print("   🟡 미리보기 배포 (--prod 없이)")
        
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        
        if result.returncode == 0:
            print("✅ Netlify 배포 완료!")
            return True
        else:
            print("❌ Netlify 배포 실패")
            return False
        
    except Exception as e:
        print(f"❌ 배포 오류: {e}")
        return False


def full_deploy(production=False):
    """전체 배포 (docs 폴더 생성 + Netlify 배포)"""
    deploy_to_site()
    return netlify_deploy(production=production)


if __name__ == "__main__":
    import sys
    prod = "--prod" in sys.argv
    full_deploy(production=prod)
