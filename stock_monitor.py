import requests
from bs4 import BeautifulSoup
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
import time

# 設定
PRODUCT_URL = os.getenv("PRODUCT_URL", "https://www.ci-medical.com/dental/catalog_item/801Y697")
LOGIN_URL = os.getenv("LOGIN_URL", "https://www.ci-medical.com/accounts/sign_in")

# ログイン情報 (環境変数から取得することを推奨)
CI_MEDICAL_USERNAME = os.getenv("CI_MEDICAL_USERNAME")
CI_MEDICAL_PASSWORD = os.getenv("CI_MEDICAL_PASSWORD")

# 通知設定 (環境変数から取得することを推奨)
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD") # アプリパスワードなど
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# 以前の在庫状況を保存するファイル
LAST_STATUS_FILE = "last_stock_status.txt"

def get_stock_status_with_selenium():
    """Seleniumを使用してウェブページから在庫状況を取得する"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)  # タイムアウトを60秒に延長
        driver.implicitly_wait(10)  # 暗黙的待機を追加
        
        # WebDriver検出を回避
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print(f"ログインページにアクセス中: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        # ページが完全に読み込まれるまで待機
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # HTMLソースから確認した正確なセレクタを使用
        try:
            login_id_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "account_login"))
            )
            print("ログインIDフィールドが見つかりました")
        except TimeoutException:
            print("ログインIDフィールドが見つかりません")
            raise Exception("ログインフォームが見つかりません")

        # パスワードフィールド
        try:
            password_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "account_password"))
            )
            print("パスワードフィールドが見つかりました")
        except TimeoutException:
            raise Exception("パスワードフィールドが見つかりません")

        # ログイン処理
        print("ログイン情報を入力中...")
        login_id_field.clear()
        login_id_field.send_keys(CI_MEDICAL_USERNAME)
        time.sleep(1)
        
        password_field.clear()
        password_field.send_keys(CI_MEDICAL_PASSWORD)
        time.sleep(1)

        # ログインボタン（HTMLソースから確認）
        try:
            submit_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="submit"][value="ログイン"]'))
            )
            submit_button.click()
            print("ログインボタンをクリックしました")
        except TimeoutException:
            raise Exception("ログインボタンが見つかりません")

        # ログイン後の処理を待機
        time.sleep(3)
        
        print(f"商品ページにアクセス中: {PRODUCT_URL}")
        driver.get(PRODUCT_URL)
        
        # ページが読み込まれるまで待機
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # 業種選択のポップアップが表示された場合、閉じる
        try:
            close_selectors = [
                "//button[contains(text(), 'ウィンドウを閉じる')]",
                "//button[contains(text(), '閉じる')]",
                "//button[contains(text(), 'Close')]",
                ".modal-close",
                ".popup-close"
            ]
            
            for selector in close_selectors:
                try:
                    if selector.startswith("//"):
                        close_button = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        close_button = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    close_button.click()
                    print("ポップアップを閉じました。")
                    time.sleep(1)
                    break
                except TimeoutException:
                    continue
        except Exception as e:
            print("ポップアップは表示されませんでした。")

        # ページソースを取得してBeautifulSoupで解析
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # 在庫状況を示す要素を特定
        # 「買い物カゴに入れる」ボタンの有無を確認
        cart_button_selectors = [
            {"class": "btn-cart"},
            {"class": "add-to-cart"},
            {"class": "cart-button"},
        ]
        
        for selector in cart_button_selectors:
            add_to_cart_button = soup.find("a", selector) or soup.find("button", selector)
            if add_to_cart_button and ("買い物カゴ" in add_to_cart_button.text or "カート" in add_to_cart_button.text):
                print("在庫ありと判断しました。（「買い物カゴに入れる」ボタンが見つかったため）")
                return "在庫あり"

        # 価格表示の確認
        price_selectors = [
            {"class": "item-price__num"},
            {"class": "price"},
            {"class": "item-price"},
        ]
        
        for selector in price_selectors:
            price_element = soup.find("span", selector) or soup.find("div", selector)
            if price_element and price_element.text.strip() and price_element.text.strip() != "":
                print("在庫ありと判断しました。（価格要素が見つかったため）")
                return "在庫あり"
        
        # 在庫なしを示すメッセージの確認
        out_of_stock_indicators = [
            "在庫なし", "品切れ", "売り切れ", "完売", "Out of Stock", "Sold Out"
        ]
        
        page_text = soup.get_text()
        for indicator in out_of_stock_indicators:
            if indicator in page_text:
                print(f"在庫なしと判断しました。（「{indicator}」が見つかったため）")
                return "在庫なし"

        print("在庫なしと判断しました。（「買い物カゴに入れる」ボタンも価格要素も見つからないため）")
        return "在庫なし"

    except TimeoutException as e:
        print(f"要素のロード中にタイムアウトしました: {e}")
        return "エラー: タイムアウト"
    except WebDriverException as e:
        print(f"WebDriverエラーが発生しました: {e}")
        return "エラー: WebDriver"
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return "エラー: その他"
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def send_email_notification(subject, body):
    """メールで通知を送信する"""
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        print("メール通知設定が不完全です。環境変数を確認してください。")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print("メール通知を送信しました。")
    except Exception as e:
        print(f"メールの送信中にエラーが発生しました: {e}")

def main():
    print(f"[{datetime.now()}] 在庫状況を確認中...")
    current_status = get_stock_status_with_selenium()

    if current_status.startswith("エラー"):
        print(f"在庫状況の取得中にエラーが発生しました: {current_status}。通知は行いません。")
        send_email_notification(
            f"CI Medical 在庫監視エラー: {current_status}",
            f"CI Medicalの製品ページ ({PRODUCT_URL}) の在庫状況取得中にエラーが発生しました。\nエラー詳細: {current_status}\nスクリプトの実行環境またはログイン情報を確認してください。"
        )
        # エラーファイルを作成してGitHub Actionsで状態を把握できるようにする
        with open(LAST_STATUS_FILE, "w") as f:
            f.write("エラー")
        return

    last_status = None
    if os.path.exists(LAST_STATUS_FILE):
        with open(LAST_STATUS_FILE, "r") as f:
            last_status = f.read().strip()

    # 現在の状態を保存
    with open(LAST_STATUS_FILE, "w") as f:
        f.write(current_status)

    if current_status != last_status:
        print(f"在庫状況が変化しました: {last_status if last_status else '初回'} -> {current_status}")
        subject = f"CI Medical 在庫通知: {current_status}"
        body = f"CI Medicalの製品ページ ({PRODUCT_URL}) の在庫状況が「{current_status}」に変化しました。\n確認してください。"
        send_email_notification(subject, body)
    else:
        print(f"在庫状況に変化はありません: {current_status}")

if __name__ == "__main__":
    main()
