# Calcu iPadアプリ - 超簡単インストールガイド

## 🎯 目標: iPadでCalcuアプリを動かす

### 方法1: 最も簡単 - GitHub Actions + TestFlight（完全自動）

#### ステップ1: Apple Developer Program登録（$99/年）
```
📍 https://developer.apple.com/programs/
💰 学生/個人: $99
```

#### ステップ2: App Store Connectアプリ作成
1. https://appstoreconnect.apple.com/ にログイン
2. 「マイアプリ」→「+」→「新規アプリ」
3. プラットフォーム: iOS
4. 名前: Calcu
5. Bundle ID: `com.yourname.calcu` （一意に）
6. SKU: calcu001

#### ステップ3: GitHub Actions設定（自動ビルド）
```yaml
# .github/workflows/build.yml を作成
name: Build and Release iOS App
on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: macos-latest
    steps:
    - uses: actions/checkout@v3
    - name: Setup Xcode
      uses: maxim-lobanov/setup-xcode@v1
      with:
        xcode-version: '14.0'
    - name: Build and Test
      run: |
        xcodebuild -scheme Calcu-iPad -sdk iphoneos -configuration Release build
    - name: Archive
      run: |
        xcodebuild -scheme Calcu-iPad -archivePath build/Calcu.xcarchive archive
    - name: Export IPA
      run: |
        xcodebuild -exportArchive -archivePath build/Calcu.xcarchive -exportPath build -exportOptionsPlist exportOptions.plist
    - name: Upload to TestFlight
      run: |
        # TestFlightアップロードスクリプト
```

#### ステップ4: iPadでTestFlightインストール
1. iPadで **TestFlightアプリ** をインストール
2. 招待メールを受け取ってインストール

---

## 🚀 方法2: 超シンプル - Expo Application Services（無料）

### Expoを使うメリット
- ✅ **完全無料**
- ✅ **Mac不要**
- ✅ **ブラウザだけでOK**
- ✅ **数分で完了**

#### ステップ1: Expoアカウント作成
```
📍 https://expo.dev/
💰 無料
```

#### ステップ2: Expo CLIインストール
```bash
npm install -g @expo/cli
```

#### ステップ3: React Nativeプロジェクト作成
```bash
npx create-expo-app CalcuExpo --template
cd CalcuExpo
```

#### ステップ4: Calcu機能をReact Nativeで実装
```javascript
// App.js
import React, { useState, useRef } from 'react';
import { View, PanResponder, StyleSheet } from 'react-native';

export default function App() {
  const [paths, setPaths] = useState([]);
  const [currentPath, setCurrentPath] = useState([]);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onPanResponderGrant: (evt) => {
        const { locationX, locationY } = evt.nativeEvent;
        setCurrentPath([{ x: locationX, y: locationY }]);
      },
      onPanResponderMove: (evt) => {
        const { locationX, locationY } = evt.nativeEvent;
        setCurrentPath(prev => [...prev, { x: locationX, y: locationY }]);
      },
      onPanResponderRelease: () => {
        setPaths(prev => [...prev, currentPath]);
        setCurrentPath([]);
      },
    })
  );

  return (
    <View style={styles.container} {...panResponder.current.panHandlers}>
      {/* 描画パスを表示 */}
      {paths.map((path, index) => (
        <View key={index} style={styles.path}>
          {path.map((point, i) => (
            <View
              key={i}
              style={[styles.point, { left: point.x, top: point.y }]}
            />
          ))}
        </View>
      ))}
      
      {/* 現在の描画パス */}
      {currentPath.map((point, index) => (
        <View
          key={`current-${index}`}
          style={[styles.point, styles.currentPoint, { left: point.x, top: point.y }]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f0f0f0',
  },
  path: {
    position: 'absolute',
  },
  point: {
    position: 'absolute',
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#000',
  },
  currentPoint: {
    backgroundColor: '#007AFF',
  },
});
```

#### ステップ5: Expoでビルド・実行
```bash
# 開発サーバー起動
npx expo start

# iPadでQRコードをスキャンしてインストール
# または Expo Goアプリで開く
```

---

## 📱 方法3: WebアプリとしてiPadで動かす（最も簡単）

### PWA (Progressive Web App) 化
```html
<!-- index.html に追加 -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Calcu">
<link rel="apple-touch-icon" href="icon-192.png">

<script>
// Service Worker登録
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}
</script>
```

#### iPadでのインストール方法
1. Safariで `http://localhost:8080` を開く
2. 共有ボタン → 「ホーム画面に追加」
3. アプリとして起動可能

---

## 🏆 まとめ: おすすめ順位

### 1位: Expo Application Services ⭐⭐⭐⭐⭐
```
✅ 完全無料
✅ Mac不要
✅ 数分で完了
✅ 本物のiPadアプリ
```

### 2位: PWA (Webアプリ) ⭐⭐⭐⭐
```
✅ 無料
✅ ブラウザで開発
✅ 即時動作確認
```

### 3位: Xcode + TestFlight ⭐⭐⭐
```
✅ プロ並み品質
✅ App Store対応
❌ 複雑で高価
```

## 🎯 今すぐ試せる: Expoから始めよう！

```bash
# 1. Expo CLIインストール
npm install -g @expo/cli

# 2. プロジェクト作成
npx create-expo-app CalcuApp --template

# 3. 起動
cd CalcuApp
npx expo start
```

**Expo Goアプリ** をiPadにインストールして、QRコードをスキャンするだけ！

これでiPadでCalcuアプリが動きます！ 🎨📱✨