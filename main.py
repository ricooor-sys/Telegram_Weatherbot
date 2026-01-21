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
# 파일명을 json으로 변경 (중요)
LOG_FILE = "last_sent_data.json"
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
    """저장된 이전 데이터를 불러옵니다"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_current_data(data_dict):
    """현재 데이터를 파일로 저장합니다"""
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data_dict, f, ensure_ascii=False, indent=4)

def crawl_weather_site():
    print(f"[{datetime.now()}] 봇 실행 (JSON 저장 및 Update 표시 기능)")

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
        # [수정] 오타 없이 주소 입력
        url = "https://www.weather.go.kr/w/special-report/overall.do"
        driver.get(url)
        driver.implicitly_wait(10)
        time.sleep(2)

        tbody = driver.find_element(By.CSS_SELECTOR, "table tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        
        current_data = {}
        last_type = ""
        last_level = ""

        # 1. 현재 기상청 데이터 수집
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
                # 공백 제거 비교로 정확도 향상
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

        # 2. 과거 데이터와 비교 (Update 및 해제 감지)
        last_data = read_last_data()
        
        # 해제된 항목 찾기 (이전엔 있었는데 지금은 없는 키)
        released_items = []
        for key, val in last_data.items():
            if key not in current_data:
                released_items.append(f"* {val['area']} {val['type']} {val['level']} 해제")

        active_messages = []
        is_changed = False 

        # 현재 항목들 순회하며 변동 체크
        for key, curr_val in current_data.items():
            prev_val = last_data.get(key)
            
            display_level = curr_val['level']
            display_announce = curr_val['announce']
            display_effective = curr_val['effective']
            display_clear = curr_val['clear']

            # 이전 기록이 있다면 비교 시작
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
                # 새로운 특보면 무조건 변경으로 간주
                is_changed = True

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

        # 3. 전송 여부 판단 및 메시지 발송
        
        # [상황 1] 아무 특보도 없고, 해제된 것도 없음 -> 조용히 저장만 하고 끝
        if not current_data and not released_items:
            print(">> 특보 없음")
            save_current_data({})
            return

        # [상황 2] 변동 사항 없음 -> 전송 안 함
        if not is_changed:
            print(">> [중복] 변동 사항 없음.")
            # 데이터는 최신화해서 저장해둠 (혹시 모를 오류 방지)
            save_current_data(current_data)
            return

        # [상황 3] 전체 해제 발생 -> 해제 알림 전송
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

        # [상황 4] 신규/변경/부분해제 -> 상세 알림 전송
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
        
        # ★ 중요: (Update) 글자가 없는 '원본 데이터'를 저장해야 다음 비교가 정확함
        save_current_data(current_data)

    except Exception as e:
        print(f"에러 발생: {e}")
        # 에러 나도 텔레그램으로 알려주면 좋음 (디버깅용)
        # send_telegram_msg(f"⚠️ 봇 오류 발생: {e}") 
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_weather_site()
