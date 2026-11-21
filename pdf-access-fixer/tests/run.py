"""Run the tests: python tests/run.py [--verapdf <launcher> | --verapdf-home <folder> --java <java>] [--no-skips]

--no-skips fails the run if any test was skipped (no Tesseract, no veraPDF), so a green run means every claim ran.
"""
import argparse
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import test_pipeline  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--verapdf")
ap.add_argument("--verapdf-home")
ap.add_argument("--java")
ap.add_argument("--no-skips", action="store_true")
args = ap.parse_args()
test_pipeline.VERAPDF.update(launcher=args.verapdf, home=args.verapdf_home, java=args.java)
suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py", top_level_dir=str(HERE))
result = unittest.TextTestRunner(verbosity=1).run(suite)
print(f"ran {result.testsRun}, failures {len(result.failures)}, errors {len(result.errors)}, skipped {len(result.skipped)}")
if not result.wasSuccessful() or (args.no_skips and result.skipped):
    sys.exit(1)
