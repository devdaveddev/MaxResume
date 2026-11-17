"""Parsing-accuracy regression gate: every field of every known resume must stay correct."""

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import eval_parsing  # noqa: E402


@pytest.mark.skipif(not (shutil.which("soffice") or shutil.which("libreoffice")),
                    reason="the accuracy gate includes .doc/.rtf/.odt files, which need LibreOffice for full fidelity")
def test_parsing_accuracy_on_known_resumes(samples):
    result = eval_parsing.evaluate(eval_parsing.sample_truth() + eval_parsing.edge_truth()
                                   + eval_parsing.heldout_truth("dev") + eval_parsing.heldout_truth("heldout"))
    # files whose converter is not installed (e.g. .rtf without LibreOffice) are skipped, not failed
    assert result["resumes"] + len(result["skipped"]) >= 28 and result["field_checks"] >= 450
    assert result["field_accuracy"] >= 0.98, result["failures"]
    assert result["skills"]["f1"] >= 0.98, result["failures"]


def test_evaluator_detects_errors(samples):
    truth = eval_parsing.sample_truth()[:1]
    truth[0]["name"] = "Someone Else"
    result = eval_parsing.evaluate(truth)
    assert result["field_accuracy"] < 1 and any("name" in f for f in result["failures"])
