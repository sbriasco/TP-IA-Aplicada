from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flowsight.core.config import ConfigurationError, load_settings


class SettingsTests(unittest.TestCase):
    def valid_environment(self) -> dict[str, str]:
        return {
            "FLOWSIGHT_ENV": "test",
            "FLOWSIGHT_DATABASE_URL": "postgresql+psycopg://flowsight:secret@localhost/flowsight",
            "FLOWSIGHT_API_HOST": "127.0.0.1",
            "FLOWSIGHT_API_PORT": "8000",
            "FLOWSIGHT_WORKER_ID": "worker-test",
            "FLOWSIGHT_PREVIEW_MAX_FPS": "5",
        }

    def test_loads_valid_settings(self) -> None:
        with patch.dict(os.environ, self.valid_environment(), clear=True):
            settings = load_settings()

        self.assertEqual(settings.environment, "test")
        self.assertEqual(settings.api_port, 8000)
        self.assertEqual(settings.preview_max_fps, 5)

    def test_loads_explicit_frontend_origins(self) -> None:
        environment = self.valid_environment()
        environment["FLOWSIGHT_CORS_ORIGINS"] = '["https://demo.example.test"]'
        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()
        self.assertEqual(settings.cors_origins, ["https://demo.example.test"])

    def test_reports_missing_database_url_without_exposing_values(self) -> None:
        environment = self.valid_environment()
        del environment["FLOWSIGHT_DATABASE_URL"]

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                load_settings()

        message = str(raised.exception)
        self.assertIn("FLOWSIGHT_DATABASE_URL", message)
        self.assertIn("missing", message)
        self.assertIn(".env.example", message)

    def test_reports_empty_worker_id(self) -> None:
        environment = self.valid_environment()
        environment["FLOWSIGHT_WORKER_ID"] = "   "

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                load_settings()

        self.assertIn("FLOWSIGHT_WORKER_ID", str(raised.exception))
        self.assertIn("empty", str(raised.exception))

    def test_rejects_invalid_port(self) -> None:
        environment = self.valid_environment()
        environment["FLOWSIGHT_API_PORT"] = "70000"

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                load_settings()

        self.assertIn("FLOWSIGHT_API_PORT", str(raised.exception))
        self.assertIn("invalid_format", str(raised.exception))

    def test_reports_invalid_database_url_format_without_exposing_it(self) -> None:
        environment = self.valid_environment()
        invalid_url = "mysql://flowsight:secret@localhost/flowsight"
        environment["FLOWSIGHT_DATABASE_URL"] = invalid_url

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                load_settings()

        message = str(raised.exception)
        self.assertIn("FLOWSIGHT_DATABASE_URL", message)
        self.assertIn("invalid_format", message)
        self.assertNotIn(invalid_url, message)

    def test_redacts_database_credentials_from_validation_errors(self) -> None:
        environment = self.valid_environment()
        secret_url = "postgresql+psycopg://flowsight:super-secret@localhost/flowsight"
        environment["FLOWSIGHT_DATABASE_URL"] = secret_url
        environment["FLOWSIGHT_PREVIEW_MAX_FPS"] = "0"

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                load_settings()

        message = str(raised.exception)
        self.assertNotIn(secret_url, message)
        self.assertNotIn("super-secret", message)
        self.assertIn("FLOWSIGHT_PREVIEW_MAX_FPS", message)

    def test_video_settings_are_optional(self) -> None:
        with patch.dict(os.environ, self.valid_environment(), clear=True):
            settings = load_settings()

        self.assertIsNone(settings.videos_dir)
        self.assertIsNone(settings.machine_id)

    def test_empty_video_settings_are_treated_as_missing(self) -> None:
        environment = self.valid_environment()
        environment["FLOWSIGHT_VIDEOS_DIR"] = "  "
        environment["FLOWSIGHT_MACHINE_ID"] = ""

        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()

        self.assertIsNone(settings.videos_dir)
        self.assertIsNone(settings.machine_id)

    def test_loads_valid_video_settings(self) -> None:
        videos_dir = Path(tempfile.gettempdir()).resolve() / "flowsight-videos"
        environment = self.valid_environment()
        environment["FLOWSIGHT_VIDEOS_DIR"] = str(videos_dir)
        environment["FLOWSIGHT_MACHINE_ID"] = " equipo-03 "

        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()

        self.assertEqual(settings.videos_dir, videos_dir)
        self.assertEqual(settings.machine_id, "equipo-03")

    def test_invalid_machine_id_does_not_block_startup(self) -> None:
        for invalid in ("Equipo-03", "ab", "-equipo", "equipo_03", "a" * 41):
            environment = self.valid_environment()
            environment["FLOWSIGHT_MACHINE_ID"] = invalid

            with self.subTest(machine_id=invalid):
                with patch.dict(os.environ, environment, clear=True):
                    settings = load_settings()

                self.assertIsNone(settings.machine_id)

    def test_rejects_relative_videos_dir_without_exposing_it(self) -> None:
        environment = self.valid_environment()
        relative_dir = "videos-privados/santiago"
        environment["FLOWSIGHT_VIDEOS_DIR"] = relative_dir

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                load_settings()

        message = str(raised.exception)
        self.assertIn("FLOWSIGHT_VIDEOS_DIR", message)
        self.assertIn("invalid_format", message)
        self.assertNotIn(relative_dir, message)
        self.assertNotIn("santiago", message)

    def test_invalid_machine_id_is_never_echoed(self) -> None:
        environment = self.valid_environment()
        environment["FLOWSIGHT_MACHINE_ID"] = "Santiago Alvarez"
        environment["FLOWSIGHT_API_PORT"] = "70000"

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                load_settings()

        message = str(raised.exception)
        self.assertNotIn("Santiago", message)
        self.assertNotIn("FLOWSIGHT_MACHINE_ID", message)

    def test_api_rejects_invalid_configuration_before_starting(self) -> None:
        from flowsight.api.main import create_app

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError):
                create_app()

    def test_api_starts_with_valid_configuration(self) -> None:
        from flowsight.api.main import create_app

        with (
            patch.dict(os.environ, self.valid_environment(), clear=True),
            patch("flowsight.api.main.create_database_engine") as create_engine,
        ):
            app = create_app()

        self.assertEqual(app.title, "FlowSight API")
        create_engine.return_value.connect.assert_called_once()

    def test_api_rejects_unavailable_database_safely(self) -> None:
        from sqlalchemy.exc import OperationalError

        from flowsight.api.main import create_app

        with (
            patch.dict(os.environ, self.valid_environment(), clear=True),
            patch("flowsight.api.main.create_database_engine") as create_engine,
        ):
            create_engine.return_value.connect.side_effect = OperationalError(
                "SELECT 1", {}, Exception("super-secret")
            )
            with self.assertRaises(ConfigurationError) as raised:
                create_app()

        self.assertIn("PostgreSQL no está disponible", str(raised.exception))
        self.assertNotIn("super-secret", str(raised.exception))

    def test_worker_rejects_invalid_configuration_before_starting(self) -> None:
        from flowsight.worker.main import bootstrap_worker

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError):
                bootstrap_worker()

    def test_detector_absent_is_fake(self) -> None:
        with patch.dict(os.environ, self.valid_environment(), clear=True):
            settings = load_settings()

        self.assertEqual(settings.detector, "fake")
        self.assertIsNone(settings.yolo_weights)

    def test_detector_accepts_fake_and_ultralytics(self) -> None:
        environment = self.valid_environment()
        environment["FLOWSIGHT_DETECTOR"] = "fake"
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(load_settings().detector, "fake")

        environment["FLOWSIGHT_DETECTOR"] = "ultralytics"
        environment["FLOWSIGHT_YOLO_WEIGHTS"] = "weights/yolov8n.pt"
        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()

        self.assertEqual(settings.detector, "ultralytics")
        self.assertEqual(settings.yolo_weights, Path("weights/yolov8n.pt"))

    def test_invalid_detector_falls_back_to_fake(self) -> None:
        environment = self.valid_environment()
        environment["FLOWSIGHT_DETECTOR"] = "gpu-mystery"
        environment["FLOWSIGHT_YOLO_WEIGHTS"] = "  "
        environment["FLOWSIGHT_API_PORT"] = "70000"
        absolute_weight = r"C:\secretos\yolov8n.pt"
        environment["FLOWSIGHT_YOLO_WEIGHTS"] = absolute_weight

        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(ConfigurationError) as raised:
                load_settings()

        message = str(raised.exception)
        self.assertNotIn(absolute_weight, message)
        self.assertNotIn("secretos", message)

        environment["FLOWSIGHT_API_PORT"] = "8000"
        with patch.dict(os.environ, environment, clear=True):
            settings = load_settings()

        self.assertEqual(settings.detector, "fake")

    def test_worker_starts_with_valid_configuration(self) -> None:
        from flowsight.worker.main import bootstrap_worker

        with patch.dict(os.environ, self.valid_environment(), clear=True):
            settings = bootstrap_worker()

        self.assertEqual(settings.worker_id, "worker-test")


if __name__ == "__main__":
    unittest.main()
