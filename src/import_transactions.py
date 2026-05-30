from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
import pandas as pd
from datetime import datetime
import time 
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import os
import subprocess
from dotenv import load_dotenv
load_dotenv()

# ================== FUNCTIONS ==================

def get_chrome_user_data_dir():
    path = os.environ.get('CHROME_USER_DATA_DIR')
    if not path:
        raise ValueError('CHROME_USER_DATA_DIR is not set in .env')
    if not os.path.isabs(path):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(project_root, path)
    os.makedirs(path, exist_ok=True)
    return path

def clear_stale_chrome_lock(user_data_dir):
    lock_path = os.path.join(user_data_dir, 'SingletonLock')
    if not os.path.lexists(lock_path):
        return

    def remove_lock_files():
        for name in ('SingletonLock', 'SingletonCookie', 'SingletonSocket'):
            stale_path = os.path.join(user_data_dir, name)
            if os.path.lexists(stale_path):
                os.remove(stale_path)

    try:
        lock_target = os.readlink(lock_path)
        pid = int(lock_target.rsplit('-', 1)[-1])
        os.kill(pid, 0)

        result = subprocess.run(['ps', '-p', str(pid), '-o', 'args='], capture_output=True, text=True)
        cmdline = result.stdout.strip()
        if '--enable-automation' in cmdline:
            os.kill(pid, 9)
            time.sleep(1)
            remove_lock_files()
            return

        raise RuntimeError(
            'Chrome is already running with this profile. '
            'Close that Chrome window, then run the script again.'
        )
    except ProcessLookupError:
        remove_lock_files()

def init_driver():
    user_data_dir = get_chrome_user_data_dir()
    clear_stale_chrome_lock(user_data_dir)

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument(f'user-data-dir={user_data_dir}')
    chrome_options.add_argument('--profile-directory=Default')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-default-browser-check')
    if os.environ.get('ENV') == 'docker':
        driver = webdriver.Remote(
            "http://chrome:4444/wd/hub", 
            DesiredCapabilities.CHROME,
            options=chrome_options
        )
    else:
        driver = webdriver.Chrome(options=chrome_options)
    driver.get("https://web.moneylover.me/")
    return driver

def wait_for_xpath(xpath, driver, timeout=20):
    return WebDriverWait(driver, timeout).until(expected_conditions.presence_of_element_located((By.XPATH, xpath)))

def is_logged_in(driver):
    try:
        WebDriverWait(driver, 5).until(
            expected_conditions.presence_of_element_located(
                (By.XPATH, '//button[.//*[contains(text(), "Thêm giao dịch")]]')
            )
        )
        return True
    except:
        return False

def wait_for_login_page(driver):
    WebDriverWait(driver, 30).until(
        lambda d: is_logged_in(d) or d.find_elements(
            By.XPATH, '//form//input[@type="text" or @type="email"]'
        )
    )

def login(driver):
    wait_for_login_page(driver)
    if is_logged_in(driver):
        print("Already logged in")
        return

    email = wait_for_xpath('//form//input[@type="text" or @type="email"]', driver)
    email.clear()
    email.send_keys(os.environ.get('MONEYLOVER_USER_NAME'))
    password = wait_for_xpath('//input[@type="password"]', driver)
    password.clear()
    password.send_keys(os.environ.get('MONEYLOVER_PASSWORD'))
    click_when_clickable('//form//button[contains(., "LOGIN") or contains(., "Login")]', driver)
    wait_for_xpath('//button[.//*[contains(text(), "Add transaction")]]', driver, timeout=30)

def click_when_clickable(xpath, driver, scrollIntoView=False):
    element = wait_for_xpath(xpath, driver)
    if scrollIntoView:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
    try:
        WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable(element)).click()
    except:
        element.click()

def enter_text(xpath, text, driver):
    element = wait_for_xpath(xpath, driver)
    element.send_keys(text)

def parse_date(cell):
    # check if cell is a timestamp
    if isinstance(cell, datetime):
        return cell.year, cell.strftime("%b"), cell.day
    try:
        date = datetime.strptime(cell, '%d/%m/%Y')
    except:
        date = datetime.strptime(cell, '%d-%b-%Y')
    return date.year, date.strftime("%b"), date.day

def parse_amount(row):
    if 'Change' in row:
        return abs(row['Change'])
    elif float(str(row['Withdraw']).replace(',', '')) > 0:
        return str(row['Withdraw']).replace(',', '')
    else:
        return str(row['Deposit']).replace(',', '')

# ================== VALIDATION ==================

