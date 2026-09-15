from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXPERIMENT_ROOT))

from scene_config import (
    SceneConfigError,
    classify_line_sides,
    load_scene_config,
    validate_scene_config,
)

SCENE_EXAMPLE_PATH = EXPERIMENT_ROOT / "config" / "scene.example.json"


class SceneConfigValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid_scene = load_scene_config(SCENE_EXAMPLE_PATH)

    def test_synthetic_example_is_geometrically_valid(self) -> None:
        scene = validate_scene_config(self.valid_scene)
        self.assertTrue(scene["synthetic"])
        self.assertIn("ajeno a los videos reales", scene["notes"])
        self.assertGreater(scene["frame_reference"]["width"], 0)
        self.assertGreater(scene["frame_reference"]["height"], 0)
        self.assertEqual(scene["entry_line"]["directions"]["A_to_B"], "entry")
        self.assertEqual(scene["entry_line"]["directions"]["B_to_A"], "exit")
        self.assertIn("segmento", scene["entry_line"]["segment_rule"])
        sides = classify_line_sides(
            tuple(scene["entry_line"]["start"]),
            tuple(scene["entry_line"]["end"]),
        )
        self.assertEqual(sides(tuple(scene["entry_line"]["side_A"]["sample_point"])), "A")
        self.assertEqual(sides(tuple(scene["entry_line"]["side_B"]["sample_point"])), "B")

    def test_dimensions_must_be_positive(self) -> None:
        for field, value in (("width", 0), ("height", -1080)):
            with self.subTest(field=field, value=value):
                scene = copy.deepcopy(self.valid_scene)
                scene["frame_reference"][field] = value
                with self.assertRaises(SceneConfigError):
                    validate_scene_config(scene)

    def test_points_must_stay_inside_the_frame(self) -> None:
        scene = copy.deepcopy(self.valid_scene)
        scene["front_zone"]["polygon"][0] = [-1, 300]
        with self.assertRaises(SceneConfigError):
            validate_scene_config(scene)

        scene = copy.deepcopy(self.valid_scene)
        scene["entry_line"]["end"] = [1920, 1081]
        with self.assertRaises(SceneConfigError):
            validate_scene_config(scene)

    def test_polygon_requires_at_least_three_points_and_nonzero_area(self) -> None:
        scene = copy.deepcopy(self.valid_scene)
        scene["front_zone"]["polygon"] = [[420, 300], [1280, 300]]
        with self.assertRaises(SceneConfigError):
            validate_scene_config(scene)

        scene = copy.deepcopy(self.valid_scene)
        scene["front_zone"]["polygon"] = [[100, 100], [200, 100], [300, 100]]
        with self.assertRaises(SceneConfigError):
            validate_scene_config(scene)

    def test_line_requires_two_distinct_points(self) -> None:
        scene = copy.deepcopy(self.valid_scene)
        scene["entry_line"]["end"] = [500, 850]
        with self.assertRaises(SceneConfigError):
            validate_scene_config(scene)

    def test_both_crossing_directions_must_be_declared(self) -> None:
        scene = copy.deepcopy(self.valid_scene)
        del scene["entry_line"]["directions"]["B_to_A"]
        with self.assertRaises(SceneConfigError):
            validate_scene_config(scene)

        scene = copy.deepcopy(self.valid_scene)
        scene["entry_line"]["directions"]["A_to_B"] = "inward"
        with self.assertRaises(SceneConfigError):
            validate_scene_config(scene)

    def test_example_file_is_json_and_not_a_real_video_scene(self) -> None:
        raw = json.loads(SCENE_EXAMPLE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(raw["video_id"], "synthetic-video-001")
        self.assertTrue(raw["synthetic"])


if __name__ == "__main__":
    unittest.main()
