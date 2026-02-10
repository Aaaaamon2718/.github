"""エスカレーション通知サービス。

エスカレーション発生時に管理者へ通知を送信する。
メール(SMTP)、Slack(Webhook)、LINE(Messaging API) に対応。
"""

import json
import logging
import os
import smtplib
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EscalationEvent:
    """エスカレーションイベントデータ。"""

    conversation_id: int
    session_id: str
    user_id: str
    question: str
    reason: str
    confidence: float
    category: str
    timestamp: str = ""


class NotificationBackend(ABC):
    """通知バックエンドの抽象基底クラス。"""

    @abstractmethod
    def send(self, event: EscalationEvent) -> bool:
        """通知を送信する。成功時 True を返す。"""
        ...


class EmailNotifier(NotificationBackend):
    """SMTP メール通知。"""

    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        from_address: str = "",
        recipients: Optional[list[str]] = None,
    ) -> None:
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST", "")
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user or os.environ.get("SMTP_USER", "")
        self.smtp_password = smtp_password or os.environ.get("SMTP_PASSWORD", "")
        self.from_address = from_address or self.smtp_user
        self.recipients = recipients or []

    def _build_message(self, event: EscalationEvent) -> MIMEMultipart:
        """メールメッセージを構築する。"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[エスカレーション] {event.category} - {event.reason}"
        msg["From"] = self.from_address
        msg["To"] = ", ".join(self.recipients)

        text = (
            f"エスカレーション通知\n"
            f"====================\n\n"
            f"会話ID: {event.conversation_id}\n"
            f"セッション: {event.session_id}\n"
            f"ユーザー: {event.user_id}\n"
            f"カテゴリ: {event.category}\n"
            f"理由: {event.reason}\n"
            f"確信度: {event.confidence:.2f}\n"
            f"日時: {event.timestamp}\n\n"
            f"質問内容:\n{event.question}\n"
        )
        msg.attach(MIMEText(text, "plain", "utf-8"))

        html = (
            f"<h2>エスカレーション通知</h2>"
            f"<table border='1' cellpadding='8' style='border-collapse:collapse;'>"
            f"<tr><td><b>会話ID</b></td><td>{event.conversation_id}</td></tr>"
            f"<tr><td><b>セッション</b></td><td>{event.session_id}</td></tr>"
            f"<tr><td><b>ユーザー</b></td><td>{event.user_id}</td></tr>"
            f"<tr><td><b>カテゴリ</b></td><td>{event.category}</td></tr>"
            f"<tr><td><b>理由</b></td><td>{event.reason}</td></tr>"
            f"<tr><td><b>確信度</b></td><td>{event.confidence:.2f}</td></tr>"
            f"<tr><td><b>日時</b></td><td>{event.timestamp}</td></tr>"
            f"</table>"
            f"<h3>質問内容</h3>"
            f"<blockquote>{event.question}</blockquote>"
        )
        msg.attach(MIMEText(html, "html", "utf-8"))

        return msg

    def send(self, event: EscalationEvent) -> bool:
        """SMTPでメールを送信する。"""
        if not self.smtp_host or not self.recipients:
            logger.warning("SMTP設定が不完全です。メール送信をスキップします。")
            return False

        try:
            msg = self._build_message(event)
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            logger.info(
                f"エスカレーションメール送信完了: conv_id={event.conversation_id}"
            )
            return True
        except Exception as e:
            logger.error(f"メール送信エラー: {e}")
            return False


class SlackNotifier(NotificationBackend):
    """Slack Webhook 通知。"""

    def __init__(self, webhook_url: str = "") -> None:
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL", "")

    def send(self, event: EscalationEvent) -> bool:
        """Slack Webhookで通知を送信する。"""
        if not self.webhook_url:
            logger.warning("Slack Webhook URLが未設定です。")
            return False

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"エスカレーション: {event.category}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*理由:*\n{event.reason}"},
                        {"type": "mrkdwn", "text": f"*確信度:*\n{event.confidence:.2f}"},
                        {"type": "mrkdwn", "text": f"*ユーザー:*\n{event.user_id}"},
                        {"type": "mrkdwn", "text": f"*会話ID:*\n{event.conversation_id}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*質問内容:*\n> {event.question[:500]}",
                    },
                },
            ],
        }

        try:
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            logger.info(
                f"Slack通知送信完了: conv_id={event.conversation_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Slack通知エラー: {e}")
            return False


class LineNotifier(NotificationBackend):
    """LINE Messaging API 通知。"""

    API_URL = "https://api.line.me/v2/bot/message/push"

    def __init__(
        self,
        channel_token: str = "",
        admin_user_ids: Optional[list[str]] = None,
    ) -> None:
        self.channel_token = channel_token or os.environ.get("LINE_CHANNEL_TOKEN", "")
        self.admin_user_ids = admin_user_ids or []

    def send(self, event: EscalationEvent) -> bool:
        """LINE Messaging APIで通知を送信する。"""
        if not self.channel_token or not self.admin_user_ids:
            logger.warning("LINE設定が不完全です。")
            return False

        text = (
            f"[エスカレーション]\n"
            f"カテゴリ: {event.category}\n"
            f"理由: {event.reason}\n"
            f"確信度: {event.confidence:.2f}\n"
            f"ユーザー: {event.user_id}\n\n"
            f"質問: {event.question[:300]}"
        )

        headers = {
            "Authorization": f"Bearer {self.channel_token}",
            "Content-Type": "application/json",
        }

        success = True
        for user_id in self.admin_user_ids:
            payload = {
                "to": user_id,
                "messages": [{"type": "text", "text": text}],
            }
            try:
                response = httpx.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=10,
                )
                response.raise_for_status()
            except Exception as e:
                logger.error(f"LINE通知エラー ({user_id}): {e}")
                success = False

        if success:
            logger.info(
                f"LINE通知送信完了: conv_id={event.conversation_id}"
            )
        return success


class EscalationNotifier:
    """エスカレーション通知の統合管理クラス。

    設定に基づいて適切なバックエンドを初期化し、通知を送信する。
    複数バックエンドの同時使用に対応。
    """

    def __init__(self, config: dict) -> None:
        self.backends: list[NotificationBackend] = []
        self._setup_backends(config)

    def _setup_backends(self, config: dict) -> None:
        """設定からバックエンドを初期化する。"""
        notification = config.get("notification", {})
        method = notification.get("method", "email")
        recipients = notification.get("recipients", [])

        methods = [m.strip() for m in method.split(",")]

        for m in methods:
            if m == "email":
                smtp = notification.get("smtp", {})
                self.backends.append(EmailNotifier(
                    smtp_host=smtp.get("host", ""),
                    smtp_port=smtp.get("port", 587),
                    smtp_user=smtp.get("user", ""),
                    smtp_password=smtp.get("password", ""),
                    from_address=smtp.get("from_address", ""),
                    recipients=recipients,
                ))
            elif m == "slack":
                self.backends.append(SlackNotifier(
                    webhook_url=notification.get("slack_webhook_url", ""),
                ))
            elif m == "line":
                self.backends.append(LineNotifier(
                    channel_token=notification.get("line_channel_token", ""),
                    admin_user_ids=notification.get("line_admin_user_ids", []),
                ))
            else:
                logger.warning(f"未対応の通知方式: {m}")

        if not self.backends:
            logger.warning("有効な通知バックエンドがありません。")

    def notify(self, event: EscalationEvent) -> list[tuple[str, bool]]:
        """全バックエンドに通知を送信する。

        Returns:
            [(バックエンド名, 送信成否), ...] のリスト
        """
        results: list[tuple[str, bool]] = []
        for backend in self.backends:
            name = type(backend).__name__
            try:
                results.append((name, backend.send(event)))
            except Exception as e:
                logger.error(f"通知送信エラー ({name}): {e}")
                results.append((name, False))
        return results
