"""Vercel Python serverless entry — FastAPI ASGI app 자동 감지."""
import sys
import os

# server/ 를 import path 에 추가 (api/index.py 에서 main 모듈 찾기 위함)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: F401  (Vercel 이 이 모듈의 'app' 을 ASGI 로 감지)
