"""Documentation tests: KNOWN_GAPS at repo root, README quickstart end-to-end."""

from __future__ import annotations

from pathlib import Path

from docendo.cli.main import app
from docendo.config import reset_settings_cache
from typer.testing import CliRunner


class TestKnownGapsLocation:
    def test_known_gaps_at_repo_root(self) -> None:
        p = Path("KNOWN_GAPS.md")
        assert p.exists(), "KNOWN_GAPS.md must exist at repo root"
        text = p.read_text()
        for item in (
            "MCP server",
            "Agent Builder",
            "Elastic",
            "Dockerfile",
        ):
            assert item in text, f"{item!r} missing from KNOWN_GAPS.md"

    def test_no_dead_env_vars_in_env_example(self) -> None:
        text = Path(".env.example").read_text()
        for dead in ("ELASTIC_", "BFSI_", "MINIMAX_", "RBI_"):
            assert dead not in text, f"dead prefix {dead!r} in .env.example"
        for live in ("CHAT_KEY", "VECTOR_BASE", "STORE_PATH"):
            assert live in text, f"live env var {live!r} missing from .env.example"


class TestDocsStructure:
    def test_no_dead_branding_in_user_docs(self) -> None:
        """The user-facing docs (excluding KNOWN_GAPS) must not reference the
        old brand or dead defaults."""
        for path in ("README.md", "docs/quickstart.md", "docs/installation.md"):
            text = Path(path).read_text()
            assert "BFSI-RBI" not in text, f"BFSI-RBI in {path}"


class TestReadmeQuickstartEnd2End:
    def test_docendo_checkup_offline_works(self, tmp_path, monkeypatch) -> None:
        """The README's 'docendo checkup --no-embedding --no-tokenizer' runs."""
        monkeypatch.setenv("STORE_PATH", str(tmp_path / "docendo.sqlite3"))
        monkeypatch.setenv("VECTOR_KEY", "test")
        monkeypatch.setenv("VECTOR_BASE", "https://embed.example.com")
        monkeypatch.setenv("VECTOR_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("TOKENIZER_MODEL", "Qwen/Qwen3-Embedding-8B")
        monkeypatch.setenv("VECTOR_DIMS", "4")
        monkeypatch.setenv("CHAT_KEY", "test")
        reset_settings_cache()
        try:
            runner = CliRunner()
            result = runner.invoke(
                app, ["checkup", "--no-embedding", "--no-tokenizer"]
            )
            assert result.exit_code == 0
            assert "All checks passed" in result.stdout
        finally:
            reset_settings_cache()
