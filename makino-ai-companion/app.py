"""牧野生保塾 AI伴走システム - FastAPI エントリーポイント。

Usage:
    python app.py
    uvicorn app:app --reload --port 8000
"""

import logging
import os
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from starlette.middleware.sessions import SessionMiddleware

from src.api.routes import create_routes, router
from src.auth.dependencies import get_optional_user
from src.auth.oauth import create_auth_routes
from src.chat.engine import ChatEngine
from src.database.models import init_db
from src.notifications.escalation_notifier import EscalationNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent


def load_config() -> dict:
    """設定ファイルを読み込む。"""
    config_path = BASE_DIR / "config" / "settings.yaml"
    with open(config_path, encoding="utf-8") as f:
        content = f.read()

    # 環境変数の展開
    for key, value in os.environ.items():
        content = content.replace(f"${{{key}}}", value)

    return yaml.safe_load(content)


def create_app() -> FastAPI:
    """FastAPIアプリケーションを生成する。"""
    config = load_config()

    app = FastAPI(
        title="牧野生保塾 AI伴走システム",
        description="生命保険営業AI伴走システム API",
        version=config["project"]["version"],
    )

    # セッションミドルウェア（OAuth2コールバックに必要）
    session_secret = os.environ.get("SESSION_SECRET", "dev-session-secret")
    app.add_middleware(SessionMiddleware, secret_key=session_secret)

    # CORS設定（チャットウィジェット埋め込み対応）
    server_config = config.get("server", {})
    cors_config = server_config.get("cors", {})
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config.get("allow_origins", ["*"]),
        allow_methods=cors_config.get("allow_methods", ["GET", "POST"]),
        allow_headers=cors_config.get("allow_headers", ["*"]),
        allow_credentials=True,
    )

    # 静的ファイル・テンプレート
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

    # データベース初期化
    db_path = config.get("database", {}).get("sqlite", {}).get("path", "data/conversations.db")
    db_conn = init_db(BASE_DIR / db_path)
    logger.info(f"データベース初期化完了: {db_path}")

    # チャットエンジン初期化
    claude_config = config.get("claude", {})
    api_key = claude_config.get("api_key", os.environ.get("ANTHROPIC_API_KEY", ""))

    engine = ChatEngine(
        api_key=api_key,
        model=claude_config.get("model", "claude-sonnet-4-5-20250929"),
        knowledge_dir=str(BASE_DIR / config.get("rag", {}).get("knowledge_dir", "knowledge")),
        config_path=str(BASE_DIR / "config" / "settings.yaml"),
        max_tokens=claude_config.get("max_tokens", 4096),
    )

    # 認証ルーティング
    auth_config = config.get("auth", {})
    auth_router = create_auth_routes(auth_config)
    app.include_router(auth_router)

    # エスカレーション通知サービス
    escalation_config = config.get("escalation", {})
    notifier = EscalationNotifier(escalation_config)

    # APIルーティング設定
    create_routes(engine, db_conn, notifier=notifier)
    app.include_router(router)

    # --- ページルーティング ---

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        """ログインページ。認証済みならトップへリダイレクト。"""
        user = await get_optional_user(request)
        if user:
            return RedirectResponse(url="/")
        return templates.TemplateResponse("login.html", {"request": request})

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """メインチャットページ。未認証ならログインページへ。"""
        user = await get_optional_user(request)
        if not user:
            return RedirectResponse(url="/login")
        return templates.TemplateResponse("index.html", {"request": request, "user": user})

    @app.get("/widget", response_class=HTMLResponse)
    async def widget(request: Request) -> HTMLResponse:
        """埋め込み用チャットウィジェット。"""
        return templates.TemplateResponse("widget.html", {"request": request})

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """管理ダッシュボード（管理者用KPI表示）。未認証・非管理者はリダイレクト。"""
        user = await get_optional_user(request)
        if not user:
            return RedirectResponse(url="/login")
        if not user.is_admin:
            return RedirectResponse(url="/")
        return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

    logger.info("アプリケーション初期化完了")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    config = load_config()
    server_config = config.get("server", {})

    uvicorn.run(
        "app:app",
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8000),
        reload=server_config.get("debug", False),
    )
