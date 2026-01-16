import time
import os
import sys
import subprocess
import requests
from datetime import datetime

# ================= [설정] =================
TARGET_AREAS = ["서해중부안쪽먼바다", "충남남부앞바다"]

# ★ 중요: 직접 적지 말고 os.environ.get으로 변경! (보안 필수)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
LOG_FILE = "last_sent.txt"
# =========================================

# ... (나머지 코드는 그대로 두시면 됩니다) ...
# ... (install_heavy_libraries, send_telegram_msg 등 기존 로직 유지) ...

def install_heavy_libraries():
    try:
        import selenium
        import webdriver_manager
    except ImportError:
        print(">> [설치] 필요한 라이브러리가 없어 설치합니다...")
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

def should_i_run():
    last_status = read_last_log()
    if last_status:
        print(">> [🚨 비상] 특보 발효 중 -> 15분 간격 감시")
        return True
    
    now_minute = datetime.now().minute
    if now_minute < 10:
        print(f">> [🕒 정기] 1시간 간격 점검 시간 ({now_minute}분)")
        return True
        
    print(f">> [💤 대기] 특보 없음. 정시까지 대기 ({now_minute}분)")
    return False

def crawl_weather_site():
    print(f"[{datetime.now()}] 봇 실행 시작")
    if not should_i_run(): return

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
        
        last_type, last_level = "", ""

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 2: continue
            col_idx = 0
            if len(cols) == 6:
                last_type, last_level = cols[0].text.strip(), cols[1].text.strip()
                col_idx = 2
            elif len(cols) == 4: col_idx = 0

            area, announce = cols[col_idx].text.strip(), cols[col_idx+1].text.strip()
            effect, clear = cols[col_idx+2].text.strip(), cols[col_idx+3].text.strip()
            
            for target in TARGET_AREAS:
                if target.replace(" ", "") in area.replace(" ", ""):
                    unique_id = f"{target}_{last_type}_{announce}"
                    found_unique_ids.append(unique_id)
                    found_details_msg.append(
                        f"특보 : {last_type}\n수준 : {last_level}\n해당지역 : {area}\n"
                        f"발표시각 : {announce}\n발효시각 : {effect}\n해제예고 : {clear if clear else '-'}"
                    )

        current_status = "/".join(found_unique_ids)
        last_status = read_last_log()

        if not current_status:
            if last_status:
                send_telegram_msg("🌈 기상특보 해제 🌈\n\n지정된 구역의 모든 특보가 해제되었습니다.")
                save_current_log("")
            return

        if current_status == last_status: return

        head_msg = f"감시구역: {TARGET_AREAS}\n\n새로운 특보가 발표되었습니다.\n" + "\n\n".join(found_details_msg)
        send_telegram_msg(head_msg)
        save_current_log(current_status)

    except Exception as e: print(f"에러: {e}")
    finally: driver.quit()

if __name__ == "__main__":
    crawl_weather_site()
