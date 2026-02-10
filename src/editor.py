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
from streamlit_image_select import image_select
from streamlit_sortables import sort_items

# 페이지 설정
st.set_page_config(
    page_title="강의 노트 편집기",
    page_icon="📝",
    layout="wide",
    menu_items={}
)

# CSS 스타일
st.markdown("""
<style>
    /* Deploy 버튼과 햄버거 메뉴 숨기기 */
    .stDeployButton, 
    [data-testid="stToolbar"],
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    /* 상단 패딩 줄이기 */
    .block-container {
        padding-top: 0.5rem !important;
    }
    
    /* streamlit-sortables 스타일 오버라이드 */
    div[data-testid="stVerticalBlock"] div[data-baseweb="card"],
    .element-container iframe + div,
    div[class*="sortable"] > div,
    div[draggable="true"] {
        background-color: white !important;
        border: 1px solid #d0d0d0 !important;
        border-radius: 4px !important;
        padding: 12px 14px !important;
        margin-bottom: 8px !important;
        font-size: 14px !important;
        text-align: left !important;
        cursor: grab !important;
        min-height: 50px !important;
        line-height: 1.5 !important;
    }
</style>
""", unsafe_allow_html=True)

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
    """강의 데이터 저장 (버전 백업 포함)"""
    from datetime import datetime
    
    lecture_dir = OUTPUT_DIR / lecture_name
    summary_path = lecture_dir / "lecture_summary.json"
    
    # 버전 백업 폴더 생성
    versions_dir = lecture_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    
    # 타임스탬프로 백업 파일 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = versions_dir / f"lecture_summary_{timestamp}.json"
    
    # 현재 파일 백업 (존재하는 경우)
    if summary_path.exists():
        import shutil
        shutil.copy2(summary_path, backup_path)
    
    # 새 데이터 저장
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 오래된 버전 정리 (최근 20개만 유지)
    versions = sorted(versions_dir.glob("lecture_summary_*.json"), reverse=True)
    for old_version in versions[20:]:
        old_version.unlink()
    
    return len(versions[:20])  # 현재 버전 수 반환


def get_version_list(lecture_name):
    """저장된 버전 목록 조회"""
    lecture_dir = OUTPUT_DIR / lecture_name
    versions_dir = lecture_dir / "versions"
    
    if not versions_dir.exists():
        return []
    
    versions = []
    for f in sorted(versions_dir.glob("lecture_summary_*.json"), reverse=True):
        # 파일명에서 타임스탬프 추출
        ts = f.stem.replace("lecture_summary_", "")
        # 포맷팅: 20260209_143022 -> 2026-02-09 14:30:22
        try:
            formatted = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:15]}"
            versions.append({"file": f.name, "time": formatted, "path": str(f)})
        except:
            versions.append({"file": f.name, "time": ts, "path": str(f)})
    
    return versions


def restore_version(lecture_name, version_path):
    """이전 버전 복원"""
    import shutil
    from datetime import datetime
    
    lecture_dir = OUTPUT_DIR / lecture_name
    summary_path = lecture_dir / "lecture_summary.json"
    versions_dir = lecture_dir / "versions"
    
    # 현재 상태 먼저 백업
    if summary_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = versions_dir / f"lecture_summary_{timestamp}.json"
        shutil.copy2(summary_path, backup_path)
    
    # 선택한 버전으로 복원
    shutil.copy2(version_path, summary_path)
    return True


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


