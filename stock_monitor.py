
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
 # PyGithubは不要になるためコメントアウト

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
    options.add_argument("--headless")  # ヘッドレスモードで実行
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30) # ページロードのタイムアウトを設定

        print("ログインページにアクセス中...")
        driver.get(LOGIN_URL)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, 'customer[email]'))
        )



        # ログインボタンが表示されるまで待機
        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
        )


        # ログイン処理
        print("ログイン情報を入力中...")
        driver.find_element(By.NAME, "customer[email]").send_keys(CI_MEDICAL_USERNAME)
        driver.find_element(By.NAME, "customer[password]").send_keys(CI_MEDICAL_PASSWORD)
        driver.find_element(By.CSS_SELECTOR, "button[type=\"submit\"]").click()

        print("ログイン後、商品ページにアクセス中...")
        # ログイン後に商品ページにリダイレクトされることを期待し、商品ページの特定の要素が出現するまで待機
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1.item-name")) # 商品名のh1タグを待機
        )

        driver.get(PRODUCT_URL) # 念のため再度商品ページにアクセス
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )


        # 業種選択のポップアップが表示された場合、閉じる
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()=\"ウィンドウを閉じる\"]"))
            )
            close_button.click()
            print("業種選択ポップアップを閉じました。")
            time.sleep(1) # ポップアップが閉じるのを待つ
        except TimeoutException:
            print("業種選択ポップアップは表示されませんでした。")

        # ページソースを取得してBeautifulSoupで解析
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # 在庫状況を示す要素を特定
        # 「買い物カゴに入れる」ボタンの有無を最優先で確認
        add_to_cart_button = soup.find("a", class_="btn-cart")
        if add_to_cart_button and "買い物カゴに入れる" in add_to_cart_button.text:
            print("在庫ありと判断しました。（「買い物カゴに入れる」ボタンが見つかったため）")
            return "在庫あり"

        # 次に価格が表示されているかを確認
        price_element = soup.find("span", class_="item-price__num")
        if price_element and price_element.text.strip() != "":
            print("在庫ありと判断しました。（価格要素が見つかったため）")
            return "在庫あり"
        
        # その他の在庫なしを示す要素のチェック（必要に応じて追加）
        # 例: no_stock_message = soup.find("div", class_="no-stock-message")
        # if no_stock_message:
        #     print("在庫なしと判断しました。（特定の要素が見つかったため）")
        #     return "在庫なし"

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
            driver.quit()

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

# GitHub Issueの作成はGitHub Actionsの機能を利用するため、Pythonスクリプトからは削除
# def create_github_issue(title, body):
#     """GitHub Issueを作成する"""
#     if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
#         print("GitHub通知設定が不完全です。環境変数を確認してください。")
#         return

#     try:
#         g = Github(GITHUB_TOKEN)
#         repo = g.get_user().get_repo(GITHUB_REPOSITORY.split("/")[-1]) # リポジトリ名のみ取得
#         repo.create_issue(title=title, body=body)
#         print("GitHub Issueを作成しました。")
#     except Exception as e:
#         print(f"GitHub Issueの作成中にエラーが発生しました: {e}")

def main():
    print(f"[{datetime.now()}] 在庫状況を確認中...")
    current_status = get_stock_status_with_selenium()

    if current_status.startswith("エラー"):
        print(f"在庫状況の取得中にエラーが発生しました: {current_status}。通知は行いません。")
        send_email_notification(
            f"CI Medical 在庫監視エラー: {current_status}",
            f"CI Medicalの製品ページ ({PRODUCT_URL}) の在庫状況取得中にエラーが発生しました。\nエラー詳細: {current_status}\nスクリプトの実行環境またはログイン情報を確認してください。"
        )
        # GitHub ActionsのIssue作成機能に任せるため、PythonからのIssue作成は行わない
        # create_github_issue(
        #     f"CI Medical 在庫監視エラー: {current_status}",
        #     f"CI Medicalの製品ページ ({PRODUCT_URL}) の在庫状況取得中にエラーが発生しました。\nエラー詳細: {current_status}\nスクリプトの実行環境またはログイン情報を確認してください。"
        # )
        return

    last_status = None
    if os.path.exists(LAST_STATUS_FILE):
        with open(LAST_STATUS_FILE, "r") as f:
            last_status = f.read().strip()

    if current_status != last_status:
        print(f"在庫状況が変化しました: {last_status if last_status else "初回"} -> {current_status}")
        subject = f"CI Medical 在庫通知: {current_status}"
        body = f"CI Medicalの製品ページ ({PRODUCT_URL}) の在庫状況が「{current_status}」に変化しました。\n確認してください。"
        send_email_notification(subject, body)
        # GitHub ActionsのIssue作成機能に任せるため、PythonからのIssue作成は行わない
        # create_github_issue(subject, body)
        with open(LAST_STATUS_FILE, "w") as f:
            f.write(current_status)
    else:
        print(f"在庫状況に変化はありません: {current_status}")

if __name__ == "__main__":
    main()


