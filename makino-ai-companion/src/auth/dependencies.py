"""FastAPI 認証依存関数。

エンドポイントに認証・認可を適用するための Depends 関数群。
"""

import logging
from typing import Optional

from fastapi import HTTPException, Request

from src.auth.oauth import COOKIE_NAME, decode_jwt_token

logger = logging.getLogger(__name__)


class AuthUser:
    """認証済みユーザーを表すクラス。"""

    def __init__(self, payload: dict) -> None:
        self.sub: str = payload.get("sub", "")
        self.email: str = payload.get("email", "")
        self.name: str = payload.get("name", "")
        self.picture: str = payload.get("picture", "")
        self.role: str = payload.get("role", "user")

    @property
    def user_id(self) -> str:
        """データベース保存用のユーザーID。"""
        return self.email or self.sub

    @property
    def is_admin(self) -> bool:
        """管理者かどうか。"""
        return self.role == "admin"


async def get_current_user(request: Request) -> AuthUser:
    """現在のログインユーザーを取得する。

    未認証の場合は 401 Unauthorized を返す。
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="認証が必要です")

    payload = decode_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="セッションが期限切れです")

    return AuthUser(payload)


async def get_optional_user(request: Request) -> Optional[AuthUser]:
    """現在のログインユーザーを取得する。未認証の場合は None を返す。

    認証が任意のエンドポイント用（ヘルスチェックなど）。
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    payload = decode_jwt_token(token)
    if not payload:
        return None

    return AuthUser(payload)


async def require_admin(request: Request) -> AuthUser:
    """管理者権限を要求する。

    管理者でない場合は 403 Forbidden を返す。
    """
    user = await get_current_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return user
