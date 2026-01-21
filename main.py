import time
import os
import sys
import subprocess
import requests
import json
from datetime import datetime

# ================= [설정] =================
TARGET_AREAS = [
    "서해중부안쪽먼바다", 
    "충남남부앞바다", 
    "보령시"
]

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
LOG_FILE = "last_sent_data.json" # ★ 중요: json 파일 사용
# =========================================

def install_heavy_libraries():
    try:
        import selenium
        import webdriver_manager
    except ImportError:
        print(">> [설치] 라이브러리 설치 중...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium", "webdriver-manager"])

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": text})
    except: pass

def read_last_data():
    """이전 상태를 JSON 딕셔너리로 불러옴"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_current_data(data_dict):
    """현재 상태를 JSON으로 저장"""
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=4)

def crawl_weather_site():
    print(f"[{datetime.now()}] 봇 실행 (Update/해제 추적 Ver.)")

    install_heavy_libraries()
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        url = "
