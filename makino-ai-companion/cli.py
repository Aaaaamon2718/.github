"""牧野生保塾 AI伴走システム - 開発者向けCLIツール。

ナレッジベース管理、ログエクスポート、KPI確認、
プロンプトテストを開発者がターミナルから実行するためのCLI。

Usage:
    python cli.py knowledge stats
    python cli.py knowledge validate
    python cli.py knowledge rebuild-index
    python cli.py logs export --format csv
    python cli.py logs metrics
    python cli.py logs metrics --from 2025-01-01 --to 2025-01-31
    python cli.py prompt test --pattern 1 --question "決算書の見方を教えて"
    python cli.py server start
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """設定ファイルを読み込む。"""
    config_path = BASE_DIR / "config" / "settings.yaml"
    with open(config_path, encoding="utf-8") as f:
        content = f.read()
    for key, value in os.environ.items():
        content = content.replace(f"${{{key}}}", value)
    return yaml.safe_load(content)


# ============================================================
# ナレッジベース管理
# ============================================================

def cmd_knowledge_stats(args: argparse.Namespace) -> None:
    """ナレッジベースの統計情報を表示する。"""
    from src.chat.rag import KnowledgeLoader

    config = load_config()
    knowledge_dir = BASE_DIR / config.get("rag", {}).get("knowledge_dir", "knowledge")
    loader = KnowledgeLoader(knowledge_dir)
    chunks = loader.load_all()

    # カテゴリ別集計
    categories: dict[str, int] = {}
    sources: dict[str, int] = {}
    for chunk in chunks:
        categories[chunk.category] = categories.get(chunk.category, 0) + 1
        sources[chunk.source_file] = sources.get(chunk.source_file, 0) + 1

    print(f"\n=== ナレッジベース統計 ===")
    print(f"総チャンク数: {len(chunks)}")
    print(f"ソースファイル数: {len(sources)}")
    print(f"\nカテゴリ別:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}チャンク")
    print(f"\nファイル別:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1])[:20]:
        print(f"  {src}: {count}チャンク")


def cmd_knowledge_validate(args: argparse.Namespace) -> None:
    """ナレッジベースのバリデーションを実行する。"""
    from src.knowledge_base.processor import load_knowledge_csv, validate_knowledge_base

    config = load_config()
    knowledge_dir = BASE_DIR / config.get("rag", {}).get("knowledge_dir", "knowledge")

    md_files = list(knowledge_dir.rglob("*.md"))
    csv_files = list(knowledge_dir.rglob("*.csv"))

    print(f"\n=== ナレッジベース検証 ===")
    print(f"Markdownファイル: {len(md_files)}件")
    print(f"CSVファイル: {len(csv_files)}件")

    errors = 0
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        if len(content.strip()) < 10:
            print(f"  [WARN] 内容が少ない: {md_file}")
            errors += 1

    if errors == 0:
        print("  全ファイル正常")
    else:
        print(f"\n  警告: {errors}件の問題が見つかりました")


# ============================================================
# ログ管理
# ============================================================

def cmd_logs_export(args: argparse.Namespace) -> None:
    """会話ログをCSV/JSONにエクスポートする（GitHub監査用）。"""
    from src.database.models import get_connection
    from src.database.operations import export_to_csv

    config = load_config()
    db_path = BASE_DIR / config.get("database", {}).get("sqlite", {}).get("path", "data/conversations.db")

    if not db_path.exists():
        print("データベースが見つかりません。サーバーを先に起動してください。")
        return

    conn = get_connection(db_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = BASE_DIR / "logs" / "exports"
    output_path = export_dir / f"conversations_{timestamp}.csv"

    count = export_to_csv(conn, output_path, args.date_from, args.date_to)
    conn.close()

    if count > 0:
        print(f"\nエクスポート完了: {count}件 → {output_path}")
        print(f"※ git add {output_path.relative_to(BASE_DIR)} でGitHubにコミット可能")
    else:
        print("エクスポート対象のデータがありません。")


def cmd_logs_metrics(args: argparse.Namespace) -> None:
    """KPI指標を表示する。"""
    from src.database.models import get_connection
    from src.database.operations import calculate_metrics, get_pattern_breakdown

    config = load_config()
    db_path = BASE_DIR / config.get("database", {}).get("sqlite", {}).get("path", "data/conversations.db")

    if not db_path.exists():
        print("データベースが見つかりません。")
        return

    conn = get_connection(db_path)
    metrics = calculate_metrics(conn, args.date_from, args.date_to)
    breakdown = get_pattern_breakdown(conn, args.date_from, args.date_to)
    conn.close()

    kpi = config.get("kpi", {})

    print(f"\n=== KPI指標 ===")
    print(f"総質問数:        {metrics['total_questions']}")
    print(f"回答成功率:      {metrics['answer_success_rate']:.1%}  (目標: {kpi.get('answer_success_rate', 0.8):.0%})")
    print(f"ユーザー満足度:  {metrics['user_satisfaction']:.1%}  (目標: {kpi.get('user_satisfaction', 0.85):.0%})")
    print(f"平均確信度:      {metrics['average_confidence']:.2f}  (目標: {kpi.get('average_confidence', 0.7):.1f})")
    print(f"エスカレーション: {metrics['escalation_count']}件 ({metrics['escalation_rate']:.1%})")

    if breakdown:
        print(f"\nパターン別:")
        for pattern, data in breakdown.items():
            print(f"  {pattern}: {data['count']}件 (確信度: {data['avg_confidence']:.2f})")


# ============================================================
# プロンプトテスト
# ============================================================

def cmd_prompt_test(args: argparse.Namespace) -> None:
    """プロンプトを対話的にテストする。"""
    from src.chat.engine import ChatEngine

    config = load_config()
    claude_config = config.get("claude", {})
    api_key = claude_config.get("api_key", os.environ.get("ANTHROPIC_API_KEY", ""))

    if not api_key:
        print("ANTHROPIC_API_KEY が設定されていません。")
        return

    engine = ChatEngine(
        api_key=api_key,
        model=claude_config.get("model", "claude-sonnet-4-5-20250929"),
        knowledge_dir=str(BASE_DIR / config.get("rag", {}).get("knowledge_dir", "knowledge")),
        config_path=str(BASE_DIR / "config" / "settings.yaml"),
    )

    if args.question:
        # 単発テスト
        response = engine.chat(args.question, pattern=args.pattern)
        print(f"\n--- Pattern {args.pattern} ---")
        print(f"質問: {args.question}")
        print(f"回答: {response.answer}")
        print(f"確信度: {response.confidence:.2f}")
        print(f"出典: {', '.join(response.sources) if response.sources else 'なし'}")
        print(f"トークン: {response.tokens_used}")
        if response.should_escalate:
            print(f"[ESCALATION] {response.escalation_reason}")
    else:
        # 対話モード
        print(f"\n=== 対話テスト (Pattern {args.pattern}) ===")
        print("'quit' で終了\n")
        while True:
            question = input("あなた > ").strip()
            if question.lower() in ("quit", "exit", "q"):
                break
            if not question:
                continue
            response = engine.chat(question, pattern=args.pattern)
            print(f"\n牧野: {response.answer}")
            print(f"  [確信度: {response.confidence:.2f}]\n")


# ============================================================
# サーバー起動
# ============================================================

def cmd_server_start(args: argparse.Namespace) -> None:
    """FastAPIサーバーを起動する。"""
    import uvicorn

    config = load_config()
    server_config = config.get("server", {})

    print(f"\nサーバー起動: http://localhost:{server_config.get('port', 8000)}")
    uvicorn.run(
        "app:app",
        host=server_config.get("host", "0.0.0.0"),
        port=args.port or server_config.get("port", 8000),
        reload=args.reload,
    )


# ============================================================
# メイン
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="牧野生保塾 AI伴走システム - 開発者CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # knowledge サブコマンド
    kb = subparsers.add_parser("knowledge", help="ナレッジベース管理")
    kb_sub = kb.add_subparsers(dest="kb_action")
    kb_sub.add_parser("stats", help="統計情報を表示")
    kb_sub.add_parser("validate", help="バリデーション実行")

    # logs サブコマンド
    logs = subparsers.add_parser("logs", help="ログ管理")
    logs_sub = logs.add_subparsers(dest="logs_action")

    export_p = logs_sub.add_parser("export", help="CSVエクスポート")
    export_p.add_argument("--from", dest="date_from", help="開始日 (YYYY-MM-DD)")
    export_p.add_argument("--to", dest="date_to", help="終了日 (YYYY-MM-DD)")

    metrics_p = logs_sub.add_parser("metrics", help="KPI指標表示")
    metrics_p.add_argument("--from", dest="date_from", help="開始日")
    metrics_p.add_argument("--to", dest="date_to", help="終了日")

    # prompt サブコマンド
    prompt = subparsers.add_parser("prompt", help="プロンプトテスト")
    prompt_sub = prompt.add_subparsers(dest="prompt_action")
    test_p = prompt_sub.add_parser("test", help="対話テスト")
    test_p.add_argument("--pattern", type=int, default=1, choices=[1, 2, 3, 4])
    test_p.add_argument("--question", "-q", type=str, help="単発テスト用の質問")

    # server サブコマンド
    server = subparsers.add_parser("server", help="サーバー管理")
    server_sub = server.add_subparsers(dest="server_action")
    start_p = server_sub.add_parser("start", help="サーバー起動")
    start_p.add_argument("--port", type=int, help="ポート番号")
    start_p.add_argument("--reload", action="store_true", help="ホットリロード有効")

    args = parser.parse_args()

    if args.command == "knowledge":
        if args.kb_action == "stats":
            cmd_knowledge_stats(args)
        elif args.kb_action == "validate":
            cmd_knowledge_validate(args)
        else:
            kb.print_help()
    elif args.command == "logs":
        if args.logs_action == "export":
            cmd_logs_export(args)
        elif args.logs_action == "metrics":
            cmd_logs_metrics(args)
        else:
            logs.print_help()
    elif args.command == "prompt":
        if args.prompt_action == "test":
            cmd_prompt_test(args)
        else:
            prompt.print_help()
    elif args.command == "server":
        if args.server_action == "start":
            cmd_server_start(args)
        else:
            server.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
