"""Verify the ONNX engine is a drop-in replacement for PyTorch (same model, same results).

Compares, for every sample resume x every sample JD:
  1. embeddings of every resume chunk and JD requirement (cosine between engines)
  2. final match scores, verdicts and rankings
  3. peak memory of a full pipeline run, each engine in its own fresh process

Requires the optional PyTorch engine:  uv sync --extra torch
Run:  uv run python scripts/compare_engines.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_PIPELINE = """
import json, sys
if {block_torch}:
    # Production installs don't include PyTorch; make it unimportable so optional importers
    # (spaCy's thinc probes for it) behave exactly as they will on the server.
    sys.modules["torch"] = None
from pathlib import Path
sys.path.insert(0, {backend!r})
from app.nlp import embeddings
from app.nlp.text_extract import extract
from app.nlp.resume_parser import parse_resume
from app.nlp.jd_parser import parse_jd
from app.matching.scorer import score_candidate
root = Path({root!r})
jds = [parse_jd(p.read_text()) for p in sorted((root / "sample_data/job_descriptions").glob("*.txt"))]
scores = {{}}
for f in sorted((root / "sample_data/resumes").iterdir()):
    ex = extract(f.name, f.read_bytes())
    prof = parse_resume(ex.text, f.name, links=ex.links)
    for jd in jds:
        m = score_candidate(jd, prof)
        scores[f"{{jd['title']}}|{{prof['name']}}"] = [m["score"], m["verdict"]]
# VmHWM = this process's own peak RSS (ru_maxrss can include the parent's memory at fork time)
hwm_kb = int(next(l for l in open("/proc/self/status") if l.startswith("VmHWM")).split()[1])
print(json.dumps({{"peak_rss_mb": round(hwm_kb / 1024),
                  "scores": scores}}))
"""


def run_pipeline(engine: str) -> dict:
    env = {"EMBEDDING_ENGINE": engine, "PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
           "HF_HUB_DISABLE_PROGRESS_BARS": "1", "TOKENIZERS_PARALLELISM": "false"}
    code = _PIPELINE.format(backend=str(BACKEND), root=str(ROOT), block_torch=engine == "onnx")
    out = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True, env=env, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def compare_vectors() -> dict:
    import numpy as np

    from app.nlp import embeddings
    from app.nlp.jd_parser import parse_jd
    from app.nlp.resume_parser import parse_resume
    from app.nlp.text_extract import extract

    texts: list[str] = []
    for p in sorted((ROOT / "sample_data/job_descriptions").glob("*.txt")):
        texts += parse_jd(p.read_text())["requirements"]
    for f in sorted((ROOT / "sample_data/resumes").iterdir()):
        ex = extract(f.name, f.read_bytes())
        texts += parse_resume(ex.text, f.name)["chunks"]
    texts = list(dict.fromkeys(texts))
    a = embeddings.make_encoder("onnx").encode(texts)
    b = embeddings.make_encoder("torch").encode(texts)
    cos = (a * b).sum(axis=1)
    return {"texts": len(texts), "min_cosine": float(cos.min()), "mean_cosine": float(cos.mean()),
            "max_abs_diff": float(np.abs(a - b).max())}


def main() -> None:
    vec = compare_vectors()
    onnx, torch = run_pipeline("onnx"), run_pipeline("torch")
    keys = sorted(onnx["scores"])
    diffs = [abs(onnx["scores"][k][0] - torch["scores"][k][0]) for k in keys]
    verdicts_equal = all(onnx["scores"][k][1] == torch["scores"][k][1] for k in keys)

    def ranking(s, jd):
        return [k for k in sorted((k for k in s if k.startswith(jd)), key=lambda k: -s[k][0])]

    jds = sorted({k.split("|")[0] for k in keys})
    rankings_equal = all(ranking(onnx["scores"], j) == ranking(torch["scores"], j) for j in jds)

    print(f"Embeddings: {vec['texts']} sentences | cosine(onnx, torch) min {vec['min_cosine']:.6f}, "
          f"mean {vec['mean_cosine']:.6f} | max abs diff {vec['max_abs_diff']:.2e}")
    print(f"Scores:     {len(keys)} candidate x JD pairs | max |diff| {max(diffs):.2f} points | "
          f"verdicts identical: {verdicts_equal} | rankings identical: {rankings_equal}")
    print(f"Memory:     peak RSS onnx {onnx['peak_rss_mb']} MB (without PyTorch installed) "
          f"vs torch {torch['peak_rss_mb']} MB")
    if not (verdicts_equal and rankings_equal and max(diffs) <= 0.1):
        sys.exit(1)


if __name__ == "__main__":
    main()
