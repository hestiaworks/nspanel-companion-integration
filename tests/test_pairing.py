"""Tests for short-code pairing without a Home Assistant runtime."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"
package = types.ModuleType("nspanel_companion")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("nspanel_companion", package)
for name in ("const", "pairing"):
    spec = spec_from_file_location(f"nspanel_companion.{name}", ROOT / f"{name}.py")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)

PairingManager = sys.modules["nspanel_companion.pairing"].PairingManager


class PairingManagerTest(unittest.TestCase):
    def test_approval_reveals_token_once_to_valid_claim(self):
        now = 1000.0
        manager = PairingManager(lambda: now)
        request, claim = manager.start("panel-123e4567e89b12d3a456426614174000", "Kitchen")
        self.assertRegex(request["code"], r"^\d{6}$")
        self.assertNotIn("code", manager.list_public()[0])
        self.assertEqual("pending", manager.claim(request["request_id"], claim)["status"])
        with self.assertRaises(ValueError):
            manager.approve(request["request_id"], "000000" if request["code"] != "000000" else "999999", "bad-secret")
        manager.approve(request["request_id"], request["code"], "permanent-secret")
        result = manager.claim(request["request_id"], claim)
        self.assertEqual("approved", result["status"])
        self.assertEqual("permanent-secret", result["token"])
        with self.assertRaises(ValueError):
            manager.claim(request["request_id"], claim)

    def test_expiry_and_wrong_claim_are_rejected(self):
        clock = [1000.0]
        manager = PairingManager(lambda: clock[0])
        request, claim = manager.start("panel-123e4567e89b12d3a456426614174000", "Kitchen")
        with self.assertRaises(ValueError):
            manager.claim(request["request_id"], claim + "wrong")
        clock[0] += 301
        with self.assertRaises(ValueError):
            manager.claim(request["request_id"], claim)


if __name__ == "__main__":
    unittest.main()
