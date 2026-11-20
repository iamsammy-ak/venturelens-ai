"""Generate the saved AI analyses that power demo mode.

Runs the real pipeline (two model calls per sample) and stores the result under
demo/analyses/<fingerprint>.json. Existing analyses are skipped unless --force is given.

    python scripts/build_demo.py [--force]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from venturelens.demo import load_samples, load_saved_analysis, sample_inputs, save_analysis  # noqa: E402
from venturelens.llm import LLMClient, LLMError  # noqa: E402
from venturelens.pipeline import compute, fingerprint, run_ai  # noqa: E402


def main(force: bool = False) -> int:
    llm = LLMClient(app_name="VentureLens AI")
    failures = 0
    for sample in load_samples():
        idea, a, m = sample_inputs(sample)
        fp = fingerprint(idea, a, m)
        if load_saved_analysis(fp) and not force:
            print(f"skip   {idea.name} ({fp}): already saved")
            continue
        try:
            analysis = run_ai(llm, idea, a, m, compute(a, m), on_step=lambda msg: print(f"       {msg}"))
        except LLMError as exc:
            failures += 1
            print(f"FAILED {idea.name}: {exc}")
            continue
        path = save_analysis(analysis)
        print(f"saved  {idea.name} -> {path.name} ({analysis['model']})")
    print(f"model calls made: {llm.calls_made}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(force="--force" in sys.argv))
