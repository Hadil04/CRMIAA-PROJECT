"""Tests for CRIA sensitive-data masking, including typo tolerance."""

import os
import tempfile
import unittest

from app.cria.security import SensitiveDataMasker, mask, unmask


class TypoMaskingTests(unittest.TestCase):
    """Verify fuzzy typo masking maps to the same fake code as the correct word."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.map_path = os.path.join(self.temp_dir.name, "mask_map.json")
        self.masker = SensitiveDataMasker(map_path=self.map_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _code_for(self, word: str) -> str:
        self.masker.mask(word)
        return self.masker.mapping[word]

    def test_ahled_maps_to_same_code_as_ahmed(self):
        ahmed_code = self._code_for("Ahmed")
        masked = self.masker.mask("What did Ahled earn?")

        self.assertIn(ahmed_code, masked)
        self.assertNotRegex(masked, r"\bAhled\b")

    def test_sara_maps_to_same_code_as_sarah(self):
        sarah_code = self._code_for("Sarah")
        masked = self.masker.mask("Sara works in Finance")

        self.assertIn(sarah_code, masked)
        self.assertNotRegex(masked, r"\bSara\b")

    def test_nadai_maps_to_same_code_as_nadia(self):
        nadia_code = self._code_for("Nadia")
        masked = self.masker.mask("What is the salary of nadai?")

        self.assertIn(nadia_code, masked)
        self.assertNotIn("nadai", masked.lower())

    def test_round_trip_unmask_after_typo_mask(self):
        ahmed_code = self._code_for("Ahmed")
        masked = self.masker.mask("Ahled checked the salary")
        restored = self.masker.unmask(masked)

        self.assertIn("Ahmed", restored)
        self.assertNotIn(ahmed_code, restored)


class DefaultMaskerSmokeTests(unittest.TestCase):
    """Smoke tests for module-level mask/unmask helpers."""

    def test_mask_unmask_preserves_non_sensitive_text(self):
        original = "The total count is 3."
        self.assertEqual(unmask(mask(original)), original)


if __name__ == "__main__":
    unittest.main()
