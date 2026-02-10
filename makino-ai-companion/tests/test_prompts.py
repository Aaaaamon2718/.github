"""システムプロンプトと人格設定のテスト。"""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.prompts.persona_config import PersonaConfig, load_persona_config
from src.prompts.system_prompts import build_system_prompt


class TestPersonaConfig:
    """PersonaConfigのテスト。"""

    def test_default_values(self) -> None:
        """デフォルト値が正しいこと。"""
        config = PersonaConfig()
        assert config.name == "牧野 克彦"
        assert config.warmth == 0.7
        assert config.strictness == 0.6
        assert config.professionalism == 0.9
        assert config.empathy == 0.8
        assert len(config.signature_phrases) > 0
        assert len(config.ng_words) > 0

    def test_format_persona_section(self) -> None:
        """人格セクションのフォーマットが正しいこと。"""
        config = PersonaConfig()
        section = config.format_persona_section()
        assert "牧野 克彦" in section
        assert "温かさ" in section
        assert "0.7" in section

    def test_format_ng_words(self) -> None:
        """NGワードセクションのフォーマットが正しいこと。"""
        config = PersonaConfig()
        section = config.format_ng_words()
        assert "ネットスラング" in section
        assert section.startswith("- ")

    def test_format_signature_phrases(self) -> None:
        """象徴的フレーズのフォーマットが正しいこと。"""
        config = PersonaConfig()
        section = config.format_signature_phrases()
        assert "誰にでもできること" in section
        assert "「" in section

    def test_custom_values(self) -> None:
        """カスタム値が反映されること。"""
        config = PersonaConfig(
            name="テスト太郎",
            warmth=1.0,
            ng_words=["テストNG"],
        )
        assert config.name == "テスト太郎"
        assert config.warmth == 1.0
        assert "テストNG" in config.ng_words


class TestLoadPersonaConfig:
    """load_persona_configのテスト。"""

    def test_load_none(self) -> None:
        """Noneの場合はデフォルトが返ること。"""
        config = load_persona_config(None)
        assert config.name == "牧野 克彦"

    def test_load_nonexistent(self) -> None:
        """存在しないパスでデフォルトが返ること。"""
        config = load_persona_config("/nonexistent/path.yaml")
        assert config.name == "牧野 克彦"

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        """YAMLから設定が読み込めること。"""
        config_data = {
            "persona": {
                "name": "テスト先生",
                "role": "テストメンター",
                "traits": {
                    "warmth": 0.9,
                    "strictness": 0.3,
                    "professionalism": 0.8,
                    "empathy": 0.6,
                },
                "signature_phrases": ["テストフレーズ"],
                "ng_words": ["テストNG"],
            }
        }
        yaml_path = tmp_path / "test_config.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True)

        config = load_persona_config(yaml_path)
        assert config.name == "テスト先生"
        assert config.warmth == 0.9
        assert "テストフレーズ" in config.signature_phrases


class TestBuildSystemPrompt:
    """build_system_promptのテスト。"""

    def test_pattern_1(self) -> None:
        """Pattern 1のプロンプトが構築されること。"""
        prompt = build_system_prompt(1)
        assert "牧野生保塾" in prompt
        assert "質問対応" in prompt
        assert "牧野 克彦" in prompt  # デフォルトpersona注入
        assert "（人格定義書完成後に設定）" not in prompt  # プレースホルダーがないこと

    def test_pattern_2(self) -> None:
        """Pattern 2にNGワード・象徴フレーズが含まれること。"""
        prompt = build_system_prompt(2)
        assert "ドクターマーケット" in prompt
        assert "ネットスラング" in prompt  # NGワード
        assert "誰にでもできること" in prompt  # 象徴フレーズ

    def test_pattern_3(self) -> None:
        """Pattern 3のプロンプトが構築されること。"""
        prompt = build_system_prompt(3)
        assert "法人保険" in prompt
        assert "P/L" in prompt
        assert "牧野 克彦" in prompt

    def test_pattern_4(self) -> None:
        """Pattern 4の励まし・メンタリングプロンプト。"""
        prompt = build_system_prompt(4)
        assert "メンター" in prompt
        assert "誰にでもできること" in prompt

    def test_invalid_pattern(self) -> None:
        """無効なパターン番号でValueErrorが出ること。"""
        with pytest.raises(ValueError, match="無効なパターン番号"):
            build_system_prompt(5)

    def test_custom_persona(self) -> None:
        """カスタムPersonaConfigが反映されること。"""
        custom = PersonaConfig(name="カスタム先生", warmth=1.0)
        prompt = build_system_prompt(1, custom)
        assert "カスタム先生" in prompt
        assert "1.0" in prompt

    def test_all_patterns_no_placeholder(self) -> None:
        """全パターンでプレースホルダーが残っていないこと。"""
        for pattern in [1, 2, 3, 4]:
            prompt = build_system_prompt(pattern)
            assert "（人格定義書完成後に設定）" not in prompt
            assert "（NGワードリスト完成後に設定）" not in prompt
            assert "（象徴的フレーズ確定後に設定）" not in prompt
