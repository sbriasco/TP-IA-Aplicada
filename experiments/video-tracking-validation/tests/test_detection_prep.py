from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from detection_prep import WeightsNotApprovedError, describe_weight_approval, require_local_weights


class DetectionPrepTests(unittest.TestCase):
    def test_describe_weight_approval_does_not_download(self) -> None:
        text = describe_weight_approval()
        self.assertIn("yolov8n.pt", text)
        self.assertIn("6.53 MB", text)
        self.assertIn("AGPL-3.0", text)
        self.assertIn("github.com/ultralytics/assets", text)

    def test_require_local_weights_fails_without_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "yolov8n.pt"
            with self.assertRaises(WeightsNotApprovedError):
                require_local_weights(missing)


if __name__ == "__main__":
    unittest.main()
