#!/bin/bash
# Calcu Expo App セットアップスクリプト

echo "🎨 Calcu Expo App セットアップ開始..."

# Node.js確認
if ! command -v node &> /dev/null; then
    echo "❌ Node.jsがインストールされていません"
    echo "📦 https://nodejs.org/ からインストールしてください"
    exit 1
fi

# npm確認
if ! command -v npm &> /dev/null; then
    echo "❌ npmがインストールされていません"
    exit 1
fi

echo "✅ Node.js $(node --version) 検出"
echo "✅ npm $(npm --version) 検出"

# Expo CLI確認・インストール
if ! command -v expo &> /dev/null; then
    echo "📦 Expo CLIをインストール中..."
    npm install -g @expo/cli
fi

echo "✅ Expo CLI $(expo --version) 準備完了"

# プロジェクトディレクトリ移動
cd ios-prototype/expo-app

# 依存関係インストール
echo "📦 依存関係をインストール中..."
npm install

echo "🎉 セットアップ完了！"
echo ""
echo "🚀 アプリを起動するには:"
echo "   cd ios-prototype/expo-app"
echo "   npx expo start"
echo ""
echo "📱 iPadでテストするには:"
echo "   1. iPadにExpo Goアプリをインストール"
echo "   2. QRコードをスキャン"
echo ""
echo "📚 詳細: expo-app/README.md"