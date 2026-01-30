# Calcu - Expo iPad App

iPadで動くCalcu描画アプリ。Expo Application Servicesを使って簡単にビルド・配布できます。

## 🚀 3分でiPadアプリ化！

### ステップ1: Expo CLIインストール
```bash
npm install -g @expo/cli
```

### ステップ2: プロジェクトセットアップ
```bash
cd ios-prototype/expo-app
npm install
```

### ステップ3: 開発サーバー起動
```bash
npx expo start
```

### ステップ4: iPadでテスト
1. iPadに **Expo Go** アプリをインストール
2. QRコードをスキャン
3. アプリが起動！

## 📱 機能

- ✅ **タッチ描画**: 指やApple Pencilで描画
- ✅ **描画保存**: 自動保存・読み込み
- ✅ **Split View**: サイドバーに描画リスト
- ✅ **エクスポート**: SVG形式で共有
- ✅ **iPad最適化**: 大画面レイアウト

## 🛠️ プロジェクト構造

```
expo-app/
├── App.js              # メインアプリ
├── package.json        # 依存関係
└── assets/            # 画像・アイコン
```

## 🎯 使い方

### 描画モード
1. 「✏️ New Drawing」をタップ
2. 画面をタッチして描画開始
3. 指を離すと保存完了

### 閲覧モード
1. サイドバーから描画を選択
2. 「📤 Export」でSVG出力

### データ管理
- 自動保存: 描画完了時に保存
- 読み込み: アプリ起動時に復元
- 削除: 個別削除または全削除

## 📦 ビルド・配布

### 開発ビルド
```bash
npx expo run:ios
```

### プロダクションビルド
```bash
npx expo build:ios
eas build --platform ios
```

### TestFlight配布
```bash
eas submit --platform ios
```

## 🔧 カスタマイズ

### 描画設定変更
```javascript
// App.js のスタイルを編集
const styles = StyleSheet.create({
  canvas: {
    // キャンバス設定
  },
  currentPoint: {
    // 描画線設定
  },
});
```

### 新機能追加
- 色変更機能
- ブラシツール
- レイヤー機能
- クラウド同期

## 🐛 トラブルシューティング

### Expo Goが起動しない
```bash
# キャッシュクリア
npx expo r -c
```

### ビルドエラー
```bash
# 依存関係再インストール
rm -rf node_modules
npm install
```

### iPadで表示がおかしい
- Expo Goアプリを最新版に更新
- iPadを再起動

## 📚 関連リンク

- [Expo公式ドキュメント](https://docs.expo.dev/)
- [React Nativeドキュメント](https://reactnative.dev/)
- [Expo Goアプリ](https://apps.apple.com/app/expo-go/id982107779)

## 🎉 完成！

これでiPadで本物のCalcuアプリが動きます！

**ExpoならMac不要・無料・数分で完了！** 🎨📱✨