valid_categories = [
    'Ăn uống',
    'Hoá đơn & Tiện ích',
    'Hoá đơn điện thoại',
    'Hoá đơn nước',
    'Hoá đơn điện',
    'Hoá đơn gas',
    'Hoá đơn TV',
    'Hoá đơn internet',
    'Thuê nhà',
    'Hoá đơn tiện ích khác',
    'Di chuyển',
    'Bảo dưỡng xe',
    'Mua sắm',
    'Đồ dùng cá nhân',
    'Đồ gia dụng',
    'Làm đẹp',
    'Gia đình',
    'Sửa & trang trí nhà',
    'Dịch vụ gia đình',
    'Vật nuôi',
    'Sức khỏe',
    'Khám sức khoẻ',
    'Thể dục thể thao',
    'Giáo dục',
    'Giải trí',
    'Dịch vụ trực tuyến',
    'Vui - chơi',
    'Quà tặng & Quyên góp',
    'Bảo hiểm',
    'Đầu tư',
    'Các chi phí khác',
    'Tiền chuyển đi',
    'Trả lãi',
    'Tiết kiệm',
    'Hẹn hò',
    'Công tác phí',
    'Du lịch',
    'DL Di chuyển',
    'DL Ăn uống',
    'DL Lưu trú',
    'DL Mua sắm',
    'DL Vui chơi',
    'Tiêu tết',
    'Tết ăn uống',
    'Mừng tuổi',
    'Tết vui chơi',
    'Tết mua sắm',
]
valid_titles = ['Expense', 'Income']
wallets = list(pd.read_excel('data/transactions.xlsx', None).keys())
all_titles = []
all_categories = []
for wallet in wallets:
    df = pd.read_excel('data/transactions.xlsx', sheet_name=wallet)
    categories = df['Category']
    all_titles = all_titles + list(map(lambda x: x.split('|')[0], categories))
    all_categories = all_categories + list(map(lambda x: x.split('|')[1], categories))

unique_titles = list(set(all_titles))
unique_categories = list(set(all_categories))

# check if all titles are present in valid_titles
for title in unique_titles:
    if title not in valid_titles:
        raise Exception('Invalid title: ' + title)

# check if all categories are present in valid_categories
for category in unique_categories:
    if category not in valid_categories:
        raise Exception('Invalid category: ' + category)


# ================== MAIN ==================

driver = None
try:
    driver = init_driver()

    # Login
    print("Logging in")
    login(driver)
    print("Logging success")

    # Tabs
    tabs = {
        "Expense": 2,
        "Income": 3
    }

    # Read excel
    wallets = list(pd.read_excel('data/transactions.xlsx', None).keys())

    for wallet in wallets:
        df = pd.read_excel('data/transactions.xlsx', sheet_name=wallet)
        for idx, row in df.iterrows():

            tab = row['Category'].split('|')[0]
            category = row['Category'].split('|')[1]
            tab_id = tabs[tab]
            print(wallet + "-" + str(idx))
            amount = parse_amount(row)
            year, month, date = parse_date(row['Date'])

            # Open transaction modal
            click_when_clickable('//button[.//*[contains(text(), "Thêm giao dịch")]]', driver)
            
            # Click wallet dropdown
            click_when_clickable('(//*[@title="Ví"]/div[contains(@class, "search-border")])[2]', driver)
            
            # Select wallet
            click_when_clickable('//div[contains(@class, "focus-wallet") and .//*[contains(text(), "' + wallet + '")]]', driver, True)
            
            # Open category dropdown
            click_when_clickable('(//*[@title="Nhóm"]/div[contains(@class, "search-border")])[2]', driver)

            # Select category tab
            click_when_clickable('//div[contains(@class, "tab-item") and .//*[contains(text(), "' + "Khoản chi" + '")]]', driver)

            # Select category
            click_when_clickable('//div[@id="tab-' + str(tab_id) + '"]//div[(contains(@class, "category-item") or contains(@class, "child-category-item")) and .//*[contains(text(), "' + category + '")]]', driver, True)

            # Open date modal
            click_when_clickable('(//*[@title="Ngày"]/div[contains(@class, "search-border")])[2]', driver)

            # Select date
            click_when_clickable('//div[contains(@class, "picker-date")]//div[contains(@class, "v-date-picker-title__year")]', driver)
            time.sleep(1)        
            click_when_clickable('//ul[contains(@class, "v-date-picker-years")]//li[contains(text(), "' + str(year) + '")]', driver, True) # Year 2023
            time.sleep(1)        
            click_when_clickable('//*[text()="' + month + '"]/..', driver, True) # month Jan
            time.sleep(1)        
            click_when_clickable('//*[contains(@class, "v-date-picker-table--date")]//*[text()="' + str(date) + '"]/..', driver, True) # date 31
            time.sleep(1)

            # Enter amount
            enter_text('//div[contains(@class, "v-dialog--active")]//div[contains(@class, "amount")]//input', amount, driver)

            # Enter note
            enter_text('//div[contains(@class, "v-dialog--active")]//div[contains(@class, "note")]//input', row['Note'], driver)
            time.sleep(1)

            # Save transaction
            click_when_clickable('//div[contains(@class, "v-dialog--active")]//div[contains(@class, "transaction-dialog")]//div[contains(@class, "transaction-action")]//button[contains(@class, "done")]', driver)
            time.sleep(5)
finally:
    if driver:
        driver.quit()
