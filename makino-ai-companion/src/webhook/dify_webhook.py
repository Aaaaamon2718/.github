"""Dify Webhookの送受信を管理するモジュール。

DifyエージェントからのWebhookイベントを受信し、
Google Apps Scriptへの転送を行う。
"""

import json
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class DifyWebhookClient:
    """Dify Webhookクライアント。

    Difyプラットフォームとの通信を管理し、
    イベントデータをGoogle Apps Scriptへ転送する。
    """

    def __init__(
        self,
        gas_endpoint: str,
        retry_count: int = 3,
        retry_delay: float = 5.0,
    ) -> None:
        """初期化。

        Args:
            gas_endpoint: Google Apps ScriptのWebhookエンドポイントURL
            retry_count: リトライ回数
            retry_delay: リトライ間隔（秒）
        """
        self.gas_endpoint = gas_endpoint
        self.retry_count = retry_count
        self.retry_delay = retry_delay

    def forward_to_gas(self, payload: dict) -> bool:
        """ログデータをGoogle Apps Scriptへ転送する。

        Args:
            payload: 転送するデータ（ConversationLog.to_dict()形式）

        Returns:
            転送成功時True
        """
        for attempt in range(1, self.retry_count + 1):
            try:
                response = requests.post(
                    self.gas_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )

                if response.status_code == 200:
                    logger.info("GASへのデータ転送成功")
                    return True

                logger.warning(
                    f"GAS転送失敗 (attempt {attempt}/{self.retry_count}): "
                    f"status={response.status_code}"
                )

            except requests.RequestException as e:
                logger.warning(
                    f"GAS転送エラー (attempt {attempt}/{self.retry_count}): {e}"
                )

            if attempt < self.retry_count:
                time.sleep(self.retry_delay)

        logger.error(f"GASへのデータ転送が{self.retry_count}回失敗しました")
        return False

    def send_escalation_notification(
        self,
        question: str,
        user_id: str,
        confidence: float,
        category: str,
        notification_endpoint: Optional[str] = None,
    ) -> bool:
        """エスカレーション通知を送信する。

        Args:
            question: エスカレーション対象の質問
            user_id: ユーザーID
            confidence: 確信度スコア
            category: 質問カテゴリ
            notification_endpoint: 通知先エンドポイント（省略時はGASエンドポイントを使用）

        Returns:
            通知成功時True
        """
        endpoint = notification_endpoint or self.gas_endpoint

        payload = {
            "type": "escalation",
            "question": question,
            "user_id": user_id,
            "confidence": confidence,
            "category": category,
            "message": f"エスカレーション発生: 確信度={confidence:.2f}, カテゴリ={category}",
        }

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if response.status_code == 200:
                logger.info(f"エスカレーション通知送信成功: user={user_id}")
                return True

            logger.warning(f"エスカレーション通知失敗: status={response.status_code}")
            return False

        except requests.RequestException as e:
            logger.error(f"エスカレーション通知エラー: {e}")
            return False
