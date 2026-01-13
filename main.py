import time
import os
import requests
from datetime import datetime

# 크롤링 도구
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ================= [설정] =================
TARGET_AREAS = ["서해중부안쪽먼바다", "충남남부앞바다"]
# GitHub Secrets에서 가져올 텔레그램 키
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
LOG_FILE = "last_sent.txt"
# =========================================

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(">> 텔레그램 설정이 없습니다.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    try:
        requests.get(url, params=params)
        print(">> 텔레그램 전송 성공!")
    except Exception as e:
        print(f">> 전송 에러: {e}")

def read_last_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def save_current_log(content):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(content)

def crawl_weather_site():
    print(f"[{datetime.now()}] 텔레그램 봇 작동 시작")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        url = "https://www.weather.go.kr/w/special-report/overall.do"
        driver.get(url)
        driver.implicitly_wait(10)
        time.sleep(2)

        tbody = driver.find_element(By.CSS_SELECTOR, "table tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        found_data = []

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 2: continue
            col_idx = 0
            if len(cols) == 6:
                col_idx = 2
            elif len(cols) == 4: col_idx = 0

            area = cols[col_idx].text.strip()
            announce = cols[col_idx+1].text.strip()
            
            for target in TARGET_AREAS:
                if target.replace(" ", "") in area.replace(" ", ""):
                    unique_id = f"{target}_{announce}"
                    found_data.append(unique_id)

        current_status = "/".join(found_data)
        last_status = read_last_log()

        # 1. 특보 해제 (있다가 없어짐)
        if not current_status:
            if last_status:
                print(">> [해제] 모든 특보 해제됨.")
                send_telegram_msg("🌈 기상특보 해제 🌈\n\n모든 특보가 해제되었습니다.\n(상황 종료)")
                save_current_log("")
            else:
                print(">> 특보 없음 (평온)")
            return

        # 2. 특보 발생/유지
        if current_status == last_status:
            print(f">> [중복] 이미 알린 내용입니다.")
        else:
            print(f">> [신규] 특보 발견! 텔레그램 전송.")
            msg = f"🚨 기상특보 발효 🚨\n\n구역: {TARGET_AREAS}\n\n새로운 특보가 발표되었습니다.\n기상청 홈페이지를 확인하세요."
            send_telegram_msg(msg)
            save_current_log(current_status)

    except Exception as e:
        print(f"에러: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_weather_site()
