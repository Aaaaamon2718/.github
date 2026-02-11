# セキュリティ設計書｜牧野生保塾 AI伴走システム

最終更新: 2026年2月11日

---

## 1. 結論

本システムのセキュリティは **Google OAuth2 + JWT HttpOnly Secure Cookie** を基盤とし、
追加の独自認証機構なしで、以下の主要攻撃ベクトルすべてに対する防御を実現している。

| 攻撃 | 防御済み | 防御手段 |
|------|---------|---------|
| 不正ログイン | ✅ | Google OAuth2（Googleアカウント必須） |
| セッション乗っ取り（XSS） | ✅ | HttpOnly Cookie（JSからアクセス不可） |
| セッション乗っ取り（盗聴） | ✅ | Secure Cookie + HTTPS（暗号化通信のみ） |
| クロスサイトリクエスト偽造（CSRF） | ✅ | SameSite="lax" Cookie属性 |
| 不正なクロスオリジン呼出 | ✅ | CORS ホワイトリスト制限 |
| 権限昇格 | ✅ | ロールベースアクセス制御（admin/user分離） |
| トークン改ざん | ✅ | JWT署名検証（HS256 + サーバー秘密鍵） |
| セッション永続化攻撃 | ✅ | JWT有効期限（24時間で強制失効） |

---

## 2. 認証方式: Google OAuth2

### なぜ Google OAuth2 で十分か

```
独自パスワード認証の場合:
  → パスワードDB管理、ハッシュ化、漏洩対策、リセット機能、総当たり攻撃対策 … すべて自前実装が必要
  → 1つでも実装ミスがあれば脆弱性に直結

Google OAuth2 の場合:
  → 認証処理はGoogleが担当。本システムはGoogleの「認証済み」という結果のみを受け取る
  → パスワードは一切保存しない。漏洩するパスワードが存在しない
```

**具体的な防御:**

| 脅威 | Google OAuth2 による対応 |
|------|------------------------|
| パスワード総当たり攻撃 | パスワード自体が存在しないため原理的に不可能 |
| フィッシング | Google側の不審ログイン検知・2段階認証で防御 |
| クレデンシャルスタッフィング | 他サービスのパスワード漏洩の影響を受けない |
| アカウント乗っ取り | Google側の多要素認証（ユーザーが有効化している場合）で防御 |

### 実装詳細

```
ファイル: src/auth/oauth.py

認証フロー:
  ① ユーザーが /auth/login にアクセス
  ② Google認証画面にリダイレクト（authlib が OAuth2フローを処理）
  ③ ユーザーがGoogleアカウントで認証
  ④ /auth/callback でGoogleからトークンを受信
  ⑤ ユーザー情報（email, name等）を取得
  ⑥ JWTを生成し、HttpOnly Secure Cookieとしてブラウザに返却

使用ライブラリ: authlib（OAuth2/OpenID Connect業界標準ライブラリ）
スコープ: openid, email, profile（最小限の情報のみ取得）
```

---

## 3. セッション管理: JWT HttpOnly Secure Cookie

### Cookie の4つのセキュリティ属性

本システムのセッションCookieには以下4つの属性がすべて設定されている。

```python
# src/auth/oauth.py (117-124行目)
response.set_cookie(
    key="makino_session",
    value=jwt_token,
    httponly=True,     # ① XSS対策
    secure=True,       # ② 盗聴対策
    samesite="lax",    # ③ CSRF対策
    max_age=86400,     # ④ セッション有効期限（24時間）
)
```

各属性の防御効果:

| 属性 | 効果 | 防御する攻撃 |
|------|------|-------------|
| `httponly=True` | JavaScriptから `document.cookie` でアクセス不可 | XSS攻撃によるトークン窃取 |
| `secure=True` | HTTPS通信でのみCookieを送信 | 中間者攻撃（Man-in-the-Middle）によるトークン盗聴 |
| `samesite="lax"` | 外部サイトからのPOSTリクエストにCookieを付与しない | CSRF（クロスサイトリクエスト偽造）攻撃 |
| `max_age=86400` | 24時間で自動失効 | 盗まれたトークンの無期限悪用 |

### なぜ専用CSRFトークンが不要か

