"""Google OAuth2 認証フロー。

Google OAuth2 を使用してユーザー認証を行い、
JWT トークンでセッションを管理する。
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# JWT設定
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
COOKIE_NAME = "makino_session"

# OAuth クライアント（create_auth_routes で初期化）
_oauth: Optional[OAuth] = None


def create_jwt_token(user_data: dict) -> str:
    """JWTトークンを生成する。

    Args:
        user_data: ユーザー情報 (sub, email, name, picture, role)

    Returns:
        エンコードされたJWT文字列
    """
    payload = {
        **user_data,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[dict]:
    """JWTトークンをデコードする。

    Returns:
        デコードされたペイロード。無効な場合はNone。
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def create_auth_routes(config: dict) -> APIRouter:
    """OAuth認証ルーターを生成する。

    Args:
        config: settings.yaml の auth セクション

    Returns:
        認証用APIRouter
    """
    global _oauth

    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=config.get("google_client_id", os.environ.get("GOOGLE_CLIENT_ID", "")),
        client_secret=config.get("google_client_secret", os.environ.get("GOOGLE_CLIENT_SECRET", "")),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
    _oauth = oauth

    admin_emails = set(config.get("admin_emails", []))

    @auth_router.get("/login")
    async def login(request: Request) -> RedirectResponse:
        """Google OAuth2 認証画面へリダイレクトする。"""
        redirect_uri = request.url_for("auth_callback")
        return await oauth.google.authorize_redirect(request, redirect_uri)

    @auth_router.get("/callback")
    async def auth_callback(request: Request) -> RedirectResponse:
        """Google OAuth2 コールバック。JWTトークンを発行しクッキーに設定する。"""
        try:
            token = await oauth.google.authorize_access_token(request)
        except Exception as e:
            logger.error(f"OAuth トークン取得エラー: {e}")
            raise HTTPException(status_code=401, detail="認証に失敗しました")

        user_info = token.get("userinfo")
        if not user_info:
            raise HTTPException(status_code=401, detail="ユーザー情報を取得できません")

        email = user_info.get("email", "")
        role = "admin" if email in admin_emails else "user"

        jwt_token = create_jwt_token({
            "sub": user_info.get("sub", ""),
            "email": email,
            "name": user_info.get("name", ""),
            "picture": user_info.get("picture", ""),
            "role": role,
        })

        logger.info(f"ログイン成功: {email} (role={role})")

        response = RedirectResponse(url="/")
        response.set_cookie(
            key=COOKIE_NAME,
            value=jwt_token,
            httponly=True,
            samesite="lax",
            max_age=JWT_EXPIRATION_HOURS * 3600,
        )
        return response

    @auth_router.get("/logout")
    async def logout() -> RedirectResponse:
        """ログアウト。セッションクッキーを削除する。"""
        response = RedirectResponse(url="/")
        response.delete_cookie(key=COOKIE_NAME)
        return response

    @auth_router.get("/me")
    async def me(request: Request) -> dict:
        """現在のログインユーザー情報を返す。"""
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return {"authenticated": False}

        payload = decode_jwt_token(token)
        if not payload:
            return {"authenticated": False}

        return {
            "authenticated": True,
            "email": payload.get("email"),
            "name": payload.get("name"),
            "picture": payload.get("picture"),
            "role": payload.get("role"),
        }

    return auth_router