def deploy_to_github():
    """GitHub Pages 배포"""
    import subprocess
    result = subprocess.run(
        ["python3", "deploy.py"],
        cwd=PROJECT_ROOT / "src",
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr


def run_refinement(lecture_name):
    """포인트 재배치 실행"""
    import subprocess
    result = subprocess.run(
        ["python3", "refiner.py", f"../output/{lecture_name}"],
        cwd=PROJECT_ROOT / "src",
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr


# 상단 헤더 영역 (컴팩트하게)
header_col1, header_col2, header_col3, header_col4, header_col5, header_col6 = st.columns([0.6, 3, 0.6, 0.7, 0.8, 0.8])

lectures = get_available_lectures()

if not lectures:
    st.error("편집할 강의가 없습니다. 먼저 강의 노트를 생성해주세요.")
    st.stop()

with header_col2:
    selected_lecture = st.selectbox(
        "강의 선택",
        lectures,
        format_func=lambda x: x.split("-")[1] + " - " + "-".join(x.split("-")[2:-1]) if len(x.split("-")) > 3 else x,
        label_visibility="collapsed"
    )

with header_col1:
    # 편집 중인 슬라이드 수 표시
    edit_count = len([k for k in st.session_state.get('slide_edits', {}).keys() if k.startswith(selected_lecture + '_')]) if 'slide_edits' in st.session_state else 0
    if edit_count > 0:
        st.markdown(f"**📝 ({edit_count})**")
    else:
        st.markdown("**📚**")

# 데이터 로드
if 'data' not in st.session_state or st.session_state.get('current_lecture') != selected_lecture:
    st.session_state.data = load_lecture_data(selected_lecture)
    st.session_state.current_lecture = selected_lecture
    # 강의 변경 시 편집 버퍼 초기화
    st.session_state.slide_edits = {}

data = st.session_state.data

with header_col3:
    if st.button("💾 저장", type="primary", use_container_width=True):
        # 먼저 모든 content_ 키에서 slide_edits로 동기화
        if 'slide_edits' not in st.session_state:
            st.session_state.slide_edits = {}
        
        for key in list(st.session_state.keys()):
            if key.startswith('content_'):
                try:
                    s_num = int(key.replace('content_', ''))
                    edit_key = f"{selected_lecture}_{s_num}"
                    st.session_state.slide_edits[edit_key] = st.session_state[key]
                except ValueError:
                    pass
        
        # 편집 버퍼의 모든 내용을 data에 적용
        for edit_key, edited_text in st.session_state.slide_edits.items():
            # edit_key 형식: "{lecture_name}_{slide_num}"
            parts = edit_key.rsplit('_', 1)
            if len(parts) == 2 and parts[0] == selected_lecture:
                try:
                    slide_num = int(parts[1])
                    slide_idx = slide_num - 1
                    if 0 <= slide_idx < len(data['summaries']):
                        # 텍스트를 포인트 목록으로 파싱
                        if edited_text.strip():
                            raw_points = edited_text.split('\n\n')
                            new_points = []
                            for p in raw_points:
                                cleaned = ' '.join(line.strip() for line in p.split('\n') if line.strip())
                                if cleaned.startswith('•') or cleaned.startswith('-') or cleaned.startswith('*'):
                                    cleaned = cleaned[1:].strip()
                                if cleaned:
                                    new_points.append(cleaned)
                            data['summaries'][slide_idx]['key_points'] = new_points
                        else:
                            data['summaries'][slide_idx]['key_points'] = []
                except ValueError:
                    pass
        
        version_count = save_lecture_data(selected_lecture, data)
        # 저장 후 편집 버퍼 및 content_ 키 초기화
        st.session_state.slide_edits = {}
        for key in list(st.session_state.keys()):
            if key.startswith('content_'):
                del st.session_state[key]
        st.toast(f"저장되었습니다! (버전 {version_count}개 보관중)", icon="✅")

with header_col4:
    if st.button("🔄 HTML", use_container_width=True):
        with st.spinner("HTML 생성 중..."):
            if regenerate_html(selected_lecture):
                st.toast("HTML이 재생성되었습니다!", icon="✅")
            else:
                st.toast("HTML 생성 실패", icon="❌")

with header_col5:
    if st.button("🔄 재배치", use_container_width=True, help="LLM으로 포인트 재배치"):
        st.session_state.show_refinement = True
        st.rerun()

# 재배치 실행 (별도 처리)
if st.session_state.get('show_refinement'):
    del st.session_state['show_refinement']
    
    with st.status("🔄 포인트 재배치 중...", expanded=True) as status:
        st.write("📊 슬라이드 분석 중...")
        st.write("⏳ LLM이 뒤 슬라이드부터 검토합니다 (1-2분 소요)")
        
        success, output = run_refinement(selected_lecture)
        
        if success:
            status.update(label="✅ 재배치 완료!", state="complete", expanded=True)
            
            # 로그 파일에서 변경 내역 읽기
            log_path = OUTPUT_DIR / selected_lecture / "refinement_log.json"
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as f:
                    movements = json.load(f)
                
                if movements:
                    st.success(f"**{len(movements)}개 포인트가 재배치되었습니다!**")
                    st.write("변경 내역:")
                    for m in movements[:10]:  # 최대 10개만 표시
                        st.write(f"- 슬라이드 {m['from']} → {m['to']}: {m['point']}")
                    if len(movements) > 10:
                        st.write(f"... 외 {len(movements) - 10}개")
                else:
                    st.info("재배치가 필요한 포인트가 없습니다.")
            else:
                st.info("재배치가 필요한 포인트가 없습니다.")
            
            st.write("")
            st.write("💡 **재배치 결과는 자동 저장되었습니다.** 새로고침해도 유지됩니다.")
            
            # 데이터 다시 로드
            st.session_state.data = load_lecture_data(selected_lecture)
        else:
            status.update(label="❌ 재배치 실패", state="error")
            st.error(output)

with header_col6:
    if st.button("🚀 GitHub", use_container_width=True):
        with st.spinner("GitHub에 배포 중..."):
            success, output = deploy_to_github()
            if success:
                st.toast("GitHub Pages에 배포되었습니다!", icon="✅")
            else:
                st.toast("배포 실패 - 터미널 확인", icon="❌")

# 메인 영역 탭
tab1, tab2, tab3, tab4 = st.tabs(["📊 슬라이드별 내용", "💬 Q&A", "🎯 Key Takeaways", "📁 버전 관리"])

# 탭 1: 슬라이드별 내용
with tab1:
    # 슬라이드 선택
    num_slides = len(data['summaries'])
    
    # 모든 슬라이드 이미지 경로 수집 (먼저 준비)
    slide_images = []
    slide_captions = []
    for i in range(1, num_slides + 1):
        img_path = OUTPUT_DIR / selected_lecture / "slides" / f"slide_{i:03d}.png"
        if img_path.exists():
            slide_images.append(str(img_path))
            slide_captions.append(str(i))
    
    # 선택된 슬라이드 초기화
    if 'selected_slide' not in st.session_state:
        st.session_state.selected_slide = 1
    
    # 3컬럼 레이아웃: 썸네일 | 큰 이미지 | 편집 영역
    thumb_col, img_col, edit_col = st.columns([1.2, 2, 2.8])
    
    # 왼쪽: 썸네일 목록 (스크롤 가능)
    with thumb_col:
        # 스크롤 가능한 썸네일 컨테이너
        thumb_container = st.container(height=700)
        
        with thumb_container:
            # 이미지 선택 컴포넌트 - 선택 시 자동 반영 (rerun 없음)
            if slide_images:
                selected_path = image_select(
                    label="",
                    images=slide_images,
                    captions=slide_captions,
                    index=st.session_state.selected_slide - 1,
                    use_container_width=True,
                    key="slide_selector"
                )
                
                # 선택된 이미지에서 슬라이드 번호 추출
                if selected_path in slide_images:
                    new_slide_num = slide_images.index(selected_path) + 1
                    prev_slide_num = st.session_state.selected_slide
                    
                    # 슬라이드 변경 시 이전 슬라이드의 편집 내용 저장
                    if new_slide_num != prev_slide_num:
                        prev_content_key = f"content_{prev_slide_num}"
                        if prev_content_key in st.session_state:
                            prev_edit_key = f"{selected_lecture}_{prev_slide_num}"
                            if 'slide_edits' not in st.session_state:
                                st.session_state.slide_edits = {}
                            st.session_state.slide_edits[prev_edit_key] = st.session_state[prev_content_key]
                    
                    slide_num = new_slide_num
                    st.session_state.selected_slide = slide_num
                else:
                    slide_num = st.session_state.selected_slide
            else:
                slide_num = 1
    
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
        # 편집 버퍼 초기화 (슬라이드별 편집 내용 저장)
        if 'slide_edits' not in st.session_state:
            st.session_state.slide_edits = {}
        
        # 모든 content_ 키에서 slide_edits로 동기화 (슬라이드 변경 시 이전 편집 내용 보존)
        for key in list(st.session_state.keys()):
            if key.startswith('content_'):
                try:
                    s_num = int(key.replace('content_', ''))
                    sync_edit_key = f"{selected_lecture}_{s_num}"
                    st.session_state.slide_edits[sync_edit_key] = st.session_state[key]
                except ValueError:
                    pass
        
        # 현재 슬라이드 데이터
        slide_idx = slide_num - 1
        current_summary = data['summaries'][slide_idx]
        
        st.markdown(f"**슬라이드 {slide_num} 주요 내용**")
        
        # 편집 버퍼에 있으면 버퍼에서, 없으면 원본 데이터에서 가져오기
        edit_key = f"{selected_lecture}_{slide_num}"
        if edit_key not in st.session_state.slide_edits:
            # 원본 데이터로 초기화
            key_points = list(current_summary.get('key_points', []))
            st.session_state.slide_edits[edit_key] = "\n\n".join(key_points) if key_points else ""
        
        # 현재 슬라이드의 초기값 결정 (버퍼에서)
        initial_value = st.session_state.slide_edits[edit_key]
        
        # 하나의 큰 텍스트 영역으로 편집
        edited_text = st.text_area(
            "주요 내용 편집",
            value=initial_value,
            height=400,
            key=f"content_{slide_num}",
            label_visibility="collapsed",
            placeholder="포인트 1\n\n포인트 2\n\n포인트 3\n\n(빈 줄로 포인트 구분)"
        )
        
        # 편집 내용을 버퍼에 저장
        st.session_state.slide_edits[edit_key] = edited_text
        
        # 편집된 텍스트를 다시 포인트 목록으로 파싱 (빈 줄로 구분)
        if edited_text.strip():
            # 빈 줄(2개 이상 연속 줄바꿈)로 분리
            raw_points = edited_text.split('\n\n')
            new_points = []
            
            for p in raw_points:
                # 각 포인트 정리 (줄바꿈을 공백으로)
                cleaned = ' '.join(line.strip() for line in p.split('\n') if line.strip())
                # 불릿 기호 제거
                if cleaned.startswith('•') or cleaned.startswith('-') or cleaned.startswith('*'):
                    cleaned = cleaned[1:].strip()
                if cleaned:
                    new_points.append(cleaned)
        else:
            new_points = []
        
        # 데이터 업데이트 (메모리상에서만, 저장은 버튼 클릭 시)
        data['summaries'][slide_idx]['key_points'] = new_points
        
        st.caption("💡 빈 줄로 포인트 구분 | 여러 슬라이드 편집 후 한꺼번에 저장 가능")

# 탭 2: Q&A
with tab2:
    st.header("Q&A 편집")
    
    qa_section = data.get('qa_section', [])
    
    # 삭제할 Q&A 인덱스 추적
    if 'qa_to_delete' not in st.session_state:
        st.session_state.qa_to_delete = set()
    
    if not qa_section:
        st.info("Q&A 내용이 없습니다. 아래에서 새로 추가할 수 있습니다.")
    
    new_qa_section = []
    
    for i, qa in enumerate(qa_section):
        # 삭제 예정인 항목은 건너뛰기
        if i in st.session_state.qa_to_delete:
            continue
            
        with st.expander(f"Q{i+1}: {qa.get('question', '')[:50]}...", expanded=False):
            col_q, col_del = st.columns([6, 1])
            
            with col_del:
                if st.button("🗑️ 삭제", key=f"del_qa_{i}", type="secondary"):
                    st.session_state.qa_to_delete.add(i)
                    st.rerun()
            
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
    
    st.divider()
    
    # 새 Q&A 추가
    st.subheader("➕ 새 Q&A 추가")
    new_q = st.text_area("새 질문", key="new_qa_q", height=80, placeholder="질문을 입력하세요...")
    new_a = st.text_area("새 답변", key="new_qa_a", height=120, placeholder="답변을 입력하세요...")
    
    if new_q.strip() and new_a.strip():
        new_qa_section.append({
            'question': new_q.strip(),
            'answer': new_a.strip()
        })
    
    data['qa_section'] = new_qa_section
    
    st.caption("💡 Q&A를 삭제하려면 각 항목의 '삭제' 버튼을 클릭하세요. 저장 버튼을 눌러야 최종 반영됩니다.")

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

# 탭 4: 버전 관리
with tab4:
    st.header("버전 관리")
    st.caption("저장할 때마다 자동으로 백업됩니다. 최근 20개 버전이 보관됩니다.")
    
    versions = get_version_list(selected_lecture)
    
    if not versions:
        st.info("아직 저장된 버전이 없습니다. '💾 저장' 버튼을 눌러 첫 버전을 만들어보세요.")
    else:
        st.write(f"**저장된 버전: {len(versions)}개**")
        
        for i, v in enumerate(versions):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(f"📄 {v['time']}")
            with col2:
                if st.button("복원", key=f"restore_{i}", type="secondary"):
                    if restore_version(selected_lecture, v['path']):
                        st.toast(f"버전 복원됨: {v['time']}", icon="✅")
                        # 데이터 다시 로드
                        st.session_state.data = load_lecture_data(selected_lecture)
                        st.rerun()
        
        st.divider()
        st.warning("⚠️ 복원 시 현재 상태가 자동 백업된 후 선택한 버전으로 되돌아갑니다.")