SameSite="lax" は現代ブラウザ（Chrome, Firefox, Safari, Edge すべて対応）において
CSRF攻撃を防御する標準的な方法であり、二重に専用CSRFトークンを実装する必要はない。

```
SameSite="lax" の動作:
  ✅ 同一サイトからのGET/POSTリクエスト → Cookieが送信される（正常動作）
  ✅ 外部サイトからのリンククリック（GET） → Cookieが送信される（正常動作）
  ❌ 外部サイトからのPOST/PUT/DELETEリクエスト → Cookieが送信されない（CSRF防御）
  ❌ 外部サイトのiframe/img/scriptからのリクエスト → Cookieが送信されない（CSRF防御）
```

### JWT トークンの構造

```
ペイロード:
  sub     : Google ユーザーID（一意識別子）
  email   : メールアドレス
  name    : 表示名
  picture : プロフィール画像URL
  role    : "admin" または "user"
  exp     : 有効期限（発行から24時間後のUNIXタイムスタンプ）
  iat     : 発行日時

署名アルゴリズム: HS256（HMAC-SHA256）
署名鍵: 環境変数 JWT_SECRET（サーバーのみが保持）
```

**トークン改ざんが不可能な理由:**
JWT の署名は `JWT_SECRET`（サーバー側のみが保持する秘密鍵）で生成される。
攻撃者がペイロード（例: role を "admin" に変更）を改ざんしても、
秘密鍵を知らなければ正しい署名を生成できず、サーバー側の検証で拒否される。

---

## 4. アクセス制御: ロールベース（RBAC）

### ロール定義

| ロール | 割り当て条件 | アクセス可能な機能 |
|--------|-------------|-------------------|
| `admin` | `settings.yaml` の `admin_emails` リストに含まれるメールアドレス | 全機能 + 管理ダッシュボード + KPI API |
| `user` | 上記以外のGoogleアカウント | チャット + フィードバック |

### エンドポイント別アクセス制御

```
ファイル: src/auth/dependencies.py, src/api/routes.py

┌────────────────────────┬───────────────────┬──────────────┐
│ エンドポイント          │ 認証依存関数       │ 必要ロール    │
├────────────────────────┼───────────────────┼──────────────┤
│ POST /api/chat         │ get_current_user  │ user以上      │
│ POST /api/feedback     │ get_current_user  │ user以上      │
│ POST /api/guide/...    │ get_current_user  │ user以上      │
│ GET  /api/metrics      │ require_admin     │ admin のみ    │
│ GET  /api/metrics/...  │ require_admin     │ admin のみ    │
│ GET  /api/health       │ （なし）           │ 公開          │
│ GET  /auth/me          │ （なし）           │ 公開 *        │
└────────────────────────┴───────────────────┴──────────────┘

* /auth/me は認証状態の確認用。有効なJWTが存在する場合のみユーザー情報を返す。
  未認証時は { "authenticated": false } を返すだけで、情報漏洩は発生しない。
```

### 権限チェックの仕組み

```python
# src/auth/dependencies.py

# ① 全リクエストでCookieからJWTを取得・検証
async def get_current_user(request):
    token = request.cookies.get("makino_session")
    if not token:       → 401 Unauthorized
    payload = decode_jwt_token(token)
    if not payload:     → 401 Unauthorized（期限切れ or 改ざん）
    return AuthUser(payload)

# ② 管理者専用エンドポイントでは追加チェック
async def require_admin(request):
    user = await get_current_user(request)  # まず①の認証チェック
    if not user.is_admin:  → 403 Forbidden
    return user
```

FastAPI の `Depends()` パターンにより、各エンドポイントの関数定義に
認証依存関数を指定するだけで、**自動的にアクセス制御が適用される**。
新規エンドポイント追加時にチェック漏れが起きにくい設計。

---

## 5. CORS（クロスオリジン）制御

```yaml
# config/settings.yaml
cors:
  allow_origins:
    - "http://localhost:3000"      # 開発環境
    - ${ALLOWED_ORIGIN}            # 本番ドメイン（環境変数で指定）
  allow_methods: ["GET", "POST"]   # 必要最小限のHTTPメソッド
  allow_headers: ["*"]
```

