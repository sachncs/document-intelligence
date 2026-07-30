"""Typer CLI - the entry point installed as ``docendo``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from docendo.cli.checkup import run as run_checkup
from docendo.config import get_settings
from docendo.eval.cases import load as load_cases
from docendo.eval.driver import run as run_eval
from docendo.eval.summarize import render
from docendo.exceptions import Error
from docendo.ingestion.ingest import run as run_ingest
from docendo.ingestion.scraper import discover
from docendo.logging import configure_logging, get_logger

app = typer.Typer(
    name="docendo",
    help="docendo: grounded RAG agent for document intelligence.",
    no_args_is_help=True,
    add_completion=False,
)
logger = get_logger(__name__)


def configure(verbose: bool = False) -> None:
    settings = get_settings()
    configure_logging("DEBUG" if verbose else settings.log_level)


@app.callback()
def root(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logging."),
) -> None:
    configure(verbose)


@app.command()
def fetch(
    max_docs: int | None = typer.Option(None, "--max", "-n", help="Max PDFs to download."),
    source_dir: Path | None = typer.Option(None, "--source-dir", help="Output directory."),
) -> None:
    """Discover and download PDFs into ``source_dir`` (default: data/raw/)."""
    settings = get_settings()
    target = source_dir or settings.data_raw_dir
    count = 0
    for doc, path in discover(
        target_dir=target,
        max_docs=max_docs or settings.fetch_max_docs,
        settings=settings,
    ):
        typer.echo(f"  {doc.circular_id:60s} -> {path}")
        count += 1
    typer.echo(f"Fetched {count} PDFs to {target}")


@app.command()
def ingest(
    source_dir: Path | None = typer.Option(None, "--source-dir", help="Raw PDF directory."),
    max_docs: int | None = typer.Option(None, "--max", "-n"),
    chunk_size: int | None = typer.Option(None, "--chunk-size", help="Override chunk size (tokens)."),
    chunk_overlap: int | None = typer.Option(None, "--chunk-overlap", help="Override chunk overlap (tokens)."),
) -> None:
    """Run the full ingestion pipeline: scrape -> extract -> index into SQLite."""
    settings = get_settings()
    report = run_ingest(
        raw_dir=source_dir,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_docs=max_docs,
        settings=settings,
    )
    typer.echo(
        json.dumps(
            {
                "discovered": report.total_discovered,
                "downloaded": report.downloaded,
                "extracted": report.extracted,
                "indexed": report.indexed,
                "skipped": report.skipped,
                "failed": len(report.failed),
            },
            indent=2,
        )
    )


@app.command()
def eval(
    dataset: Path | None = typer.Option(None, "--dataset", "-d"),
    concurrency: int | None = typer.Option(None, "--concurrency", "-c"),
    limit: int | None = typer.Option(None, "--limit", "-n"),
    out: Path | None = typer.Option(None, "--out", "-o"),
) -> None:
    """Run the evaluation suite."""
    settings = get_settings()
    cases = load_cases(dataset or settings.eval_dataset_path)
    if limit:
        cases = cases[:limit]
    outcomes = run_eval(
        cases,
        concurrency=concurrency,
        output_path=out or (settings.reports_dir / "results.jsonl"),
        settings=settings,
    )
    typer.echo(
        f"Ran {len(outcomes)} cases. Results written to {out or settings.reports_dir / 'results.jsonl'}"
    )


@app.command()
def report(
    results: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path | None = typer.Option(None, "--out", "-o"),
) -> None:
    """Generate a Markdown report from results.jsonl."""
    from docendo.eval.driver import Outcome
    from docendo.eval.judge import Verdict

    settings = get_settings()
    raw = []
    for line in results.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw.append(json.loads(line))
    cases: list[Outcome] = []
    for r in raw:
        cases.append(
            Outcome(
                case_name=r["case_name"],
                question=r["question"],
                gold_answer=r["gold_answer"],
                metadata=r.get("metadata", {}),
                grounded_answer=r.get("grounded_answer", ""),
                grounded_citations=r.get("grounded_citations", []),
                grounded_hallucination=(
                    Verdict(
                        **{
                            k: v
                            for k, v in r["grounded_hallucination"].items()
                            if k != "claims"
                        }
                    )
                    if r.get("grounded_hallucination")
                    else None
                ),
                ungrounded_answer=r.get("ungrounded_answer", ""),
                ungrounded_hallucination=(
                    Verdict(
                        **{
                            k: v
                            for k, v in r["ungrounded_hallucination"].items()
                            if k != "claims"
                        }
                    )
                    if r.get("ungrounded_hallucination")
                    else None
                ),
            )
        )
    target = out or (settings.reports_dir / "eval_report.md")
    rep = render(cases, target)
    typer.echo(f"Report written to {target}")
    typer.echo(
        f"  Grounded hallucination: {rep.grounded_hallucination_rate:.1%}\n"
        f"  Ungrounded hallucination: {rep.ungrounded_hallucination_rate:.1%}\n"
        f"  Relative reduction: {rep.relative_reduction:+.1%}"
    )


@app.command()
def demo(
    port: int = typer.Option(8501, "--port", "-p"),
    host: str = typer.Option("localhost", "--host"),
) -> None:
    """Launch the Streamlit A/B demo."""
    import subprocess

    target = Path(__file__).parent.parent / "ui" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(target),
        "--server.port",
        str(port),
        "--server.address",
        host,
    ]
    typer.echo("Launching: " + " ".join(cmd))
    subprocess.run(cmd, check=False)


@app.command(name="cases")
def cases(
    dataset: Path | None = typer.Option(None, "--dataset", "-d"),
) -> None:
    """Show summary stats for the eval dataset."""
    settings = get_settings()
    items = load_cases(dataset or settings.eval_dataset_path)
    by_topic: dict[str, int] = {}
    for c in items:
        t = c.metadata.get("topic", "unknown")
        by_topic[t] = by_topic.get(t, 0) + 1
    typer.echo(f"Total cases: {len(items)}")
    for t, n in sorted(by_topic.items()):
        typer.echo(f"  {t}: {n}")


@app.command()
def checkup(
    no_embedding: bool = typer.Option(
        False,
        "--no-embedding",
        help="Skip the live embedding probe (for offline CI).",
    ),
    no_tokenizer: bool = typer.Option(
        False,
        "--no-tokenizer",
        help="Skip the live tokenizer load (for offline CI).",
    ),
) -> None:
    """Run local diagnostics: SQLite, vector extension, embedding/tokenizer reachability."""
    rc = run_checkup(do_embedding=not no_embedding, do_tokenizer=not no_tokenizer)
    raise typer.Exit(code=rc)


def main() -> None:
    """Entry point for ``docendo`` console script."""
    try:
        app()
    except Error as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    main()
