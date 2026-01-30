# iPadでCalcuアプリを動かす方法

## 🚀 即時プレビューURL
**http://localhost:3000/preview.html**

※ ローカル環境でWebサーバーを起動してください

## 📱 iPadでアプリ化する3つの方法

### 方法1: Xcode + iPad実機（開発者向け）
#### 必要なもの
- MacBook/iMac
- Xcode 14.0+
- Apple Developer Program ($99/年)
- iPad (iPadOS 15.0+)

#### 手順
1. **Xcodeをインストール**
   ```bash
   # Mac App StoreからXcodeをダウンロード
   ```

2. **プロジェクトを開く**
   ```bash
   cd ios-prototype
   open Calcu-iPad.xcodeproj
   ```

3. **iPadを接続**
   - USBケーブルでMacとiPadを接続
   - iPadのロックを解除し、「信頼する」を選択

4. **ビルド実行**
   - Xcodeで iPad をターゲットに選択
   - ▶️ ボタンをクリックしてビルド
   - 初回はApple IDでのコード署名が必要

### 方法2: TestFlight（無料配布）
#### 手順
1. **Apple Developer Program登録**
   - https://developer.apple.com/programs/
   - 年間$99

2. **App Store Connect設定**
   - https://appstoreconnect.apple.com/
   - 新しいアプリを作成

3. **Xcodeでアーカイブ**
   ```bash
   # Xcode: Product > Archive
   ```

4. **TestFlightにアップロード**
   - OrganizerウィンドウでDistribute App
   - TestFlightを選択

5. **テスター招待**
   - メールアドレスでテスターを招待
   - iPadでTestFlightアプリからインストール

### 方法3: Xcode Cloud（クラウドビルド）
#### 利点
- Mac不要
- 自動ビルド
- チーム共有可能

#### 手順
1. **GitHubリポジトリにプッシュ**
   ```bash
   git add .
   git commit -m "iPad Calcu app"
   git push origin main
   ```

2. **Xcode Cloud有効化**
   - https://developer.apple.com/xcode-cloud/
   - リポジトリを接続

3. **ワークフロー作成**
   - 自動ビルド設定
   - TestFlight自動配布

## 🎯 推奨: 方法2 (TestFlight)

### なぜTestFlightがおすすめ？
- ✅ Mac不要（クラウドビルド可能）
- ✅ 無料で100人まで配布可能
- ✅ App Storeと同等の審査
- ✅ 自動アップデート
- ✅ クラッシュレポート取得

### TestFlightの流れ
```
GitHub → Xcode Cloud → TestFlight → iPadインストール
    ↓           ↓           ↓           ↓
  コード     自動ビルド   審査・配布   アプリ使用
```

## 📋 必要な開発環境

### 必須
- Apple Developer Program: $99/年
- iPad: iPadOS 15.0+
- Xcode: 14.0+ (クラウド使用時は不要)

### オプション
- Mac: 開発効率向上
- Apple Pencil: 描画機能テスト

## 🔧 トラブルシューティング

### ビルドエラー
```bash
# 依存関係クリーン
xcodebuild clean

# 派生データ削除
rm -rf ~/Library/Developer/Xcode/DerivedData
```

### 署名エラー
- Xcode → Preferences → Accounts
- Apple IDを追加
- チームを選択

### iPad認識されない
- USBケーブルを交換
- iPadの「信頼する」を確認
- Xcodeを再起動

## 📞 サポート

質問があればいつでもどうぞ！

**今すぐ始めましょう！** 🎨📱