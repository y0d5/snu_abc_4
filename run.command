#!/bin/bash
# 강의 노트 자동 정리 프로그램 실행 스크립트

cd "$(dirname "$0")"
source VENV/bin/activate
python3 src/main.py

echo ""
echo "프로그램이 종료되었습니다. 아무 키나 누르면 창이 닫힙니다."
read -n 1
