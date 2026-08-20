"""Tests for the Layer 2 separation diagnostic."""

import json

import pytest

from foa_pipeline.evaluation.diagnostics import (
    _auc,
    cosine_separation,
    format_separation_report,
)


def _row(concept, category, layer, confidence):
    return {
        "foa_id": "f1",
        "title": "t",
        "concept": concept,
        "label": concept,
        "category": category,
        "layer": layer,
        "confidence": confidence,
    }


@pytest.fixture
def eval_dir(tmp_path):
    def _write(true_positives, false_positives):
        (tmp_path / "true_positives_gold.json").write_text(json.dumps(true_positives))
        (tmp_path / "false_positives_gold.json").write_text(json.dumps(false_positives))
        return tmp_path

    return _write


class TestEvalSetNamespacing:
    """
    Gold and silver runs must not overwrite each other's error logs.

    They previously shared filenames, so a silver run left files that kept the
    gold names while describing 46 different FOAs — and Documentation/EVALUATION.md presents
    those files as the reported gold error analysis.
    """

    def test_slug_per_eval_set(self):
        from foa_pipeline.evaluation.runner import eval_set_slug

        assert eval_set_slug(True) == "gold"
        assert eval_set_slug(False) == "silver"

    def test_reads_the_gold_logs_by_default(self, tmp_path):
        gold = [_row("c1", "method", "layer_2_embedding", 0.9)]
        silver = [_row("c2", "method", "layer_2_embedding", 0.1)]
        (tmp_path / "true_positives_gold.json").write_text(json.dumps(gold))
        (tmp_path / "false_positives_gold.json").write_text(json.dumps([]))
        (tmp_path / "true_positives_silver.json").write_text(json.dumps(silver))
        (tmp_path / "false_positives_silver.json").write_text(json.dumps([]))

        report = cosine_separation(tmp_path)
        assert report["overall"]["correct"]["n"] == 1
        assert report["overall"]["correct"]["mean"] == pytest.approx(0.9)

    def test_can_read_the_silver_logs_explicitly(self, tmp_path):
        (tmp_path / "true_positives_gold.json").write_text(json.dumps([]))
        (tmp_path / "false_positives_gold.json").write_text(json.dumps([]))
        (tmp_path / "true_positives_silver.json").write_text(
            json.dumps([_row("c2", "method", "layer_2_embedding", 0.1)])
        )
        (tmp_path / "false_positives_silver.json").write_text(json.dumps([]))

        report = cosine_separation(tmp_path, eval_set="silver")
        assert report["overall"]["correct"]["mean"] == pytest.approx(0.1)

    def test_missing_file_names_the_command_to_run(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="evaluate --gold"):
            cosine_separation(tmp_path)

    def test_legacy_unnamespaced_file_is_called_out(self, tmp_path):
        """Anyone upgrading has the old filenames sitting there; say so."""
        (tmp_path / "true_positives.json").write_text(json.dumps([]))
        with pytest.raises(FileNotFoundError, match="before error logs"):
            cosine_separation(tmp_path)


class TestAuc:
    def test_perfect_separation(self):
        assert _auc([0.9, 0.8], [0.2, 0.1]) == 1.0

    def test_perfect_inversion(self):
        assert _auc([0.1, 0.2], [0.8, 0.9]) == 0.0

    def test_no_information_when_identical(self):
        """Ties count as half, so identical distributions give exactly 0.5."""
        assert _auc([0.5, 0.5], [0.5, 0.5]) == 0.5

    def test_returns_none_when_a_side_is_empty(self):
        assert _auc([], [0.5]) is None
        assert _auc([0.5], []) is None


class TestCosineSeparation:
    def test_ignores_non_layer2_evidence(self, eval_dir):
        """L1 is always 1.0 and L3 always 0.95, so their scores mean nothing."""
        path = eval_dir(
            [_row("a", "method", "layer_1_terminological", 1.0),
             _row("b", "method", "layer_2_embedding", 0.60)],
            [_row("c", "method", "layer_3_llm", 0.95),
             _row("d", "method", "layer_2_embedding", 0.30)],
        )
        report = cosine_separation(path)
        assert report["overall"]["correct"]["n"] == 1
        assert report["overall"]["incorrect"]["n"] == 1
        assert report["overall"]["auc"] == 1.0

    def test_computes_mean_gap(self, eval_dir):
        path = eval_dir(
            [_row("a", "method", "layer_2_embedding", 0.60)],
            [_row("b", "method", "layer_2_embedding", 0.40)],
        )
        assert cosine_separation(path)["overall"]["mean_gap"] == pytest.approx(0.20)

    def test_detects_anti_correlation(self, eval_dir):
        """AUC below 0.5 means the score is actively misleading, not just noisy."""
        path = eval_dir(
            [_row("a", "population", "layer_2_embedding", 0.30)],
            [_row("b", "population", "layer_2_embedding", 0.70)],
        )
        assert cosine_separation(path)["per_category"]["population"]["auc"] < 0.5

    def test_splits_by_category(self, eval_dir):
        path = eval_dir(
            [_row("a", "method", "layer_2_embedding", 0.60),
             _row("b", "population", "layer_2_embedding", 0.20)],
            [_row("c", "method", "layer_2_embedding", 0.30),
             _row("d", "population", "layer_2_embedding", 0.80)],
        )
        report = cosine_separation(path)
        assert report["per_category"]["method"]["auc"] == 1.0
        assert report["per_category"]["population"]["auc"] == 0.0

    def test_rejects_artifacts_missing_layer_field(self, eval_dir):
        """Older runners didn't record evidence for true positives."""
        path = eval_dir(
            [{"concept": "a", "category": "method"}],
            [_row("b", "method", "layer_2_embedding", 0.30)],
        )
        with pytest.raises(ValueError, match="no 'layer' field"):
            cosine_separation(path)

    def test_missing_file_raises_actionable_error(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Run an evaluation first"):
            cosine_separation(tmp_path)


class TestReportFormatting:
    def test_renders_without_error(self, eval_dir):
        path = eval_dir(
            [_row("a", "method", "layer_2_embedding", 0.60)],
            [_row("b", "method", "layer_2_embedding", 0.30)],
        )
        text = format_separation_report(cosine_separation(path))
        assert "AUC" in text
        assert "method" in text

    def test_handles_category_with_one_empty_side(self, eval_dir):
        """A category with no false positives must not crash the report."""
        path = eval_dir(
            [_row("a", "method", "layer_2_embedding", 0.60)],
            [_row("b", "population", "layer_2_embedding", 0.30)],
        )
        text = format_separation_report(cosine_separation(path))
        assert "n/a" in text
