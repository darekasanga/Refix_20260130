# Calcu - iPad専用 SwiftUI アプリ

このプロジェクトは、VercelにデプロイされたCalcu.htmlの内容を、iPad専用に最適化されたSwiftUIネイティブアプリとして実装したものです。

## 主な機能

### 🎨 **Apple Pencil 最適化描画**
- ネイティブSwiftUI Canvasを使用した高精度描画
- Apple Pencilの筆圧と傾き検知
- ズーム＆パン対応のキャンバスビュー

### 📱 **iPad特化UI**
- Split View: サイドバーに描画リスト、メインにキャンバス/WebView
- Multi-window対応（iPadOS 13.4+）
- ランドスケープ/ポートレート両対応
- キーボードショートカット（Cmd+Nで新規描画）

### 💾 **高度なデータ管理**
- Core Dataを使用した永続化（20MB上限、LRU自動削除）
- 描画のエクスポート（PNG/JPEG）
- iCloud同期対応
- メタデータ管理（タイムスタンプ、サイズ）

### 🌐 **WebView統合**
- WKWebViewを使用したHTMLコンテンツ表示
- IndexedDBデータのネイティブ連携
- オフラインファースト（バンドルHTMLフォールバック）

## 使い方

### 開発環境構築
1. **Xcode 14.0+** をインストール
2. このプロジェクトをXcodeで開く
3. iPadシミュレータまたは実機でビルド実行

### SwiftPMでのビルド
```bash
cd ios-prototype
swift build
swift run
```

## アーキテクチャ

### MVVMパターン
- **View**: SwiftUIベースの宣言的UI
- **ViewModel**: 状態管理とビジネスロジック
- **Model**: Core Dataモデル（描画データ）

### 主要コンポーネント
- `ContentView`: メインSplit View
- `DrawingViewModel`: 描画データ管理
- `WebViewModel`: Webコンテンツ管理
- `DrawingCanvas`: Pencil描画キャンバス
- `DrawingOverlay`: モーダル描画インターフェース

## iPad特化機能

### Split Viewレイアウト
```
┌─────────────┬─────────────────────┐
│  Drawings   │                     │
│  ┌────────┐ │     Canvas/Web      │
│  │ + New  │ │                     │
│  │ Drawing│ │                     │
│  └────────┘ │                     │
│  ┌────────┐ │                     │
│  │Drawing │ │                     │
│  │2024/1/9│ │                     │
│  └────────┘ │                     │
└─────────────┴─────────────────────┘
```

### Apple Pencil操作
- **シングルタップ**: 描画開始
- **ドラッグ**: 滑らかな線描画
- **筆圧**: 線の太さ変化
- **ダブルタップ**: 描画完了

### キーボードショートカット
- `Cmd+N`: 新規描画
- `Cmd+Delete`: 選択描画削除
- `Cmd+Shift+S`: エクスポート

## テスト

### 自動テスト
```bash
# テスト実行
swift test

# UIテスト
xcodebuild test -scheme Calcu-iPad -destination 'platform=iOS Simulator,name=iPad Pro (12.9-inch) (6th generation)'
```

### パフォーマンステスト
- メモリ使用量: 20MB上限のストレージ管理
- 描画速度: 60fps目標
- 起動時間: 2秒以内

## デプロイ

### TestFlight
1. Xcodeでアーカイブ作成
2. App Store Connectにアップロード
3. TestFlightで配布

### App Store
- **対象デバイス**: iPadのみ
- **iOSバージョン**: 15.0+
- **スクリーンショット**: 12.9-inch iPad Pro推奨

## 今後の拡張予定

- [ ] **マルチキャンバス**: 複数の描画を同時に開く
- [ ] **レイヤー機能**: 描画レイヤーの管理
- [ ] **クラウド同期**: iCloud Drive連携
- [ ] **共有機能**: 描画のコラボレーション
- [ ] **エクスポート形式**: PDF/SVG対応

---

**注意**: このアプリはiPad専用設計です。iPhoneでの動作はサポートしていません。

