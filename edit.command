#!/bin/bash
# 강의 노트 웹 편집기 실행 스크립트

cd "$(dirname "$0")"
source VENV/bin/activate

echo "🚀 웹 편집기를 시작합니다..."
echo "   브라우저가 자동으로 열립니다."
echo "   종료하려면 Ctrl+C를 누르세요."
echo ""

streamlit run src/editor.py --server.headless true
