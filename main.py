import time
import os
import sys
import subprocess
import requests
from datetime import datetime

# ================= [설정] =================
TARGET_AREAS = [
    "서해중부안쪽먼바다", 
    "충남남부앞바다", 
    "보령시"
]

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
LOG_FILE = "last_sent.txt"
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

def read_last_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def save_current_log(content):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(content)

def crawl_weather_site():
    print(f"[{datetime.now()}] 봇 실행 (이모티콘 헤더 적용 Ver.)")

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
        url = "https://www.weather.go.kr/w/special-report/overall.do"
        driver.get(url)
        driver.implicitly_wait(10)
        time.sleep(2)

        tbody = driver.find_element(By.CSS_SELECTOR, "table tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        
        found_unique_ids = []
        found_details_msg = []
        
        last_type = ""
        last_level = ""

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 2: continue
            
            col_idx = 0
            if len(cols) == 6:
                last_type = cols[0].text.strip()
                last_level = cols[1].text.strip()
                col_idx = 2
            elif len(cols) == 4:
                col_idx = 0

            raw_area_text = cols[col_idx].text.strip()
            announce_time = cols[col_idx+1].text.strip()
            effect_time = cols[col_idx+2].text.strip()
            clear_notice = cols[col_idx+3].text.strip()
            
            matched_targets = []
            for target in TARGET_AREAS:
                if target.replace(" ", "") in raw_area_text.replace(" ", ""):
                    matched_targets.append(target)
            
            if matched_targets:
                clean_area_text = ", ".join(matched_targets)
                unique_id = f"{clean_area_text}_{last_type}_{announce_time}"
                found_unique_ids.append(unique_id)
                
                detail_msg = (
                    f"특보 : {last_type}\n"
                    f"수준 : {last_level}\n"
                    f"해당지역 : {clean_area_text}\n"
                    f"발표시각 : {announce_time}\n"
                    f"발효시각 : {effect_time}\n"
                    f"해제예고 : {clear_notice if clear_notice else '-'}"
                )
                found_details_msg.append(detail_msg)

        current_status_str = "/".join(found_unique_ids)
        last_status_str = read_last_log()

        # [CASE 1] 특보 해제 (무지개 이모티콘 적용)
        if not current_status_str:
            if last_status_str:
                print(">> [해제] 특보가 해제되었습니다.")
                send_telegram_msg("🌈 기상특보 해제 🌈\n\n지정된 구역의 모든 특보가 해제되었습니다.\n(상황 종료)")
                save_current_log("")
            else:
                print(">> 특보 없음")
            return

        # [CASE 2] 중복 체크
        if current_status_str == last_status_str:
             print(">> [중복] 변동 사항 없음.")
             return

        # [CASE 3] 전송 (사이렌 이모티콘 적용!)
        print(">> [전송] 알림 발송")
        
        final_msg_body = "\n\n".join(found_details_msg)
        
        # ★ 수정된 부분: 사이렌 이모티콘 헤더 추가
        head_msg = (
            f"🚨 기상특보 발표 🚨\n\n"
            f"감시구역: {TARGET_AREAS}\n\n"
            f"새로운 특보가 발표되었습니다.\n\n"
            f"{final_msg_body}"
        )
        
        send_telegram_msg(head_msg)
        save_current_log(current_status_str)

    except Exception as e:
        print(f"에러: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_weather_site()
