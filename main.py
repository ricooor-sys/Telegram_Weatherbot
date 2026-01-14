# (위쪽 import 부분과 send_telegram_msg 함수 등은 그대로 두세요)

def crawl_weather_site():
    print(f"[{datetime.now()}] 텔레그램 봇 작동 시작")
    
    # ... (크롬 드라이버 설정 부분 생략, 그대로 두세요) ...
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

        # 1. 특보 해제 또는 없음 (수정된 부분!)
        if not current_status:
            if last_status:
                print(">> [해제] 모든 특보 해제됨.")
                send_telegram_msg("🌈 기상특보 해제 🌈\n\n모든 특보가 해제되었습니다.\n(상황 종료)")
                save_current_log("")
            else:
                print(">> 특보 없음 (생존 신고 발송)")
                # ★ 여기가 추가된 부분입니다!
                send_telegram_msg("✅ [정상 작동 중]\n\n현재 서해안 지역에\n발효 중인 특보가 없습니다.\n\n(이상 무!)")
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
