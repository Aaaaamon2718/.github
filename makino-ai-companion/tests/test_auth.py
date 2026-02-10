"""認証モジュールのテスト。"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.auth.dependencies import AuthUser, get_current_user, get_optional_user, require_admin
from src.auth.oauth import (
    COOKIE_NAME,
    JWT_SECRET,
    create_jwt_token,
    decode_jwt_token,
)


class TestJWT:
    """JWTトークン生成・検証のテスト。"""

    def test_create_and_decode(self) -> None:
        """トークンの生成と検証が正しく動くこと。"""
        user_data = {
            "sub": "google-123",
            "email": "test@example.com",
            "name": "テスト太郎",
            "picture": "",
            "role": "user",
        }
        token = create_jwt_token(user_data)
        assert isinstance(token, str)
        assert len(token) > 0

        payload = decode_jwt_token(token)
        assert payload is not None
        assert payload["email"] == "test@example.com"
        assert payload["name"] == "テスト太郎"
        assert payload["role"] == "user"

    def test_decode_invalid_token(self) -> None:
        """不正なトークンでNoneが返ること。"""
        result = decode_jwt_token("invalid.token.here")
        assert result is None

    def test_decode_empty_token(self) -> None:
        """空トークンでNoneが返ること。"""
        result = decode_jwt_token("")
        assert result is None

    def test_token_contains_expiry(self) -> None:
        """トークンにexp/iatが含まれること。"""
        token = create_jwt_token({"sub": "test", "email": "a@b.com"})
        payload = decode_jwt_token(token)
        assert "exp" in payload
        assert "iat" in payload

    def test_admin_role_in_token(self) -> None:
        """管理者ロールがトークンに保持されること。"""
        token = create_jwt_token({
            "sub": "admin-1",
            "email": "admin@example.com",
            "role": "admin",
        })
        payload = decode_jwt_token(token)
        assert payload["role"] == "admin"


class TestAuthUser:
    """AuthUserクラスのテスト。"""

    def test_user_id_from_email(self) -> None:
        """emailがuser_idとして使われること。"""
        user = AuthUser({
            "sub": "123",
            "email": "user@example.com",
            "name": "テスト",
            "role": "user",
        })
        assert user.user_id == "user@example.com"
        assert not user.is_admin

    def test_user_id_fallback_to_sub(self) -> None:
        """emailがない場合subがuser_idになること。"""
        user = AuthUser({"sub": "123", "email": "", "role": "user"})
        assert user.user_id == "123"

    def test_admin_check(self) -> None:
        """is_adminが正しく動くこと。"""
        admin = AuthUser({"sub": "1", "email": "a@b.com", "role": "admin"})
        assert admin.is_admin

        user = AuthUser({"sub": "2", "email": "c@d.com", "role": "user"})
        assert not user.is_admin


class TestAuthDependencies:
    """認証依存関数のテスト。"""

    @pytest.mark.asyncio
    async def test_get_current_user_valid(self) -> None:
        """有効なトークンでユーザーが返ること。"""
        token = create_jwt_token({
            "sub": "123",
            "email": "test@example.com",
            "name": "テスト",
            "role": "user",
        })
        request = MagicMock()
        request.cookies = {COOKIE_NAME: token}

        user = await get_current_user(request)
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_current_user_no_cookie(self) -> None:
        """クッキーなしで401が返ること。"""
        request = MagicMock()
        request.cookies = {}

        with pytest.raises(Exception) as exc_info:
            await get_current_user(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self) -> None:
        """不正トークンで401が返ること。"""
        request = MagicMock()
        request.cookies = {COOKIE_NAME: "bad-token"}

        with pytest.raises(Exception) as exc_info:
            await get_current_user(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_optional_user_none(self) -> None:
        """クッキーなしでNoneが返ること。"""
        request = MagicMock()
        request.cookies = {}

        user = await get_optional_user(request)
        assert user is None

    @pytest.mark.asyncio
    async def test_get_optional_user_valid(self) -> None:
        """有効なトークンでユーザーが返ること。"""
        token = create_jwt_token({
            "sub": "123",
            "email": "test@example.com",
            "role": "user",
        })
        request = MagicMock()
        request.cookies = {COOKIE_NAME: token}

        user = await get_optional_user(request)
        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_require_admin_success(self) -> None:
        """管理者で正常にパスすること。"""
        token = create_jwt_token({
            "sub": "1",
            "email": "admin@example.com",
            "role": "admin",
        })
        request = MagicMock()
        request.cookies = {COOKIE_NAME: token}

        user = await require_admin(request)
        assert user.is_admin

    @pytest.mark.asyncio
    async def test_require_admin_forbidden(self) -> None:
        """一般ユーザーで403が返ること。"""
        token = create_jwt_token({
            "sub": "2",
            "email": "user@example.com",
            "role": "user",
        })
        request = MagicMock()
        request.cookies = {COOKIE_NAME: token}

        with pytest.raises(Exception) as exc_info:
            await require_admin(request)
        assert exc_info.value.status_code == 403
