"""
Data persistence layer.

Saves plain-text reports and structured JSON results to local disk.
Does not perform analysis, scoring, or formatting — it consumes outputs
from those layers only.

Default output directories:
  Plain-text reports  →  outputs/reports/
  Structured results  →  outputs/results/
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.utils.helpers import normalize_ticker


_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({"txt", "json", "md"})


class StorageError(Exception):
    """Raised when a report or result cannot be saved to disk."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_report_filename(
    ticker: str,
    timestamp: datetime | None = None,
    extension: str = "txt",
) -> str:
    """Return a safe, deterministic filename for a report or result file.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL"). Case-insensitive.
        timestamp: Datetime to embed in the filename. Defaults to current UTC time.
        extension: File extension — "txt", ".txt", "json", or ".json".

    Returns:
        A filename string of the form ``TICKER_YYYYMMDD_HHMMSS.extension``.

    Raises:
        StorageError: If ticker is invalid or extension is not supported.
    """
    try:
        symbol = normalize_ticker(ticker)
    except ValueError as exc:
        raise StorageError(str(exc)) from exc
    ext = _normalise_extension(extension)
    ts = timestamp if timestamp is not None else datetime.now(tz=timezone.utc)
    stamp = ts.strftime("%Y%m%d_%H%M%S")
    return f"{symbol}_{stamp}.{ext}"


def ensure_output_dir(output_dir: str | Path) -> Path:
    """Create output_dir (and any parents) if it does not exist.

    Args:
        output_dir: Directory path to create.

    Returns:
        The resolved Path object.

    Raises:
        StorageError: If the directory cannot be created.
    """
    path = Path(output_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError(
            f"Could not create output directory '{path}': {exc}"
        ) from exc
    return path


def save_text_report(
    report_text: str,
    ticker: str,
    output_dir: str | Path = "outputs/reports",
    timestamp: datetime | None = None,
) -> Path:
    """Save a plain-text report to disk as a UTF-8 .txt file.

    Args:
        report_text: The report string to save. Must be non-empty.
        ticker: Stock ticker symbol used in the filename.
        output_dir: Directory to write into (created if absent).
        timestamp: Datetime to embed in the filename. Defaults to current UTC time.

    Returns:
        The full Path to the saved file.

    Raises:
        StorageError: If report_text is blank, ticker is invalid, or a
            filesystem error occurs while writing.
    """
    if not isinstance(report_text, str) or not report_text.strip():
        raise StorageError("report_text must be a non-empty string.")
    try:
        normalize_ticker(ticker)
    except ValueError as exc:
        raise StorageError(str(exc)) from exc
    directory = ensure_output_dir(output_dir)
    filename = build_report_filename(ticker, timestamp=timestamp, extension="txt")
    filepath = directory / filename
    try:
        filepath.write_text(report_text, encoding="utf-8")
    except OSError as exc:
        raise StorageError(
            f"Could not write text report to '{filepath}': {exc}"
        ) from exc
    return filepath


def save_markdown_report(
    report_text: str,
    ticker: str,
    output_dir: str | Path = "outputs/reports",
    timestamp: datetime | None = None,
) -> Path:
    """Save a Markdown report to disk as a UTF-8 .md file.

    Args:
        report_text: The Markdown string to save. Must be non-empty.
        ticker: Stock ticker symbol used in the filename.
        output_dir: Directory to write into (created if absent).
        timestamp: Datetime to embed in the filename. Defaults to current UTC time.

    Returns:
        The full Path to the saved file.

    Raises:
        StorageError: If report_text is blank, ticker is invalid, or a
            filesystem error occurs while writing.
    """
    if not isinstance(report_text, str) or not report_text.strip():
        raise StorageError("report_text must be a non-empty string.")
    try:
        normalize_ticker(ticker)
    except ValueError as exc:
        raise StorageError(str(exc)) from exc
    directory = ensure_output_dir(output_dir)
    filename = build_report_filename(ticker, timestamp=timestamp, extension="md")
    filepath = directory / filename
    try:
        filepath.write_text(report_text, encoding="utf-8")
    except OSError as exc:
        raise StorageError(
            f"Could not write Markdown report to '{filepath}': {exc}"
        ) from exc
    return filepath


def save_json_result(
    result: Mapping[str, Any] | BaseModel,
    ticker: str,
    output_dir: str | Path = "outputs/results",
    timestamp: datetime | None = None,
) -> Path:
    """Save a structured result to disk as a pretty-printed UTF-8 .json file.

    Accepts a plain dict/mapping or a Pydantic BaseModel. BaseModel instances
    are serialised via ``model_dump(mode="json")`` so all field types (including
    datetime and nested models) are JSON-compatible.

    Args:
        result: The data to save — a mapping or Pydantic BaseModel instance.
        ticker: Stock ticker symbol used in the filename.
        output_dir: Directory to write into (created if absent).
        timestamp: Datetime to embed in the filename. Defaults to current UTC time.

    Returns:
        The full Path to the saved file.

    Raises:
        StorageError: If ticker is invalid, result cannot be serialised, or a
            filesystem error occurs while writing.
    """
    try:
        normalize_ticker(ticker)
    except ValueError as exc:
        raise StorageError(str(exc)) from exc
    data = _to_json_dict(result)
    directory = ensure_output_dir(output_dir)
    filename = build_report_filename(ticker, timestamp=timestamp, extension="json")
    filepath = directory / filename
    try:
        json_text = json.dumps(data, indent=2, sort_keys=True, default=_json_default)
        filepath.write_text(json_text, encoding="utf-8")
    except (TypeError, ValueError, OSError) as exc:
        raise StorageError(
            f"Could not write JSON result to '{filepath}': {exc}"
        ) from exc
    return filepath


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise_extension(extension: object) -> str:
    if not isinstance(extension, str):
        raise StorageError(
            f"extension must be a string, got {type(extension).__name__}."
        )
    ext = extension.lstrip(".")
    if ext not in _SUPPORTED_EXTENSIONS:
        raise StorageError(
            f"Unsupported extension '{extension}'. "
            f"Supported extensions: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}."
        )
    return ext


def _to_json_dict(result: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    return dict(result)


def _json_default(obj: Any) -> Any:
    """Fallback JSON serializer for types not handled by the standard library."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable.")
