#!/usr/bin/env python3
"""
GitHub Pages 배포 스크립트
- output 폴더의 강의 노트를 site 폴더로 복사
- 인덱스 페이지 자동 생성
- Git commit & push
"""

import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import re

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
SITE_DIR = PROJECT_ROOT / "site"


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
    """강의 폴더를 site로 복사 (HTML과 슬라이드만)"""
    src_dir = OUTPUT_DIR / lecture_folder
    dest_dir = SITE_DIR / lecture_folder
    
    # 기존 폴더 삭제
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # HTML 파일 복사
    for html_file in src_dir.glob("*.html"):
        shutil.copy2(html_file, dest_dir / html_file.name)
    
    # slides 폴더 복사
    slides_src = src_dir / "slides"
    if slides_src.exists():
        slides_dest = dest_dir / "slides"
        shutil.copytree(slides_src, slides_dest)
    
    return dest_dir


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
    
    # 번호순 정렬
    lectures.sort(key=lambda x: int(x["num"]) if x["num"].isdigit() else 0)
    
    # HTML 생성
    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SNU ABC 강의 노트 아카이브</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
            color: white;
        }}
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .lecture-grid {{
            display: grid;
            gap: 20px;
        }}
        .lecture-card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            text-decoration: none;
            color: inherit;
            display: block;
        }}
        .lecture-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }}
        .lecture-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 12px;
        }}
        .lecture-num {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.2em;
        }}
        .lecture-title {{
            flex: 1;
        }}
        .lecture-title h2 {{
            font-size: 1.3em;
            color: #333;
            margin-bottom: 4px;
        }}
        .lecture-title .speaker {{
            color: #666;
            font-size: 0.95em;
        }}
        .lecture-date {{
            color: #999;
            font-size: 0.9em;
        }}
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            background: white;
            border-radius: 16px;
            color: #666;
        }}
        footer {{
            text-align: center;
            margin-top: 40px;
            color: white;
            opacity: 0.7;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📚 SNU ABC 강의 노트</h1>
            <p>AI/BigData/Cloud 과정 강의 아카이브</p>
        </header>
        
        <div class="lecture-grid">
'''
    
    if lectures:
        for lecture in lectures:
            html += f'''            <a href="{lecture['folder']}/{lecture['html_file']}" class="lecture-card">
                <div class="lecture-header">
                    <div class="lecture-num">{lecture['num']}</div>
                    <div class="lecture-title">
                        <h2>{lecture['topic']}</h2>
                        <div class="speaker">{lecture['speaker']}</div>
                    </div>
                    <div class="lecture-date">{lecture['date']}</div>
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
            마지막 업데이트: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}
        </footer>
    </div>
</body>
</html>
'''
    
    return html


def deploy_to_site():
    """전체 배포 프로세스"""
    print("🚀 GitHub Pages 배포 시작...")
    
    # site 폴더 생성
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
    return lecture_count


def git_push():
    """Git commit & push"""
    print("\n📤 GitHub에 업로드 중...")
    
    try:
        # site 폴더 추가
        subprocess.run(["git", "add", "site/"], cwd=PROJECT_ROOT, check=True)
        
        # 변경사항 확인
        result = subprocess.run(
            ["git", "status", "--porcelain", "site/"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        
        if not result.stdout.strip():
            print("ℹ️  변경사항이 없습니다.")
            return True
        
        # 커밋
        commit_msg = f"강의 노트 업데이트 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=PROJECT_ROOT,
            check=True
        )
        
        # 푸시
        subprocess.run(["git", "push"], cwd=PROJECT_ROOT, check=True)
        
        print("✅ GitHub 업로드 완료!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git 오류: {e}")
        return False


def full_deploy():
    """전체 배포 (site 생성 + git push)"""
    deploy_to_site()
    return git_push()


if __name__ == "__main__":
    full_deploy()
