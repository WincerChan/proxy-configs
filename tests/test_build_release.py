import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_build_release():
    module_path = ROOT / "scripts" / "build-release.py"
    spec = importlib.util.spec_from_file_location("build_release", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildReleaseTests(unittest.TestCase):
    def test_stable_build_matches_current_dist(self):
        build_release = load_build_release()
        clash_path = ROOT / "dist" / "clash" / "clash-naixi-stable.yaml"
        quanx_path = ROOT / "dist" / "quanx" / "quantumultx-naixi-stable.conf"
        expected_clash = clash_path.read_text(encoding="utf-8")
        expected_quanx = quanx_path.read_text(encoding="utf-8")

        built_paths = build_release.build_all(version="stable", root=ROOT)

        self.assertEqual([clash_path, quanx_path], built_paths)
        self.assertEqual(expected_clash, clash_path.read_text(encoding="utf-8"))
        self.assertEqual(expected_quanx, quanx_path.read_text(encoding="utf-8"))

    def test_custom_version_build_uses_requested_suffix(self):
        build_release = load_build_release()

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            shutil.copytree(ROOT / "src", root / "src")

            built_paths = build_release.build_all(version="v-test", root=root)

            self.assertEqual(
                [
                    root / "dist" / "clash" / "clash-naixi-v-test.yaml",
                    root / "dist" / "quanx" / "quantumultx-naixi-v-test.conf",
                ],
                built_paths,
            )
            for path in built_paths:
                self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
