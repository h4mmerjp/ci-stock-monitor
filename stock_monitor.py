
import requests
from bs4 import BeautifulSoup
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# 設定
PRODUCT_URL = 'https://www.ci-medical.com/dental/catalog_COOKIES = {} # ログインが必要な場合、ここにクッキーを設定してください。ブラウザの開発者ツールから取得できます。
                 # 例: COOKIES = {"PHPSESSID": "your_session_id", "ci_medical_login": "your_login_cookie"}
                 # クッキーは有効期限があるため、定期的な更新が必要になる場合があります。
                 # より永続的な解決策としては、Seleniumなどのヘッドレスブラウザでログイン処理を自動化する方法があります。 通知設定 (環境変数から取得することを推奨)
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD') # アプリパスワードなど
RECEIVER_EMAIL = os.getenv('RECEIVER_EMAIL')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))

# 以前の在庫状況を保存するファイル
LAST_STATUS_FILE = 'last_stock_status.txt'

def get_stock_status():
    """ウェブページから在庫状況を取得する"""
    try:
        response = requests.get(PRODUCT_URL, cookies=COOKIES)
        response.raise_for_status() # HTTPエラーがあれば例外を発生させる
        soup = BeautifulSoup(response.text, 'html.parser')

        # 在庫状況を示す要素を特定（これはウェブサイトの構造によって変わります）
        # 例: 「在庫なし」というテキストがあるか、特定のクラスを持つ要素        # ログイン後のページで「買い物カゴに入れる」ボタンの有無や、価格表示の有無などを確認してください。
        # 提供されたHTMLから、ログイン後のページでは商品情報がdataLayerに格納されていることが確認できます。
        # また、価格が表示されている場合は在庫ありと判断できます。
        # 今回のHTMLでは「価格：ログイン後表示」ではなく、具体的な価格が表示されています。
        # 在庫なしの場合の表示はHTMLからは確認できませんが、一般的には「在庫なし」というテキストや、
        # 「買い物カゴに入れる」ボタンが非表示になるなどの変化があります。
        
        # 価格が表示されているかを確認
        price_element = soup.find("span", class_="item-price__num")
        if price_element and price_element.text.strip() != "":
            return '在庫あり'
        
        # その他の在庫なしを示す要素のチェック（必要に応じて追加）
        # 例: no_stock_message = soup.find('div', class_='no-stock-message')
        # if no_stock_message:
        #     return '在庫なし'

        # ログイン前の表示「価格：ログイン後表示」がある場合
        if '価格：ログイン後表示' in response.text:
            print("ログインが必要です。または、ログイン後の在庫表示要素を特定できませんでした。")
            return 'ログイン必要'
        
        return '在庫なし' # デフォルトで在庫なしと仮定

    except requests.exceptions.RequestException as e:
        print(f"ウェブページの取得中にエラーが発生しました: {e}")
        return None

def send_email_notification(subject, body):
    """メールで通知を送信する"""
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECEIVER_EMAIL:
        print("メール通知設定が不完全です。環境変数を確認してください。")
        return

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL

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
    current_status = get_stock_status()

    if current_status is None:
        print("在庫状況の取得に失敗しました。通知は行いません。")
        return

    if current_status == 'ログイン必要':
        print("ログインが必要なページです。手動でログインするか、Seleniumなどのヘッドレスブラウザの使用を検討してください。")
        send_email_notification(
            'CI Medical 在庫監視: ログインが必要です',
            f'CI Medicalの製品ページ ({PRODUCT_URL}) はログインが必要です。\nスクリプトがログイン後の在庫状況を正しく取得できませんでした。\n手動でログインするか、スクリプトの修正を検討してください。'
        )
        return

    last_status = None
    if os.path.exists(LAST_STATUS_FILE):
        with open(LAST_STATUS_FILE, 'r') as f:
            last_status = f.read().strip()

    if current_status != last_status:
        print(f"在庫状況が変化しました: {last_status if last_status else '初回'} -> {current_status}")
        subject = f'CI Medical 在庫通知: {current_status}'
        body = f'CI Medicalの製品ページ ({PRODUCT_URL}) の在庫状況が「{current_status}」に変化しました。\n確認してください。'
        send_email_notification(subject, body)
        with open(LAST_STATUS_FILE, 'w') as f:
            f.write(current_status)
    else:
        print(f"在庫状況に変化はありません: {current_status}")

if __name__ == '__main__':
    main()


