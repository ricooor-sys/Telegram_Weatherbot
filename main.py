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
        # ★ 여기가 오류가 났던 부분입니다. 잘리지 않게 조심하세요!
        url = "https://www.weather.go.kr/w/special-report/overall.do"
        
        driver.get(url)
        driver.implicitly_wait(10)
        time.sleep(2)

        tbody = driver.find_element(By.CSS_SELECTOR, "table tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        
        current_data = {}
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
            
            for target in TARGET_AREAS:
                if target.replace(" ", "") in raw_area_text.replace(" ", ""):
                    unique_key = f"{target}_{last_type}"
                    current_data[unique_key] = {
                        "area": target,
                        "type": last_type,
                        "level": last_level,
                        "announce": announce_time,
                        "effective": effect_time,
                        "clear": clear_notice if clear_notice else "-"
                    }

        # 데이터 비교 로직
        last_data = read_last_data()
        
        released_items = []
        for key, val in last_data.items():
            if key not in current_data:
                released_items.append(f"* {val['area']} {val['type']} {val['level']} 해제")

        active_messages = []
        is_changed = False 

        for key, curr_val in current_data.items():
            prev_val = last_data.get(key)
            
            display_level = curr_val['level']
            display_announce = curr_val['announce']
            display_effective = curr_val['effective']
            display_clear = curr_val['clear']

            if prev_val:
                if curr_val['level'] != prev_val['level']:
                    display_level += "(Update)"
                    is_changed = True
                if curr_val['announce'] != prev_val['announce']:
                    display_announce += "(Update)"
                    is_changed = True
                if curr_val['effective'] != prev_val['effective']:
                    display_effective += "(Update)"
                    is_changed = True
                if curr_val['clear'] != prev_val['clear']:
                    display_clear += "(Update)"
                    is_changed = True
            else:
                is_changed = True # 신규 특보

            msg_chunk = (
                f"특보 : {curr_val['type']}\n"
                f"수준 : {display_level}\n"
                f"해당지역 : {curr_val['area']}\n"
                f"발표시각 : {display_announce}\n"
                f"발효시각 : {display_effective}\n"
                f"해제예고 : {display_clear}"
            )
            active_messages.append(msg_chunk)

        if released_items:
            is_changed = True

        # 전송 로직
        if not current_data and not released_items:
            print(">> 특보 없음")
            save_current_data({})
            return

        if not is_changed:
            print(">> [중복] 변동 사항 없음.")
            return

        if not current_data and released_items:
            print(">> [전송] 전체 해제 알림")
            released_str = "\n".join(released_items)
            final_msg = (
                "🌈 기상특보 해제 🌈\n\n"
                "지정된 구역의 모든 특보가 해제되었습니다.\n"
                f"{released_str}\n"
                "(상황 종료)"
            )
            send_telegram_msg(final_msg)
            save_current_data({})
            return

        print(">> [전송] 특보 현황 알림")
        body_str = "\n\n".join(active_messages)
        footer_str = ""
        if released_items:
            footer_str = "\n\n" + "\n".join(released_items)

        final_msg = (
            "🚨 기상특보 발표 🚨\n\n"
            f"감시구역: {TARGET_AREAS}\n\n"
            "새로운 특보가 발표되었습니다.\n\n"
            f"{body_str}"
            f"{footer_str}"
        )
        
        send_telegram_msg(final_msg)
        save_current_data(current_data)

    except Exception as e:
        print(f"에러: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_weather_site()
