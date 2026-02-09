#!/usr/bin/env python3
"""
강의 노트 웹 편집기 (Streamlit)
- 슬라이드별 핵심 내용 수정
- Q&A 수정
- Key Takeaways 수정
- HTML 재생성
"""

import streamlit as st
import json
from pathlib import Path
import base64

# 페이지 설정
st.set_page_config(
    page_title="강의 노트 편집기",
    page_icon="📝",
    layout="wide"
)

# 프로젝트 경로
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


def get_available_lectures():
    """사용 가능한 강의 목록 반환"""
    lectures = []
    if OUTPUT_DIR.exists():
        for folder in sorted(OUTPUT_DIR.iterdir()):
            if folder.is_dir() and (folder / "lecture_summary.json").exists():
                lectures.append(folder.name)
    return lectures


def load_lecture_data(lecture_name):
    """강의 데이터 로드"""
    lecture_dir = OUTPUT_DIR / lecture_name
    summary_path = lecture_dir / "lecture_summary.json"
    
    with open(summary_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_lecture_data(lecture_name, data):
    """강의 데이터 저장"""
    lecture_dir = OUTPUT_DIR / lecture_name
    summary_path = lecture_dir / "lecture_summary.json"
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_slide_image(lecture_name, slide_num):
    """슬라이드 이미지를 base64로 반환"""
    img_path = OUTPUT_DIR / lecture_name / "slides" / f"slide_{slide_num:03d}.png"
    if img_path.exists():
        with open(img_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    return None


def regenerate_html(lecture_name):
    """HTML 재생성"""
    import subprocess
    result = subprocess.run(
        ["python3", "generator.py", f"../output/{lecture_name}"],
        cwd=PROJECT_ROOT / "src",
        capture_output=True,
        text=True
    )
    return result.returncode == 0


# 사이드바 - 강의 선택
st.sidebar.title("📚 강의 노트 편집기")

lectures = get_available_lectures()

if not lectures:
    st.error("편집할 강의가 없습니다. 먼저 강의 노트를 생성해주세요.")
    st.stop()

selected_lecture = st.sidebar.selectbox(
    "강의 선택",
    lectures,
    format_func=lambda x: x.split("-")[1] + " - " + "-".join(x.split("-")[2:-1]) if len(x.split("-")) > 3 else x
)

# 데이터 로드
if 'data' not in st.session_state or st.session_state.get('current_lecture') != selected_lecture:
    st.session_state.data = load_lecture_data(selected_lecture)
    st.session_state.current_lecture = selected_lecture

data = st.session_state.data

# 사이드바 - 저장 버튼
st.sidebar.divider()

if st.sidebar.button("💾 저장", type="primary", use_container_width=True):
    save_lecture_data(selected_lecture, data)
    st.sidebar.success("저장되었습니다!")

if st.sidebar.button("🔄 HTML 재생성", use_container_width=True):
    with st.spinner("HTML 생성 중..."):
        if regenerate_html(selected_lecture):
            st.sidebar.success("HTML이 재생성되었습니다!")
        else:
            st.sidebar.error("HTML 생성 실패")

# 메인 영역 탭
tab1, tab2, tab3 = st.tabs(["📊 슬라이드별 내용", "💬 Q&A", "🎯 Key Takeaways"])

# 탭 1: 슬라이드별 내용
with tab1:
    # 슬라이드 선택
    num_slides = len(data['summaries'])
    
    # 선택된 슬라이드 초기화
    if 'selected_slide' not in st.session_state:
        st.session_state.selected_slide = 1
    
    slide_num = st.session_state.selected_slide
    
    # 3컬럼 레이아웃: 썸네일 | 큰 이미지 | 편집 영역
    thumb_col, img_col, edit_col = st.columns([1, 2, 3])
    
    # 왼쪽: 썸네일 목록 (스크롤 가능)
    with thumb_col:
        st.markdown("**슬라이드 목록**")
        
        # 스크롤 가능한 썸네일 컨테이너
        thumb_container = st.container(height=600)
        
        with thumb_container:
            for i in range(1, num_slides + 1):
                thumb_b64 = get_slide_image(selected_lecture, i)
                
                if thumb_b64:
                    # 선택된 슬라이드는 테두리 굵게
                    if i == slide_num:
                        border_style = "border: 4px solid #FF4B4B; border-radius: 8px;"
                    else:
                        border_style = "border: 1px solid #ddd; border-radius: 4px;"
                    
                    # 썸네일 클릭 버튼
                    if st.button(
                        f"#{i}",
                        key=f"thumb_{i}",
                        use_container_width=True
                    ):
                        st.session_state.selected_slide = i
                        st.rerun()
                    
                    # 썸네일 이미지 표시
                    st.markdown(
                        f'<img src="data:image/png;base64,{thumb_b64}" style="width:100%; {border_style}">',
                        unsafe_allow_html=True
                    )
                    st.markdown("---")
    
    # 중간: 선택된 슬라이드 큰 이미지
    with img_col:
        st.markdown(f"**슬라이드 {slide_num}**")
        img_b64 = get_slide_image(selected_lecture, slide_num)
        if img_b64:
            st.image(f"data:image/png;base64,{img_b64}", use_container_width=True)
        else:
            st.warning("이미지 없음")
    
    # 오른쪽: 편집 영역
    with edit_col:
        # 현재 슬라이드 데이터
        slide_idx = slide_num - 1
        current_summary = data['summaries'][slide_idx]
        
        st.markdown(f"**슬라이드 {slide_num} 주요 내용**")
        
        # 핵심 포인트 편집
        key_points = current_summary.get('key_points', [])
        
        # 기존 포인트 수정
        new_points = []
        for i, point in enumerate(key_points):
            edited = st.text_area(
                f"포인트 {i+1}",
                value=point,
                key=f"point_{slide_num}_{i}",
                height=80
            )
            if edited.strip():
                new_points.append(edited.strip())
        
        # 새 포인트 추가
        new_point = st.text_area(
            "➕ 새 포인트 추가",
            value="",
            key=f"new_point_{slide_num}",
            height=80,
            placeholder="새로운 핵심 포인트를 입력하세요..."
        )
        if new_point.strip():
            new_points.append(new_point.strip())
        
        # 데이터 업데이트
        data['summaries'][slide_idx]['key_points'] = new_points
        
        # 포인트 삭제 버튼
        if key_points:
            st.caption("포인트를 삭제하려면 내용을 비우고 저장하세요.")

# 탭 2: Q&A
with tab2:
    st.header("Q&A 편집")
    
    qa_section = data.get('qa_section', [])
    
    if not qa_section:
        st.info("Q&A 내용이 없습니다.")
    
    new_qa_section = []
    
    for i, qa in enumerate(qa_section):
        with st.expander(f"Q{i+1}: {qa.get('question', '')[:50]}...", expanded=False):
            q = st.text_area(
                "질문",
                value=qa.get('question', ''),
                key=f"qa_q_{i}",
                height=100
            )
            a = st.text_area(
                "답변",
                value=qa.get('answer', ''),
                key=f"qa_a_{i}",
                height=150
            )
            
            if q.strip() or a.strip():
                new_qa_section.append({
                    'question': q.strip(),
                    'answer': a.strip()
                })
    
    # 새 Q&A 추가
    st.subheader("➕ 새 Q&A 추가")
    new_q = st.text_area("새 질문", key="new_qa_q", height=80)
    new_a = st.text_area("새 답변", key="new_qa_a", height=120)
    
    if new_q.strip() and new_a.strip():
        new_qa_section.append({
            'question': new_q.strip(),
            'answer': new_a.strip()
        })
    
    data['qa_section'] = new_qa_section

# 탭 3: Key Takeaways
with tab3:
    st.header("Key Takeaways 편집")
    
    takeaways = data.get('key_takeaways', [])
    
    new_takeaways = []
    
    for i, takeaway in enumerate(takeaways):
        edited = st.text_area(
            f"Takeaway {i+1}",
            value=takeaway,
            key=f"takeaway_{i}",
            height=100
        )
        if edited.strip():
            new_takeaways.append(edited.strip())
    
    # 새 Takeaway 추가
    new_takeaway = st.text_area(
        "➕ 새 Key Takeaway 추가",
        value="",
        key="new_takeaway",
        height=100,
        placeholder="새로운 Key Takeaway를 입력하세요..."
    )
    if new_takeaway.strip():
        new_takeaways.append(new_takeaway.strip())
    
    data['key_takeaways'] = new_takeaways

# 하단 안내
st.divider()
st.caption("💡 수정 후 '저장' 버튼을 클릭하면 JSON 파일이 업데이트됩니다. 'HTML 재생성'을 클릭하면 최종 문서가 새로 만들어집니다.")
