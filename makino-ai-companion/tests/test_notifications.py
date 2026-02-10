"""エスカレーション通知のテスト。"""

from unittest.mock import MagicMock, patch

import pytest

from src.notifications.escalation_notifier import (
    EmailNotifier,
    EscalationEvent,
    EscalationNotifier,
    LineNotifier,
    SlackNotifier,
)


@pytest.fixture
def sample_event() -> EscalationEvent:
    """テスト用エスカレーションイベント。"""
    return EscalationEvent(
        conversation_id=42,
        session_id="test-session-123",
        user_id="user@example.com",
        question="コンプライアンス的に問題ない営業方法を教えてください",
        reason="強制エスカレーションカテゴリ: コンプライアンス関連",
        confidence=0.25,
        category="コンプライアンス関連",
        timestamp="2026-02-10T10:30:00",
    )


class TestEmailNotifier:
    """EmailNotifierのテスト。"""

    def test_no_smtp_host(self, sample_event: EscalationEvent) -> None:
        """SMTP設定なしでFalseが返ること。"""
        notifier = EmailNotifier(smtp_host="", recipients=[])
        assert notifier.send(sample_event) is False

    def test_no_recipients(self, sample_event: EscalationEvent) -> None:
        """宛先なしでFalseが返ること。"""
        notifier = EmailNotifier(smtp_host="smtp.test.com", recipients=[])
        assert notifier.send(sample_event) is False

    def test_build_message(self, sample_event: EscalationEvent) -> None:
        """メールメッセージが正しく構築されること。"""
        notifier = EmailNotifier(
            smtp_host="smtp.test.com",
            recipients=["admin@test.com"],
        )
        msg = notifier._build_message(sample_event)
        assert "エスカレーション" in msg["Subject"]
        assert "admin@test.com" in msg["To"]

    @patch("src.notifications.escalation_notifier.smtplib.SMTP")
    def test_send_success(
        self,
        mock_smtp: MagicMock,
        sample_event: EscalationEvent,
    ) -> None:
        """SMTP送信が成功すること。"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(
            smtp_host="smtp.test.com",
            recipients=["admin@test.com"],
        )
        result = notifier.send(sample_event)
        assert result is True
        mock_server.send_message.assert_called_once()


class TestSlackNotifier:
    """SlackNotifierのテスト。"""

    def test_no_webhook_url(self, sample_event: EscalationEvent) -> None:
        """Webhook URL なしでFalseが返ること。"""
        notifier = SlackNotifier(webhook_url="")
        assert notifier.send(sample_event) is False

    @patch("src.notifications.escalation_notifier.httpx.post")
    def test_send_success(
        self,
        mock_post: MagicMock,
        sample_event: EscalationEvent,
    ) -> None:
        """Slack送信が成功すること。"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = notifier.send(sample_event)
        assert result is True
        mock_post.assert_called_once()

    @patch("src.notifications.escalation_notifier.httpx.post")
    def test_send_failure(
        self,
        mock_post: MagicMock,
        sample_event: EscalationEvent,
    ) -> None:
        """Slack送信エラー時にFalseが返ること。"""
        mock_post.side_effect = Exception("Network error")

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = notifier.send(sample_event)
        assert result is False


class TestLineNotifier:
    """LineNotifierのテスト。"""

    def test_no_token(self, sample_event: EscalationEvent) -> None:
        """トークンなしでFalseが返ること。"""
        notifier = LineNotifier(channel_token="", admin_user_ids=[])
        assert notifier.send(sample_event) is False

    @patch("src.notifications.escalation_notifier.httpx.post")
    def test_send_success(
        self,
        mock_post: MagicMock,
        sample_event: EscalationEvent,
    ) -> None:
        """LINE送信が成功すること。"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        notifier = LineNotifier(
            channel_token="test-token",
            admin_user_ids=["U001", "U002"],
        )
        result = notifier.send(sample_event)
        assert result is True
        assert mock_post.call_count == 2


class TestEscalationNotifier:
    """EscalationNotifier統合テスト。"""

    def test_empty_config(self) -> None:
        """空設定ではデフォルトのemailバックエンドが作成されること。"""
        notifier = EscalationNotifier({})
        assert len(notifier.backends) == 1
        assert isinstance(notifier.backends[0], EmailNotifier)

    def test_email_backend_created(self) -> None:
        """email設定でEmailNotifierが作成されること。"""
        config = {
            "notification": {
                "method": "email",
                "recipients": ["admin@test.com"],
                "smtp": {"host": "smtp.test.com"},
            }
        }
        notifier = EscalationNotifier(config)
        assert len(notifier.backends) == 1
        assert isinstance(notifier.backends[0], EmailNotifier)

    def test_multiple_backends(self) -> None:
        """複数バックエンドが同時に作成されること。"""
        config = {
            "notification": {
                "method": "email,slack",
                "recipients": ["admin@test.com"],
                "smtp": {"host": "smtp.test.com"},
                "slack_webhook_url": "https://hooks.slack.com/test",
            }
        }
        notifier = EscalationNotifier(config)
        assert len(notifier.backends) == 2

    def test_notify_calls_all_backends(
        self, sample_event: EscalationEvent
    ) -> None:
        """notifyが全バックエンドを呼び出すこと。"""
        mock_backend1 = MagicMock()
        mock_backend1.send.return_value = True
        mock_backend2 = MagicMock()
        mock_backend2.send.return_value = False

        notifier = EscalationNotifier({})
        notifier.backends = [mock_backend1, mock_backend2]

        results = notifier.notify(sample_event)
        assert mock_backend1.send.call_count == 1
        assert mock_backend2.send.call_count == 1
        assert len(results) == 2
        assert results[0][1] is True
        assert results[1][1] is False

    def test_notify_handles_exception(
        self, sample_event: EscalationEvent
    ) -> None:
        """バックエンドが例外を投げても他に影響しないこと。"""
        mock_backend1 = MagicMock()
        mock_backend1.send.side_effect = Exception("crash")
        mock_backend2 = MagicMock()
        mock_backend2.send.return_value = True

        notifier = EscalationNotifier({})
        notifier.backends = [mock_backend1, mock_backend2]

        results = notifier.notify(sample_event)
        assert mock_backend2.send.call_count == 1
