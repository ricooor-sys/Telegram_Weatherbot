import time
import os
import sys
import subprocess
import requests
from datetime import datetime

# ================= [사용자 설정] =================
TARGET_AREAS = ["서해중부안쪽먼바다", "충남남부앞바다"]

# ★ 사용자님의 계정 정보 적용 완료
TELEGRAM_TOKEN = "8503312839:AAE6ZdkIWuEZ7uoaMA_vICVcqaV8Y-xHRl8"
TELEGRAM_CHAT_ID = "-1003552260995"
GOOGLE_SHEET_URL = ""  # 구글 시트는 사용하지 않음

LOG_FILE = "last_sent.txt"
# =================================================

def install_heavy_libraries():
    """작동하는 시간에만 무거운 라이브러리 설치"""
    try:
        import selenium
        import webdriver_manager
    except ImportError:
        print(">> [설치] 필요한 라이브러리가 없어 설치합니다...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium", "webdriver-manager"])

def send_telegram_msg(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
        print(">> [전송 실패] 토큰이나 채팅 ID가 없습니다.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        res = requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": text})
        if res.status_code == 200:
            print(">> 텔레그램 전송 성공!")
        else:
            print(f">> 전송 실패: {res.text}")
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

def should_i_run():
    """
    [핵심 로직]
    1. 현재 특보가 발효 중인가? (last_sent.txt 확인) -> 무조건 실행 (15분 간격)
    2. 특보가 없는가? -> 현재 시각이 '정시(0분)' 근처일 때만 실행 (1시간 간격)
    """
    last_status = read_last_log()
    
    # [조건 1] 특보 발효 중 (응급 모드)
    if last_status:
        print(">> [🚨 비상 모드] 현재 특보가 발효 중입니다. 15분 간격으로 정밀 감시합니다.")
        return True
    
    # [조건 2] 특보 없음 (평시 모드)
    now_minute = datetime.now().minute
    # 깃허브 액션이 0분, 15분, 30분, 45분에 실행됨.
    # 그 중 '0분'에 실행된 경우(약 0~9분 사이)에만 작동 허용
    if now_minute < 10:
        print(f">> [🕒 정기 점검] 1시간 간격 정기 점검 시간입니다. ({now_minute}분)")
        return True
        
    print(f">> [💤 대기] 현재 {now_minute}분입니다. 특보가 없어 정시까지 대기합니다.")
    return False

def crawl_weather_site():
    print(f"[{datetime.now()}] 기상 감시 봇 가동 확인...")

    # 1. 실행 여부 결정 (지능형 스케줄러)
    if not should_i_run():
        return # 지금은 일할 때가 아니므로 즉시 종료

    # 2. 여기서부터 진짜 일 시작 (라이브러리 로드)
    install_heavy_libraries()
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    print(">> [작동] 기상청 정보를 확인합니다...")
    
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

            area_text = cols[col_idx].text.strip()
            announce_time = cols[col_idx+1].text.strip()
            effect_time = cols[col_idx+2].text.strip()
            clear_notice = cols[col_idx+3].text.strip()
            
            for target in TARGET_AREAS:
                if target.replace(" ", "") in area_text.replace(" ", ""):
                    unique_id = f"{target}_{last_type}_{announce_time}"
                    found_unique_ids.append(unique_id)
                    
                    detail_msg = (
                        f"특보 : {last_type}\n"
                        f"수준 : {last_level}\n"
                        f"해당지역 : {area_text}\n"
                        f"발표시각 : {announce_time}\n"
                        f"발효시각 : {effect_time}\n"
                        f"해제예고 : {clear_notice if clear_notice else '-'}"
                    )
                    found_details_msg.append(detail_msg)

        current_status_str = "/".join(found_unique_ids)
        last_status_str = read_last_log()

        # [CASE 1] 특보 해제 (비상 모드 -> 평시 모드 전환)
        if not current_status_str:
            if last_status_str:
                print(">> [해제] 특보 해제 확인. 평시 모드(1시간 간격)로 복귀합니다.")
                send_telegram_msg("🌈 기상특보 해제 🌈\n\n지정된 구역의 모든 특보가 해제되었습니다.\n\n(1시간 간격 감시로 복귀)")
                save_current_log("")
            else:
                print(">> 특보 없음 (이상 무)")
            return

        # [CASE 2] 중복 체크
        if current_status_str == last_status_str:
             print(">> [중복] 이미 보낸 특보입니다. (15분 뒤 재확인)")
             return

        # [CASE 3] 신규 특보 발생 (평시 모드 -> 비상 모드 진입)
        print(">> [전송] 신규 특보 발생! 비상 모드(15분 간격)로 전환합니다.")
        
        final_msg_body = "\n\n".join(found_details_msg)
        head_msg = (
            f"감시구역: {TARGET_AREAS}\n\n"
            f"새로운 특보가 발표되었습니다.\n"
            f"{final_msg_body}"
        )
        
        send_telegram_msg(head_msg)
        save_current_log(current_status_str)

    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_weather_site()
