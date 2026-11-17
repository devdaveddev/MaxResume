"""Parsing-accuracy regression gate: every field of every known resume must stay correct."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import eval_parsing  # noqa: E402


def test_parsing_accuracy_on_known_resumes(samples):
    result = eval_parsing.evaluate(eval_parsing.sample_truth() + eval_parsing.edge_truth()
                                   + eval_parsing.heldout_truth("dev") + eval_parsing.heldout_truth("heldout"))
    assert result["resumes"] >= 28 and result["field_checks"] >= 480
    assert result["field_accuracy"] >= 0.98, result["failures"]
    assert result["skills"]["f1"] >= 0.98, result["failures"]


def test_evaluator_detects_errors(samples):
    truth = eval_parsing.sample_truth()[:1]
    truth[0]["name"] = "Someone Else"
    result = eval_parsing.evaluate(truth)
    assert result["field_accuracy"] < 1 and any("name" in f for f in result["failures"])
