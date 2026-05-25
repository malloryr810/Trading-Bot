"""
Unit tests for app/data/storage.py.

All filesystem operations use pytest's tmp_path fixture — nothing is written
to real project directories.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from app.data.storage import (
    StorageError,
    build_report_filename,
    ensure_output_dir,
    save_json_result,
    save_text_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = datetime(2024, 6, 15, 9, 30, 0, tzinfo=timezone.utc)
_TS_STAMP = "20240615_093000"


class _SimpleModel(BaseModel):
    ticker: str
    score: float
    note: str | None = None


def _make_model() -> _SimpleModel:
    return _SimpleModel(ticker="AAPL", score=72.5, note="test")


# ---------------------------------------------------------------------------
# build_report_filename — return type and format
# ---------------------------------------------------------------------------

class TestBuildReportFilename:
    def test_returns_string(self):
        result = build_report_filename("AAPL", timestamp=_TS)
        assert isinstance(result, str)

    def test_deterministic_with_timestamp(self):
        assert build_report_filename("AAPL", timestamp=_TS) == f"AAPL_{_TS_STAMP}.txt"

    def test_ticker_uppercased(self):
        assert build_report_filename("aapl", timestamp=_TS).startswith("AAPL_")

    def test_ticker_whitespace_stripped(self):
        assert build_report_filename("  aapl  ", timestamp=_TS).startswith("AAPL_")

    def test_default_extension_is_txt(self):
        assert build_report_filename("AAPL", timestamp=_TS).endswith(".txt")

    def test_explicit_txt_extension(self):
        result = build_report_filename("AAPL", timestamp=_TS, extension="txt")
        assert result.endswith(".txt")

    def test_dotted_txt_extension(self):
        result = build_report_filename("AAPL", timestamp=_TS, extension=".txt")
        assert result.endswith(".txt")

    def test_json_extension(self):
        result = build_report_filename("AAPL", timestamp=_TS, extension="json")
        assert result.endswith(".json")

    def test_dotted_json_extension(self):
        result = build_report_filename("AAPL", timestamp=_TS, extension=".json")
        assert result.endswith(".json")

    def test_timestamp_embedded_correctly(self):
        result = build_report_filename("AAPL", timestamp=_TS)
        assert _TS_STAMP in result

    def test_no_path_separators_in_filename(self):
        result = build_report_filename("AAPL", timestamp=_TS)
        assert "/" not in result
        assert "\\" not in result

    def test_no_timestamp_uses_current_time(self):
        result = build_report_filename("AAPL")
        assert re.match(r"^AAPL_\d{8}_\d{6}\.txt$", result)

    def test_json_filename_format(self):
        result = build_report_filename("MSFT", timestamp=_TS, extension="json")
        assert result == f"MSFT_{_TS_STAMP}.json"


# ---------------------------------------------------------------------------
# build_report_filename — ticker validation
# ---------------------------------------------------------------------------

class TestBuildReportFilenameTickerValidation:
    def test_empty_string_raises(self):
        with pytest.raises(StorageError):
            build_report_filename("", timestamp=_TS)

    def test_whitespace_only_raises(self):
        with pytest.raises(StorageError):
            build_report_filename("   ", timestamp=_TS)

    def test_none_ticker_raises(self):
        with pytest.raises(StorageError):
            build_report_filename(None, timestamp=_TS)  # type: ignore[arg-type]

    def test_int_ticker_raises(self):
        with pytest.raises(StorageError):
            build_report_filename(123, timestamp=_TS)  # type: ignore[arg-type]

    def test_error_message_mentions_string(self):
        with pytest.raises(StorageError, match="string"):
            build_report_filename(42, timestamp=_TS)  # type: ignore[arg-type]

    def test_error_message_for_empty_ticker(self):
        with pytest.raises(StorageError, match="empty"):
            build_report_filename("", timestamp=_TS)


# ---------------------------------------------------------------------------
# build_report_filename — extension validation
# ---------------------------------------------------------------------------

class TestBuildReportFilenameExtensionValidation:
    def test_csv_extension_raises(self):
        with pytest.raises(StorageError):
            build_report_filename("AAPL", timestamp=_TS, extension="csv")

    def test_pdf_extension_raises(self):
        with pytest.raises(StorageError):
            build_report_filename("AAPL", timestamp=_TS, extension=".pdf")

    def test_empty_extension_raises(self):
        with pytest.raises(StorageError):
            build_report_filename("AAPL", timestamp=_TS, extension="")

    def test_dot_only_extension_raises(self):
        with pytest.raises(StorageError):
            build_report_filename("AAPL", timestamp=_TS, extension=".")

    def test_error_message_mentions_unsupported_extension(self):
        with pytest.raises(StorageError, match="csv"):
            build_report_filename("AAPL", timestamp=_TS, extension="csv")

    def test_error_message_mentions_supported_extensions(self):
        with pytest.raises(StorageError, match="json"):
            build_report_filename("AAPL", timestamp=_TS, extension="csv")


# ---------------------------------------------------------------------------
# ensure_output_dir
# ---------------------------------------------------------------------------

class TestEnsureOutputDir:
    def test_returns_path(self, tmp_path: Path):
        result = ensure_output_dir(tmp_path / "new_dir")
        assert isinstance(result, Path)

    def test_creates_directory(self, tmp_path: Path):
        target = tmp_path / "reports" / "sub"
        ensure_output_dir(target)
        assert target.is_dir()

    def test_creates_nested_directories(self, tmp_path: Path):
        target = tmp_path / "a" / "b" / "c"
        ensure_output_dir(target)
        assert target.is_dir()

    def test_idempotent_if_directory_exists(self, tmp_path: Path):
        ensure_output_dir(tmp_path)
        ensure_output_dir(tmp_path)  # should not raise

    def test_accepts_string_path(self, tmp_path: Path):
        target = str(tmp_path / "string_dir")
        result = ensure_output_dir(target)
        assert isinstance(result, Path)
        assert result.is_dir()

    def test_returned_path_matches_input(self, tmp_path: Path):
        target = tmp_path / "my_dir"
        result = ensure_output_dir(target)
        assert result == target


# ---------------------------------------------------------------------------
# save_text_report — success cases
# ---------------------------------------------------------------------------

class TestSaveTextReportSuccess:
    def test_returns_path(self, tmp_path: Path):
        result = save_text_report("Hello report", "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert isinstance(result, Path)

    def test_file_exists_after_save(self, tmp_path: Path):
        path = save_text_report("Hello report", "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.exists()

    def test_written_content_matches(self, tmp_path: Path):
        text = "STOCK RESEARCH REPORT\nAAPL\nScore: 72.5"
        path = save_text_report(text, "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.read_text(encoding="utf-8") == text

    def test_creates_output_directory(self, tmp_path: Path):
        target = tmp_path / "nested" / "reports"
        save_text_report("Report content", "AAPL", output_dir=target, timestamp=_TS)
        assert target.is_dir()

    def test_filename_contains_ticker(self, tmp_path: Path):
        path = save_text_report("Report", "MSFT", output_dir=tmp_path, timestamp=_TS)
        assert "MSFT" in path.name

    def test_filename_contains_timestamp_stamp(self, tmp_path: Path):
        path = save_text_report("Report", "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert _TS_STAMP in path.name

    def test_file_extension_is_txt(self, tmp_path: Path):
        path = save_text_report("Report", "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.suffix == ".txt"

    def test_accepts_string_output_dir(self, tmp_path: Path):
        result = save_text_report("Report", "AAPL", output_dir=str(tmp_path), timestamp=_TS)
        assert isinstance(result, Path)
        assert result.exists()

    def test_ticker_normalized_in_filename(self, tmp_path: Path):
        path = save_text_report("Report", "  aapl  ", output_dir=tmp_path, timestamp=_TS)
        assert "AAPL" in path.name

    def test_utf8_encoding_preserved(self, tmp_path: Path):
        text = "Report with special chars: €£¥"
        path = save_text_report(text, "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.read_text(encoding="utf-8") == text

    def test_multiline_content_preserved(self, tmp_path: Path):
        text = "Line 1\nLine 2\nLine 3"
        path = save_text_report(text, "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.read_text(encoding="utf-8") == text

    def test_returned_path_is_inside_output_dir(self, tmp_path: Path):
        path = save_text_report("Report", "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.parent == tmp_path


# ---------------------------------------------------------------------------
# save_text_report — input validation
# ---------------------------------------------------------------------------

class TestSaveTextReportValidation:
    def test_empty_report_text_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_text_report("", "AAPL", output_dir=tmp_path)

    def test_whitespace_only_report_text_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_text_report("   \n\t  ", "AAPL", output_dir=tmp_path)

    def test_none_report_text_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_text_report(None, "AAPL", output_dir=tmp_path)  # type: ignore[arg-type]

    def test_int_report_text_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_text_report(42, "AAPL", output_dir=tmp_path)  # type: ignore[arg-type]

    def test_empty_ticker_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_text_report("Report", "", output_dir=tmp_path)

    def test_whitespace_ticker_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_text_report("Report", "   ", output_dir=tmp_path)

    def test_non_string_ticker_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_text_report("Report", 42, output_dir=tmp_path)  # type: ignore[arg-type]

    def test_none_ticker_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_text_report("Report", None, output_dir=tmp_path)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# save_text_report — filesystem error wrapping
# ---------------------------------------------------------------------------

class TestSaveTextReportFilesystemErrors:
    def test_write_error_wrapped_in_storage_error(self, tmp_path: Path):
        with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            with pytest.raises(StorageError, match="Could not write"):
                save_text_report("Report", "AAPL", output_dir=tmp_path, timestamp=_TS)


# ---------------------------------------------------------------------------
# save_json_result — success with plain dict
# ---------------------------------------------------------------------------

class TestSaveJsonResultDict:
    def test_returns_path(self, tmp_path: Path):
        result = save_json_result({"score": 72.5}, "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert isinstance(result, Path)

    def test_file_exists_after_save(self, tmp_path: Path):
        path = save_json_result({"score": 72.5}, "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.exists()

    def test_file_extension_is_json(self, tmp_path: Path):
        path = save_json_result({"score": 72.5}, "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.suffix == ".json"

    def test_file_contains_valid_json(self, tmp_path: Path):
        path = save_json_result({"score": 72.5}, "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)

    def test_dict_content_round_trips(self, tmp_path: Path):
        data = {"ticker": "AAPL", "score": 72.5, "category": "Watchlist"}
        path = save_json_result(data, "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded == data

    def test_creates_output_directory(self, tmp_path: Path):
        target = tmp_path / "nested" / "results"
        save_json_result({"k": "v"}, "AAPL", output_dir=target, timestamp=_TS)
        assert target.is_dir()

    def test_json_is_pretty_printed(self, tmp_path: Path):
        path = save_json_result({"a": 1, "b": 2}, "AAPL", output_dir=tmp_path, timestamp=_TS)
        raw = path.read_text(encoding="utf-8")
        assert "\n" in raw

    def test_json_keys_sorted(self, tmp_path: Path):
        path = save_json_result(
            {"z": 1, "a": 2, "m": 3}, "AAPL", output_dir=tmp_path, timestamp=_TS
        )
        raw = path.read_text(encoding="utf-8")
        assert raw.index('"a"') < raw.index('"m"') < raw.index('"z"')

    def test_filename_contains_ticker(self, tmp_path: Path):
        path = save_json_result({"k": "v"}, "TSLA", output_dir=tmp_path, timestamp=_TS)
        assert "TSLA" in path.name

    def test_ticker_normalized_in_filename(self, tmp_path: Path):
        path = save_json_result({"k": "v"}, "  tsla  ", output_dir=tmp_path, timestamp=_TS)
        assert "TSLA" in path.name

    def test_returned_path_is_inside_output_dir(self, tmp_path: Path):
        path = save_json_result({"k": "v"}, "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert path.parent == tmp_path

    def test_accepts_string_output_dir(self, tmp_path: Path):
        result = save_json_result({"k": "v"}, "AAPL", output_dir=str(tmp_path), timestamp=_TS)
        assert isinstance(result, Path)
        assert result.exists()

    def test_nested_dict_serialized(self, tmp_path: Path):
        data = {"outer": {"inner": 42}}
        path = save_json_result(data, "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["outer"]["inner"] == 42

    def test_list_value_serialized(self, tmp_path: Path):
        data = {"items": [1, 2, 3]}
        path = save_json_result(data, "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["items"] == [1, 2, 3]

    def test_datetime_value_serialized_as_string(self, tmp_path: Path):
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        data: dict = {"ts": ts}
        path = save_json_result(data, "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(loaded["ts"], str)
        assert "2024" in loaded["ts"]


# ---------------------------------------------------------------------------
# save_json_result — success with Pydantic BaseModel
# ---------------------------------------------------------------------------

class TestSaveJsonResultPydantic:
    def test_accepts_pydantic_model(self, tmp_path: Path):
        path = save_json_result(_make_model(), "AAPL", output_dir=tmp_path, timestamp=_TS)
        assert isinstance(path, Path)

    def test_pydantic_model_produces_valid_json(self, tmp_path: Path):
        path = save_json_result(_make_model(), "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict)

    def test_pydantic_model_fields_in_output(self, tmp_path: Path):
        path = save_json_result(_make_model(), "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["ticker"] == "AAPL"
        assert loaded["score"] == pytest.approx(72.5)
        assert loaded["note"] == "test"

    def test_rating_model_serializes(self, tmp_path: Path):
        from app.models.rating import ConfidenceLevel, Rating, RatingCategory
        from app.models.signal import Signal, SignalCategory, SignalDirection, SignalStrength

        signal = Signal(
            name="Test",
            category=SignalCategory.TECHNICAL,
            direction=SignalDirection.BULLISH,
            strength=SignalStrength.MODERATE,
            description="Test signal.",
            score_impact=0.2,
            confidence=0.7,
        )
        rating = Rating(
            ticker="AAPL",
            final_category=RatingCategory.BUY_CANDIDATE,
            score=75.0,
            confidence=ConfidenceLevel.HIGH,
            explanation="Test rating.",
            technical_score=75.0,
            signals_used=[signal],
            data_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        path = save_json_result(rating, "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["ticker"] == "AAPL"
        assert loaded["score"] == pytest.approx(75.0)
        assert loaded["final_category"] == "Buy Candidate"
        assert isinstance(loaded["signals_used"], list)
        assert len(loaded["signals_used"]) == 1

    def test_rating_datetime_field_serialized_as_string(self, tmp_path: Path):
        from app.models.rating import ConfidenceLevel, Rating, RatingCategory

        rating = Rating(
            ticker="AAPL",
            final_category=RatingCategory.WATCHLIST,
            score=55.0,
            confidence=ConfidenceLevel.MEDIUM,
            explanation="Test.",
            data_timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        path = save_json_result(rating, "AAPL", output_dir=tmp_path, timestamp=_TS)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(loaded["data_timestamp"], str)


# ---------------------------------------------------------------------------
# save_json_result — input validation
# ---------------------------------------------------------------------------

class TestSaveJsonResultValidation:
    def test_empty_ticker_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_json_result({"k": "v"}, "", output_dir=tmp_path)

    def test_whitespace_ticker_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_json_result({"k": "v"}, "   ", output_dir=tmp_path)

    def test_non_string_ticker_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_json_result({"k": "v"}, None, output_dir=tmp_path)  # type: ignore[arg-type]

    def test_int_ticker_raises(self, tmp_path: Path):
        with pytest.raises(StorageError):
            save_json_result({"k": "v"}, 123, output_dir=tmp_path)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# save_json_result — filesystem error wrapping
# ---------------------------------------------------------------------------

class TestSaveJsonResultFilesystemErrors:
    def test_write_error_wrapped_in_storage_error(self, tmp_path: Path):
        with patch("pathlib.Path.write_text", side_effect=OSError("no space left")):
            with pytest.raises(StorageError, match="Could not write"):
                save_json_result({"k": "v"}, "AAPL", output_dir=tmp_path, timestamp=_TS)