## 使い方（手順）
1. Xcode で新しい SwiftUI iOS プロジェクトを作成（ターゲット：iPad、最低 iOS 15+ 推奨）。
2. このフォルダの `Sources` 内の Swift ファイルをプロジェクトに追加します。
3. `www/Calcu.html` をプロジェクトの「Copy Bundle Resources」に追加してバンドルに含めます。
4. `RemoteFallbackApp.swift` をアプリのエントリポイントに設定するか、既存の `@main` を置き換えます。
5. `ContentView` の `remoteURL` を実際のホストに置き換えてください（例: `https://example.com/Calcu.html`）。

## 動作
- 起動時にネットワーク状態を検出します（`NetworkMonitor`）。
- オンラインであれば `remoteURL` をロードし、ロードに失敗した場合やオフラインなら `www/Calcu.html` をバンドルから読み込みます。
- 共有ボタン・リフレッシュボタンを提供しています。

## 実機テスト手順
1. Xcode でターゲットを iPad（実機）にしてビルド・実行します。
2. アプリを起動してリモートが読み込まれることを確認（オンライン）。
3. オフライン動作の確認: iPad で機内モードにするか、Simulator の Network Link Conditioner を使いオフライン状態にして再起動し、ローカル `www/Calcu.html` が表示されるか確認します。
4. Pencil の動作確認: 右上の鉛筆ボタンを押して描画モードを開き、Apple Pencil で描画 → "Done" を押すと、描画がWebページに送信され表示されることを確認します（`pencilImage` イベント経由）。
5. 永続化確認: 描画が表示された後、アプリを再起動して同じ描画が残っているか（IndexedDB に保存されているか）を確認します。`show last` / `show all` ボタンで DB 内の画像を確認できます。

### IndexedDB 容量と削除ポリシーのテスト
- 容量制限: 実装は **20MB** を上限（`MAX_TOTAL_BYTES`）にしており、上限を超えると古いデータから自動削除（LRU風）されます。
- 手順:
  1. 連続して複数回描画して保存（Pencilで大きな画像を数回送るか、テスト用ボタンで大量に送る）
  2. `ページ表示` ボタンで一覧を確認（ページネーションで確認できます）
  3. 大量に送った後、`ページ表示` を押した状態で古いアイテムが削除されていることを確認
  4. Safari Web Inspector の Application > IndexedDB > `CalcuDrawings` > `images` を開き、最終的な数とタイムスタンプを確認

### テスト用の自動投入（Simulator / 実機での自動テスト）
- `Calcu.html` には **テスト画像投入 (50)** のボタンがあり、押すと 1024x768 のテスト画像を 50 件連続投入します（スロットル付）。Simulator や実機で動作させて、IndexedDB の上限動作を確認してください。

#### Console からの自動テスト実行（推奨）
1. Safari の Develop > <Your Device> > <App WebView> を開き Console を表示します。
2. `ios-prototype/tests/auto_inject_test.js` を開いて全体をコピーし、Console に貼り付けて実行します（または Snippets に保存して実行）。
3. Console で `await __calcuAutoTest.runFullTest({count:200, delayMs:30, checkAfterMs:3000})` を実行します。
4. 実行後に返る `before` / `after` オブジェクトで `after.count` / `after.totalBytes` を確認し、削除ポリシー（容量上限内）に合致することを確認します。

6. Safari Web Inspector の使用: 実機をMacに接続して Safari の Develop メニューからアプリの WebView を選び、Console や Application タブで localStorage/IndexedDB の値を確認できます。IndexedDB の場合は Application > IndexedDB > `CalcuDrawings` を展開して `images` を確認します。

## 次の拡張案
- リモートHTMLを初回起動時にダウンロードしてアプリ内キャッシュに保存、オフライン時はキャッシュを使う
- JS ⇄ Swift 通信（`WKScriptMessageHandler`）でネイティブ機能（共有、Pencil）を実装
- Fastlane / GitHub Actions でビルドバリアント（iPad専用 / Universal）を自動化

---

必要ならこのプロトタイプをさらに拡張して、Pencilやマルチウィンドウを追加します。どれを優先しますか？