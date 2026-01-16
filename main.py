import time
import os
import sys
import subprocess
import requests
import csv
from io import StringIO
from datetime import datetime

# ================= [설정] =================
TARGET_AREAS = ["서해중부안쪽먼바다", "충남남부앞바다"]
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_SHEET_URL = os.environ.get('GOOGLE_SHEET_URL')
LOG_FILE = "last_sent.txt"
# =========================================

def install_heavy_libraries():
    """작동하는 시간에만 무거운 라이브러리 설치"""
    print(">> [설치] 작업을 수행합니다. Selenium 설치 중...")
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

def get_interval_for_today():
    """구글 시트 확인 (기본 180분, 특정일 15분)"""
    if not GOOGLE_SHEET_URL: return 180 # 기본값

    try:
        res = requests.get(GOOGLE_SHEET_URL)
        res.raise_for_status()
        f = StringIO(res.text)
        reader = csv.reader(f)
        rows = list(reader)
        
        default_interval = 180
        if len(rows) > 0 and len(rows[0]) >= 2:
            try: default_interval = int(rows[0][1])
            except: pass

        today_str = datetime.now().strftime("%m월 %d일")
        
        for row in rows:
            if len(row) < 2: continue
            if row[0].strip() == today_str:
                try:
                    return int(row[1].strip())
                except: pass
        return default_interval

    except:
        return 180

def should_i_run(interval_minutes):
    now = datetime.now()
    total_minutes = now.hour * 60 + now.minute
    closest_schedule = round(total_minutes / 15) * 15
    return closest_schedule % interval_minutes == 0

def crawl_weather_site():
    print(f"[{datetime.now()}] 봇 실행 시작 (상세 정보 Ver.)")

    # 1. 스케줄 확인
    interval = get_interval_for_today()
    if not should_i_run(interval):
        print(f">> [대기] 현재 설정 간격: {interval}분 / 실행 타이밍 아님.")
        return

    # 2. 설치 및 로드
    install_heavy_libraries()
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    print(">> [작동] 날씨 감시를 시작합니다.")
    
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
        
        found_unique_ids = []   # 중복 방지용 ID 저장
        found_details_msg = []  # 텔레그램으로 보낼 상세 내용 저장
        
        # 이전 행의 특보 종류/수준을 기억하기 위한 변수 (병합된 셀 대응)
        last_type = ""
        last_level = ""

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 2: continue
            
            col_idx = 0
            # 6칸짜리 행: 특보종류, 수준이 새로 나옴
            if len(cols) == 6:
                last_type = cols[0].text.strip()
                last_level = cols[1].text.strip()
                col_idx = 2
            # 4칸짜리 행: 특보종류, 수준이 위와 동일 (병합됨)
            elif len(cols) == 4:
                col_idx = 0

            # 데이터 추출
            area_text = cols[col_idx].text.strip()          # 해당지역
            announce_time = cols[col_idx+1].text.strip()    # 발표시각
            effect_time = cols[col_idx+2].text.strip()      # 발효시각
            clear_notice = cols[col_idx+3].text.strip()     # 해제예고
            
            # 내가 원하는 지역인지 확인
            for target in TARGET_AREAS:
                # 공백 제거 후 비교 (서해 중부 -> 서해중부)
                if target.replace(" ", "") in area_text.replace(" ", ""):
                    
                    # 1. 중복 체크용 ID 생성 (지역_특보종류_발표시각)
                    unique_id = f"{target}_{last_type}_{announce_time}"
                    found_unique_ids.append(unique_id)
                    
                    # 2. 메시지 본문 작성 (요청하신 포맷)
                    detail_msg = (
                        f"특보 : {last_type}\n"
                        f"수준 : {last_level}\n"
                        f"발표시각 : {announce_time}\n"
                        f"발효시각 : {effect_time}\n"
                        f"해제예고 : {clear_notice if clear_notice else '-'}"
                    )
                    found_details_msg.append(detail_msg)

        # ================= [알림 로직] =================
        current_status_str = "/".join(found_unique_ids) # ID들을 합쳐서 현재 상태 문자열 생성
        last_status_str = read_last_log()

        # [CASE 1] 특보가 하나도 없을 때 (해제됨)
        if not current_status_str:
            if last_status_str:
                # 이전에는 있었는데 지금은 없다 -> 해제 알림!
                print(">> [해제] 특보가 해제되었습니다.")
                send_telegram_msg("🌈 기상특보 해제 🌈\n\n지정된 구역의 모든 특보가 해제되었습니다.\n(상황 종료)")
                save_current_log("") # 로그 초기화
            else:
                print(">> 특보 없음 (조용히 종료)")
            return

        # [CASE 2] 특보가 있는데, 지난번과 똑같을 때 (중복)
        # if current_status_str == last_status_str:
        #    print(">> [중복] 이미 보낸 특보입니다. 전송 생략.")
        #    return

        # [CASE 3] 새로운 특보 발견! (메시지 전송)
        print(">> [신규] 상세 정보를 텔레그램으로 전송합니다.")
        
        # 여러 개의 특보가 있을 수 있으므로 하나로 합침
        final_msg_body = "\n\n----------------------------------\n\n".join(found_details_msg)
        
        head_msg = (
            f"🚨 기상특보 발표 🚨\n\n"
            f"구역: {TARGET_AREAS}\n\n"
            f"새로운 특보가 발표되었습니다.\n\n"
            f"{final_msg_body}\n\n"
            f"----------------------------------"
        )
        
        send_telegram_msg(head_msg)
        save_current_log(current_status_str) # 현재 상태 저장

    except Exception as e:
        print(f"에러: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_weather_site()
