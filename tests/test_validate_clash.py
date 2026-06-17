import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_validate_clash():
    module_path = ROOT / "scripts" / "validate-clash.py"
    spec = importlib.util.spec_from_file_location("validate_clash", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidateClashTests(unittest.TestCase):
    def test_stable_clash_config_has_required_structure(self):
        validate_clash = load_validate_clash()
        path = ROOT / "dist" / "clash" / "clash-naixi-stable.yaml"

        group_count = validate_clash.validate(path)

        self.assertGreater(group_count, 0)


if __name__ == "__main__":
    unittest.main()
