import argparse
import asyncio
import html
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Table


console = Console()


@dataclass(frozen=True)
class CheckResult:
    url: str
    ok: bool
    status_code: int | None
    elapsed_ms: int
    content_type: str
    title: str
    error: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check URLs concurrently with httpx, asyncio and rich.")
    parser.add_argument("urls", nargs="*", help="URLs to check.")
    parser.add_argument("--from-file", type=Path, help="Read URLs from a text file, one URL per line.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Request timeout in seconds.")
    parser.add_argument("--html-report", type=Path, help="Write a small HTML report.")
    return parser.parse_args()


def load_urls(cli_urls: list[str], file_path: Path | None) -> list[str]:
    urls = list(cli_urls)

    if file_path:
        if not file_path.exists():
            console.print(f"[red]URL file not found:[/red] {file_path}")
            raise SystemExit(1)

        # Linhas vazias e comentarios com # sao ignorados para facilitar testes.
        file_urls = [
            line.strip()
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        urls.extend(file_urls)

    return normalize_urls(urls)


def normalize_urls(urls: Iterable[str]) -> list[str]:
    normalized = []
    for url in urls:
        # Ajuda no uso casual: "example.com" vira "https://example.com".
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        normalized.append(url)
    return normalized


async def check_url(client: httpx.AsyncClient, url: str) -> CheckResult:
    started = time.perf_counter()

    try:
        response = await client.get(url, follow_redirects=True)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        content_type = response.headers.get("content-type", "-").split(";")[0]

        return CheckResult(
            url=url,
            ok=response.is_success,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
            content_type=content_type,
            title=extract_title(response.text) if "html" in content_type else "",
            error="",
        )
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CheckResult(
            url=url,
            ok=False,
            status_code=None,
            elapsed_ms=elapsed_ms,
            content_type="-",
            title="",
            error=str(exc),
        )


def extract_title(body: str) -> str:
    lower_body = body.lower()
    start = lower_body.find("<title>")
    end = lower_body.find("</title>")

    if start == -1 or end == -1 or end <= start:
        return ""

    title = body[start + len("<title>") : end].strip()
    return " ".join(html.unescape(title).split())


async def check_all(urls: list[str], timeout: float, show_progress: bool = True) -> list[CheckResult]:
    limits = httpx.Limits(max_connections=10)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        # asyncio.as_completed mostra resultado conforme cada request termina.
        tasks = [check_url(client, url) for url in urls]
        results: list[CheckResult] = []

        if not show_progress:
            for done in asyncio.as_completed(tasks):
                results.append(await done)
            return sorted(results, key=lambda item: item.url)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Checking URLs", total=len(tasks))

            for done in asyncio.as_completed(tasks):
                results.append(await done)
                progress.advance(task_id)

    return sorted(results, key=lambda item: item.url)


def print_results(results: list[CheckResult]) -> None:
    table = Table(title="URL Check Results")
    table.add_column("Status", justify="center")
    table.add_column("Code", justify="right")
    table.add_column("Time", justify="right")
    table.add_column("Content Type")
    table.add_column("URL")
    table.add_column("Title / Error")

    for result in results:
        status = "[green]OK[/green]" if result.ok else "[red]FAIL[/red]"
        detail = result.title or result.error
        table.add_row(
            status,
            str(result.status_code or "-"),
            f"{result.elapsed_ms} ms",
            result.content_type,
            result.url,
            detail[:80],
        )

    console.print(table)

    ok_count = sum(result.ok for result in results)
    fail_count = len(results) - ok_count
    console.print(Panel.fit(f"[green]{ok_count} OK[/green] | [red]{fail_count} failed[/red]", title="Summary"))


def write_html_report(results: list[CheckResult], output: Path) -> None:
    rows = "\n".join(
        "<tr>"
        f"<td>{'OK' if result.ok else 'FAIL'}</td>"
        f"<td>{html.escape(str(result.status_code or '-'))}</td>"
        f"<td>{result.elapsed_ms} ms</td>"
        f"<td>{html.escape(result.content_type)}</td>"
        f"<td><a href=\"{html.escape(result.url)}\">{html.escape(result.url)}</a></td>"
        f"<td>{html.escape(result.title or result.error)}</td>"
        "</tr>"
        for result in results
    )

    output.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>URL Check Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 32px; color: #1f2937; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; }}
    th {{ background: #f9fafb; }}
    tr:hover {{ background: #f3f4f6; }}
  </style>
</head>
<body>
  <h1>URL Check Report</h1>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>Code</th>
        <th>Time</th>
        <th>Content Type</th>
        <th>URL</th>
        <th>Title / Error</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    urls = load_urls(args.urls, args.from_file)

    if not urls:
        console.print("[red]Pass at least one URL or use --from-file.[/red]")
        raise SystemExit(1)

    results = asyncio.run(check_all(urls, args.timeout))
    print_results(results)

    if args.html_report:
        write_html_report(results, args.html_report)
        console.print(f"[green]HTML report written:[/green] {args.html_report}")
