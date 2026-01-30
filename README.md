# webpage

シンプルな静的ページで、1号認定の方向けに「預かり保育は延長料金がかからない」ことを案内します。

## セットアップ
ブラウザで `index.html` を開くだけで表示できます。

### 管理コード発行・管理 API（FastAPI）
1. 依存インストール
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. マスター管理コードの初期化（初回のみ）
   ```bash
   uvicorn app:app --reload  # 別ターミナルで起動しておく
   curl -X POST http://127.0.0.1:8000/init-master \
     -H "Content-Type: application/json" \
     -d '{"code":"<安全なマスター管理コード>"}'
   ```
   ※ master_admin が既に存在する場合は 400 を返します。
3. 新しい admin コードの発行
   ```bash
   curl -X POST http://127.0.0.1:8000/codes/issue \
     -H "Content-Type: application/json" \
     -d '{"issuer_code":"<マスター管理コード>"}'
   ```
4. コード検証
   ```bash
   curl -X POST http://127.0.0.1:8000/codes/validate \
     -H "Content-Type: application/json" \
     -d '{"code":"<検証するコード>"}'
   ```
5. コードの無効化（master_admin だけが実行可能）
   ```bash
   curl -X POST http://127.0.0.1:8000/codes/deactivate \
     -H "Content-Type: application/json" \
     -d '{"actor_code":"<マスター管理コード>","target_code":"<無効化するコード>"}'
   ```
  SQLite DB は `data/management_codes.db` に保存されます。コードはハッシュ化され、重複防止のため fingerprint を保持しています。コード仕様は 8〜16 文字の英数字＋ハイフンで、必ず英字と数字を含みます。

## Wi-Fiローカル運用（Macゲート）
園内Wi-Fi専用での安定運用を想定したローカルAPIを FastAPI で提供します。HTTPS 不要・園内ネットワークのみ許可・更新系は共有トークンで保護します。

### 1) Wi-Fiローカル設定（管理画面）
1. FastAPI を起動します。
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8787
   ```
2. ブラウザで `http://<mac-ip>:8787/admin/login` にアクセスし、`admin / admin01` でログインします。
3. 「Wi-Fiローカルネットワーク設定」で以下を設定します。
   - **ローカルAPI Base URL**: 例 `http://mac-gate.local:8787`
   - **許可CIDR**: 例 `192.168.10.0/24,fd00::/64`
   - **端末登録用共有キー**: POST `/save` 用の `X-Local-Token`

### 2) ローカルAPI（ローカルとVercelで同一パス）
| Method | Path | 概要 |
| --- | --- | --- |
| GET | `/health` | ローカルサーバの死活確認 |
| GET | `/latest` | 最新データ（version_label / updated_at / updated_by / payload） |
| GET | `/history` | 過去データ一覧（メタ情報のみ） |
| POST | `/save` | 最新データの保存（`X-Local-Token` 必須） |

### 3) 例: 保存・取得
```bash
curl -X POST http://mac-gate.local:8787/save \\
  -H "Content-Type: application/json" \\
  -H "X-Local-Token: <shared-secret>" \\
  -d '{
    "version_label": "v1.8",
    "updated_by": "tanaka",
    "payload": {"nodes": [], "settings": {}}
  }'

curl http://mac-gate.local:8787/latest
```

## ツール一覧
- `Calcu.html` : ニュースと計算をまとめたハブ
- `Calcu2.html` : シンプル計算シート
- `line-diary-card.html` : 写真＋地図＋メモから LINE 日記カードを作成し、Flex Message JSON を生成
- `admin-login.html` / `admin-dashboard.html` : 管理用のログインとダッシュボードビュー
- `admin-code-issue.html` : FastAPI の管理コードを初期化・発行・検証・無効化するツール
