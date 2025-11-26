# CI Medical Stock Monitor

CI Medicalの商品在庫を自動監視し、在庫がある場合にメールまたはLINEで通知するシステムです。

## 機能

- 複数の商品URLを監視
- 商品名を自動取得してわかりやすく通知
- メール通知（Gmail対応）
- LINE通知（LINE Messaging API対応）
- GitHub Actionsで毎時自動実行

## 通知方法の選択

環境変数の設定により、通知方法を柔軟に選択できます：

- **メールのみ**: メール関連の環境変数のみ設定
- **LINEのみ**: LINE関連の環境変数のみ設定
- **両方**: すべての環境変数を設定

## セットアップ

### 1. GitHub Secretsの設定

リポジトリの Settings > Secrets and variables > Actions で以下のシークレットを設定：

#### CI Medical ログイン情報（必須）
- `CI_MEDICAL_USERNAME`: CI Medicalのログインユーザー名
- `CI_MEDICAL_PASSWORD`: CI Medicalのログインパスワード

#### メール通知設定（オプション）
- `SENDER_EMAIL`: 送信元メールアドレス
- `SENDER_PASSWORD`: メールアドレスのアプリパスワード
- `RECEIVER_EMAIL`: 通知先メールアドレス

#### LINE通知設定（オプション）
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Messaging APIのチャネルアクセストークン
- `LINE_USER_ID`: LINEユーザーID（オプション、指定しない場合は全友だちに送信）

### 2. LINE Messaging APIの設定手順

LINEで通知を受け取りたい場合：

#### 2.1 LINE Developersでチャネルを作成

1. [LINE Developers Console](https://developers.line.biz/console/) にアクセス
2. 「Create a new provider」をクリック（既存のProviderがある場合はスキップ）
3. Provider名を入力（例: `CI Medical Monitor`）
4. 「Create a Messaging API channel」をクリック
5. 以下の情報を入力：
   - **Channel name**: `CI Medical Stock Monitor`
   - **Channel description**: 在庫監視通知用
   - **Category**: 任意のカテゴリを選択
   - **Subcategory**: 任意のサブカテゴリを選択
6. 利用規約に同意して「Create」をクリック

#### 2.2 チャネルアクセストークンを取得

1. 作成したチャネルの「Messaging API」タブを開く
2. 「Channel access token」セクションで「Issue」をクリック
3. 生成されたトークンをコピー
4. GitHub Secretsの `LINE_CHANNEL_ACCESS_TOKEN` に設定

#### 2.3 ボットを友だち追加

1. 「Messaging API」タブの「QR code」をスキャン
2. LINEでボットを友だちに追加

#### 2.4 ユーザーIDを取得（オプション）

特定のユーザーにだけ送信したい場合：

1. ボットに何かメッセージを送信
2. [LINE Developers Console](https://developers.line.biz/console/)で「Messaging API」タブを開く
3. Webhookを有効にして一時的にエンドポイントを設定（またはWebhookログを確認）
4. ユーザーIDを確認
5. GitHub Secretsの `LINE_USER_ID` に設定

※ `LINE_USER_ID` を設定しない場合は、ボットの友だち全員に通知が送信されます。

#### 2.5 応答設定を調整

1. LINE Official Account Managerを開く（LINE Developersコンソールからリンクあり）
2. 「応答設定」で以下を設定：
   - 「応答メッセージ」: オフ
   - 「あいさつメッセージ」: 任意
   - 「Webhook」: オン

### 3. 監視する商品の追加

`stock_monitor.py` の `PRODUCT_URLS` リストに商品URLを追加：

```python
PRODUCT_URLS = [
    "https://www.ci-medical.com/dental/catalog_item/801Y880",
    "https://www.ci-medical.com/dental/catalog_item/801Y697",
    # 新しい商品URLをここに追加
]
```

## 通知メッセージの例

```
🎉 CI Medical 在庫通知！

以下の商品で在庫があります！

- 【ペンレステープ18mg [マルホ]の通販】
  https://www.ci-medical.com/dental/catalog_item/801Y253

今すぐ確認して購入を検討してください。
```

## 実行スケジュール

GitHub Actionsで毎時自動実行されます。手動実行も可能です：

1. GitHubリポジトリの「Actions」タブを開く
2. 「CI Medical Stock Monitor」ワークフローを選択
3. 「Run workflow」をクリック

## トラブルシューティング

### メール通知が届かない

- Gmailの場合、アプリパスワードを使用してください（通常のパスワードでは送信できません）
- 環境変数が正しく設定されているか確認

### LINE通知が届かない

- `LINE_CHANNEL_ACCESS_TOKEN` が正しく設定されているか確認
- ボットを友だち追加しているか確認
- GitHub Actionsのログでエラーメッセージを確認

### 商品名が「商品ID: 801YXXX」と表示される

- 商品ページのHTML構造が変更された可能性があります
- GitHub Actionsのログで「警告: 商品名を取得できませんでした」を確認
- ログに表示されるh1タグ情報を元に `extract_product_name` 関数を調整

## ライセンス

MIT License
