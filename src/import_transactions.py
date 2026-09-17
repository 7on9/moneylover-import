from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import pandas as pd
from datetime import datetime
import re
import time 
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import os
import subprocess
from dotenv import load_dotenv
from categories import VALID_CATEGORIES, VALID_TITLES
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
    element.click()
    element.clear()
    element.send_keys(str(text))

def enter_amount(xpath, amount, driver):
    element = wait_for_xpath(xpath, driver)
    value = str(int(amount)) if not isinstance(amount, str) else amount.replace(',', '')
    element.click()
    # Select-all + type (works with Vue-controlled inputs)
    element.send_keys(Keys.COMMAND, 'a')
    element.send_keys(Keys.BACKSPACE)
    element.send_keys(value)
    # Force Vue v-model update if keystrokes did not stick
    driver.execute_script(
        """
        const el = arguments[0];
        const value = arguments[1];
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        value,
    )
    time.sleep(0.5)

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

valid_categories = VALID_CATEGORIES
valid_titles = VALID_TITLES


def validate_xlsx(xlsx_path):
    wallets = list(pd.read_excel(xlsx_path, None).keys())
    all_titles = []
    all_categories = []
    for wallet in wallets:
        df = pd.read_excel(xlsx_path, sheet_name=wallet)
        categories = df['Category']
        all_titles = all_titles + list(map(lambda x: x.split('|')[0], categories))
        all_categories = all_categories + list(map(lambda x: x.split('|')[1], categories))

    unique_titles = list(set(all_titles))
    unique_categories = list(set(all_categories))

    for title in unique_titles:
        if title not in valid_titles:
            raise Exception('Invalid title: ' + title)

    for category in unique_categories:
        if category not in valid_categories:
            raise Exception('Invalid category: ' + category)


def close_active_dialog(driver):
    driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
    try:
        WebDriverWait(driver, 5).until(
            expected_conditions.invisibility_of_element_located((By.CSS_SELECTOR, 'div.v-overlay--active'))
        )
    except Exception:
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)


def parse_wallet_item_text(text):
    lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
    if not lines:
        return None
    name = lines[0]
    balance = 0
    for line in reversed(lines):
        digits = re.sub(r'[^\d,.\-]', '', line)
        if digits and any(ch.isdigit() for ch in digits):
            cleaned = digits
            if cleaned.count('.') > 1 and ',' not in cleaned:
                cleaned = cleaned.replace('.', '')
            elif cleaned.count(',') > 1:
                cleaned = cleaned.replace(',', '')
            else:
                cleaned = cleaned.replace(',', '')
            try:
                balance = int(abs(float(cleaned)))
            except ValueError:
                continue
            break
    return {'name': name, 'balance': balance}


def export_wallet_balances(driver):
    click_when_clickable('//button[.//*[contains(text(), "Thêm giao dịch")]]', driver)
    click_when_clickable('(//*[@title="Ví"]/div[contains(@class, "search-border")])[2]', driver)
    time.sleep(1)
    texts = driver.execute_script(
        """
        const nodes = Array.from(document.querySelectorAll('.focus-wallet, [class*="wallet-item"]'));
        return nodes.map((el) => el.innerText);
        """
    )
    wallets = []
    seen = set()
    for text in texts or []:
        parsed = parse_wallet_item_text(text)
        if not parsed or parsed['name'] in seen:
            continue
        seen.add(parsed['name'])
        wallets.append(parsed)
    close_active_dialog(driver)
    return wallets


def import_rows(driver, xlsx_path):
    tabs = {
        "Expense": 2,
        "Income": 3
    }
    wallets = list(pd.read_excel(xlsx_path, None).keys())
    for wallet in wallets:
        df = pd.read_excel(xlsx_path, sheet_name=wallet)
        for idx, row in df.iterrows():

            tab = row['Category'].split('|')[0]
            category = row['Category'].split('|')[1]
            tab_id = tabs[tab]
            print(wallet + "-" + str(idx))
            amount = parse_amount(row)
            year, month, date = parse_date(row['Date'])

            WebDriverWait(driver, 20).until(
                expected_conditions.invisibility_of_element_located((By.CSS_SELECTOR, 'div.v-overlay--active'))
            )

            click_when_clickable('//button[.//*[contains(text(), "Thêm giao dịch")]]', driver)
            click_when_clickable('(//*[@title="Ví"]/div[contains(@class, "search-border")])[2]', driver)
            click_when_clickable('//div[contains(@class, "focus-wallet") and .//*[contains(text(), "' + wallet + '")]]', driver, True)
            click_when_clickable('(//*[@title="Nhóm"]/div[contains(@class, "search-border")])[2]', driver)
            click_when_clickable('//div[contains(@class, "tab-item") and .//*[contains(text(), "' + "Khoản chi" + '")]]', driver)
            click_when_clickable('//div[@id="tab-' + str(tab_id) + '"]//div[(contains(@class, "category-item") or contains(@class, "child-category-item")) and .//*[contains(text(), "' + category + '")]]', driver, True)
            click_when_clickable('(//*[@title="Ngày"]/div[contains(@class, "search-border")])[2]', driver)
            click_when_clickable('//div[contains(@class, "picker-date")]//div[contains(@class, "v-date-picker-title__year")]', driver)
            time.sleep(1)
            click_when_clickable('//ul[contains(@class, "v-date-picker-years")]//li[contains(text(), "' + str(year) + '")]', driver, True)
            time.sleep(1)
            click_when_clickable('//*[text()="' + month + '"]/..', driver, True)
            time.sleep(1)
            click_when_clickable('//*[contains(@class, "v-date-picker-table--date")]//*[text()="' + str(date) + '"]/..', driver, True)
            time.sleep(1)

            amount_xpath = '//div[contains(@class, "v-dialog--active")]//div[contains(@class, "amount")]//input'
            enter_amount(amount_xpath, amount, driver)
            enter_text('//div[contains(@class, "v-dialog--active")]//div[contains(@class, "note")]//input', row['Note'], driver)
            time.sleep(1)

            done_xpath = '//div[contains(@class, "v-dialog--active")]//div[contains(@class, "transaction-dialog")]//div[contains(@class, "transaction-action")]//button[contains(@class, "done") and not(@disabled)]'
            try:
                WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.XPATH, done_xpath)))
            except Exception:
                enter_amount(amount_xpath, amount, driver)
                WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.XPATH, done_xpath)))
            click_when_clickable(done_xpath, driver)
            WebDriverWait(driver, 20).until(
                expected_conditions.invisibility_of_element_located((By.CSS_SELECTOR, 'div.v-overlay--active'))
            )
            time.sleep(1)


def run(xlsx_path='data/transactions.xlsx'):
    validate_xlsx(xlsx_path)
    driver = None
    try:
        driver = init_driver()
        print("Logging in")
        login(driver)
        print("Logging success")
        import_rows(driver, xlsx_path)
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    run()