```
効果:
  ✅ 許可されたドメインからのリクエスト → 正常処理
  ❌ 未知のドメインからのリクエスト → ブラウザが自動ブロック

  allow_credentials: true により Cookie が送信可能だが、
  これは allow_origins が "*" でない場合のみ安全に動作する（本システムは具体的なドメインを指定）。
```

---

## 6. インフラレベルの保護（Railway）

本システムは Railway 上にデプロイされており、以下のインフラレベルの保護が自動適用される。

| 保護 | 提供元 | 説明 |
|------|--------|------|
| HTTPS強制 | Railway | 全通信がTLS暗号化。HTTPリクエストは自動的にHTTPSにリダイレクト |
| DDoS基本防御 | Railway / GCP | Google Cloud Platform 基盤の基本的なDDoS対策 |
| コンテナ分離 | Docker | アプリケーションがコンテナ内で隔離実行される |
| 環境変数管理 | Railway | シークレット（JWT_SECRET等）がRailwayの暗号化されたストアに保存 |

**RailwayがHTTPSを強制するため、HSTSヘッダーの追加実装は不要。**

---

## 7. 「追加不要」と判断したセキュリティ対策とその理由

以下は一般的なセキュリティチェックリストに含まれるが、本システムでは **意図的に実装していない** 項目。
過剰実装は保守コストの増加とバグ混入リスクにつながるため、不要なものは追加しない。

| 対策 | 不要と判断した理由 |
|------|-------------------|
| 独自パスワード認証 | Google OAuth2で代替。パスワード管理の脆弱性リスクを排除 |
| 専用CSRFトークン | SameSite="lax"で十分。二重実装は複雑性を増すだけ |
| HSTSヘッダー | RailwayがHTTPSを強制しており、アプリ側での実装は冗長 |
| WAF（Web Application Firewall） | Railway/GCPインフラの基本防御で十分。専用WAFはコスト対効果が低い |
| 多要素認証（MFA） | Google側の設定で対応可能。本システムが独自に実装する必要なし |
| IP制限 | 受講生が全国各地からアクセスするため、IP制限は運用上不適切 |
| セッション無効化DB | JWT有効期限（24h）で自然失効。即時無効化が必要なケースは想定外 |

---

## 8. 環境変数一覧（本番設定時の必須項目）

| 環境変数 | 用途 | 設定箇所 |
|---------|------|---------|
| `JWT_SECRET` | JWTトークン署名鍵 | Railway環境変数（ランダムな64文字以上の文字列を設定） |
| `SESSION_SECRET` | OAuth2コールバック用セッション鍵 | Railway環境変数（ランダムな32文字以上の文字列を設定） |
| `GOOGLE_CLIENT_ID` | Google OAuth2 クライアントID | Google Cloud Console → 認証情報 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 クライアントシークレット | Google Cloud Console → 認証情報 |
| `ADMIN_EMAIL` | 管理者メールアドレス | Railway環境変数 |
| `ALLOWED_ORIGIN` | CORS許可ドメイン（本番URL） | Railway環境変数 |
| `ANTHROPIC_API_KEY` | Claude API キー | Anthropicダッシュボード |

**注意:** `JWT_SECRET` と `SESSION_SECRET` は本番環境で必ずランダムな長い文字列に設定すること。
デフォルト値（`dev-secret-change-in-production`）は開発用であり、本番で使用してはならない。

---

## 9. まとめ

```
本システムのセキュリティ構成:

  [Google OAuth2]    → 認証はGoogleに委任。パスワード管理リスクをゼロに
       ↓
  [JWT HS256]        → 改ざん不可能なトークンでセッション管理
       ↓
  [HttpOnly Cookie]  → XSS攻撃からトークンを保護
       ↓
  [Secure Flag]      → HTTPS以外でのトークン送信を禁止
       ↓
  [SameSite=lax]     → CSRF攻撃を防御
       ↓
  [RBAC]             → admin/user のロール分離
       ↓
  [CORS Whitelist]   → 許可ドメイン以外からのAPIアクセスを遮断
       ↓
  [Railway HTTPS]    → インフラレベルで全通信を暗号化

この多層防御により、Googleアカウントを持たない第三者がシステムに侵入することは不可能であり、
大規模クライアントに対しても十分なセキュリティ・ガバナンス水準を担保している。
```
