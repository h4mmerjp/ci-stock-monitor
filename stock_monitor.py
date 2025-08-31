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
import json

# 設定
LOGIN_URL = os.getenv("LOGIN_URL", "https://www.ci-medical.com/accounts/sign_in")

# 監視対象商品のリスト
PRODUCT_URLS = [
    "https://www.ci-medical.com/dental/catalog_item/801Y880",
    "https://www.ci-medical.com/dental/catalog_item/801Y697",
    "https://www.ci-medical.com/dental/catalog_item/801Y168",
    "https://www.ci-medical.com/dental/catalog_item/801Y774",
    # 追加商品のURLをここに記載
    # "https://www.ci-medical.com/dental/catalog_item/商品ID2",
    # "https://www.ci-medical.com/dental/catalog_item/商品ID3",
]

# ログイン情報 (環境変数から取得することを推奨)
CI_MEDICAL_USERNAME = os.getenv("CI_MEDICAL_USERNAME")
CI_MEDICAL_PASSWORD = os.getenv("CI_MEDICAL_PASSWORD")

# 通知設定 (環境変数から取得することを推奨)
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# 以前の在庫状況を保存するファイル
LAST_STATUS_FILE = "last_stock_status.json"

def get_stock_status_with_selenium(product_url):
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
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(10)
        
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
        
        print(f"商品ページにアクセス中: {product_url}")
        driver.get(product_url)
        
        # ページが読み込まれるまで待機
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # ポップアップが表示された場合、閉じる
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

        # **まず在庫なしを示すメッセージを優先的に確認**
        stock_status_element = soup.find("span", class_="product-stock__status")
        if stock_status_element:
            stock_text = stock_status_element.text.strip()
            stock_classes = stock_status_element.get("class", [])
            
            if "在庫なし" in stock_text or "is-soldout" in stock_classes:
                print(f"在庫なしと判断しました。（在庫状況表示: {stock_text}, クラス: {stock_classes}）")
                return "在庫なし"
            elif "在庫あり" in stock_text:
                print(f"在庫ありと判断しました。（在庫状況表示: {stock_text}）")
                return "在庫あり"

        # **「在庫なし」ボタンを確認**
        cart_button = soup.find("a", class_="button-cart")
        if cart_button:
            button_text = cart_button.text.strip()
            button_classes = cart_button.get("class", [])
            
            if "在庫なし" in button_text or "button-cart--disabled" in button_classes:
                print(f"在庫なしと判断しました。（ボタン表示: {button_text}, クラス: {button_classes}）")
                return "在庫なし"
            elif "買い物カゴ" in button_text or "カート" in button_text:
                print(f"在庫ありと判断しました。（ボタン表示: {button_text}）")
                return "在庫あり"

        # **購入フォームの状態を確認**
        product_form = soup.find("div", class_="product-form")
        if product_form:
            form_classes = product_form.get("class", [])
            if "is-disabled" in form_classes:
                print(f"在庫なしと判断しました。（購入フォームが無効化されているため: {form_classes}）")
                return "在庫なし"

        # **「買い物カゴに入れる」ボタンの有無を確認（より広範囲）**
        cart_button_selectors = [
            {"class": "button-cart"},
            {"class": "btn-cart"},
            {"class": "add-to-cart"},
            {"class": "cart-button"},
        ]
        
        for selector in cart_button_selectors:
            add_to_cart_button = soup.find("a", selector) or soup.find("button", selector)
            if add_to_cart_button:
                button_text = add_to_cart_button.text.strip()
                if "買い物カゴ" in button_text or "カート" in button_text:
                    print(f"在庫ありと判断しました。（「買い物カゴに入れる」ボタンが見つかったため: {selector}）")
                    return "在庫あり"

        # **在庫なしを示すテキストの確認**
        out_of_stock_indicators = [
            "在庫なし", "品切れ", "売り切れ", "完売", "Out of Stock", "Sold Out"
        ]
        
        page_text = soup.get_text()
        for indicator in out_of_stock_indicators:
            if indicator in page_text:
                print(f"在庫なしと判断しました。（「{indicator}」が見つかったため）")
                return "在庫なし"

        # **最後の手段として価格表示を確認（ただし、上記の在庫なし条件をクリアした場合のみ）**
        price_selectors = [
            {"class": "product-price__txt"},
            {"class": "item-price__num"},
            {"class": "price"},
            {"class": "item-price"},
        ]
        
        for selector in price_selectors:
            price_element = soup.find("p", selector) or soup.find("span", selector) or soup.find("div", selector)
            if price_element and price_element.text.strip() and "円" in price_element.text:
                # 価格が表示されているが、上記の在庫確認で在庫なしの兆候がない場合のみ在庫ありとする
                print(f"在庫ありと判断しました。（価格要素が見つかり、在庫なしの兆候がないため: {selector}）")
                return "在庫あり"

        print("在庫状況を判定できませんでした。デフォルトで在庫なしとします。")
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

def load_last_status():
    """前回の在庫状況を読み込む"""
    if os.path.exists(LAST_STATUS_FILE):
        try:
            with open(LAST_STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_current_status(status_dict):
    """現在の在庫状況を保存する"""
    with open(LAST_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_dict, f, ensure_ascii=False, indent=2)

def main():
    print(f"[{datetime.now()}] 在庫状況を確認中...")
    
    # 前回の状況を読み込み
    last_status_dict = load_last_status()
    current_status_dict = {}
    
    # 在庫ありの商品リスト
    in_stock_products = []
    error_products = []
    
    # 各商品の在庫状況をチェック
    for product_url in PRODUCT_URLS:
        print(f"\n商品チェック中: {product_url}")
        current_status = get_stock_status_with_selenium(product_url)
        current_status_dict[product_url] = current_status
        
        # エラーの場合
        if current_status.startswith("エラー"):
            error_products.append({"url": product_url, "error": current_status})
            continue
        
        # 在庫ありの商品を記録
        if current_status == "在庫あり":
            in_stock_products.append(product_url)
            print(f"在庫あり: {product_url}")

    # 現在の状況を保存
    save_current_status(current_status_dict)
    
    # 通知処理
    if error_products:
        error_urls = "\n".join([f"- {item['url']}: {item['error']}" for item in error_products])
        send_email_notification(
            "CI Medical 在庫監視エラー",
            f"以下の商品で在庫状況取得エラーが発生しました:\n\n{error_urls}\n\nスクリプトの実行環境またはログイン情報を確認してください。"
        )
    
    # 在庫ありの商品が1つ以上ある場合に通知
    if in_stock_products:
        # 在庫ありの商品リストを作成
        in_stock_summary = []
        for product_url in in_stock_products:
            in_stock_summary.append(f"- {product_url}")
        
        in_stock_text = "\n".join(in_stock_summary)
        
        subject = "🎉 CI Medical 在庫通知！"
        body = f"以下の商品で在庫があります！\n\n{in_stock_text}\n\n今すぐ確認して購入を検討してください。"
        
        send_email_notification(subject, body)
        print(f"在庫ありの商品 {len(in_stock_products)}件について通知を送信しました。")
    else:
        print("在庫ありの商品はありませんでした。")
    
    # GitHub Actions用に在庫ありの商品があるかを記録
    if in_stock_products:
        with open("last_stock_status.txt", "w") as f:
            f.write("在庫あり")
    elif error_products:
        with open("last_stock_status.txt", "w") as f:
            f.write("エラー")
    else:
        with open("last_stock_status.txt", "w") as f:
            f.write("在庫なし")

if __name__ == "__main__":
    main()
