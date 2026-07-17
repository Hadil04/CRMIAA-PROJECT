"""Sensitive-word masking helpers for CRIA."""

import difflib
import json
import random
import re
import string
from pathlib import Path


DEFAULT_MASK_MAP_PATH = Path(__file__).with_name("mask_map.json")
SENSITIVE_WORDS = ("Ahmed", "Sarah", "Nadia", "school", "salary")
FUZZY_MATCH_CUTOFF = 0.75


class SensitiveDataMasker:
    """Mask and unmask sensitive words using a persistent JSON mapping."""

    def __init__(
        self,
        map_path: str | Path = DEFAULT_MASK_MAP_PATH,
        sensitive_words: tuple[str, ...] = SENSITIVE_WORDS,
    ) -> None:
        self.map_path = Path(map_path)
        self.sensitive_words = sensitive_words
        self.mapping = self._load_mapping()

    def mask(self, text: str) -> str:
        """Replace known sensitive words (or close typos of them) with
        stable fake codes."""
        masked_text = text

        for word in self.sensitive_words:
            fake_code = self._get_or_create_fake_code(word)
            masked_text = self._replace_word(masked_text, word, fake_code)

        # Second pass: catch typos of sensitive words that weren't matched
        # exactly above (e.g. "Ahled" for "Ahmed", "finace" for "salary"/etc).
        masked_text = self._mask_typos(masked_text)

        self._save_mapping()
        return masked_text

    def unmask(self, text: str) -> str:
        """Replace fake codes in text with their original sensitive words."""
        unmasked_text = text

        for real_word, fake_code in self.mapping.items():
            unmasked_text = self._replace_word(
                unmasked_text,
                fake_code,
                real_word,
                ignore_case=True,
            )

        return unmasked_text

    def _mask_typos(self, text: str) -> str:
        """Find tokens in text that are close misspellings of a known
        sensitive word, and mask them using that word's fake code."""
        tokens = re.findall(r"[A-Za-z]+", text)
        result = text

        for token in tokens:
            # Skip tokens that are already fake codes or exact sensitive words.
            if token in self.mapping.values():
                continue
            if any(token.lower() == w.lower() for w in self.sensitive_words):
                continue

            close = difflib.get_close_matches(
                token.lower(),
                [w.lower() for w in self.sensitive_words],
                n=1,
                cutoff=FUZZY_MATCH_CUTOFF,
            )
            if not close:
                continue

            matched_word = next(
                w for w in self.sensitive_words if w.lower() == close[0]
            )
            fake_code = self._get_or_create_fake_code(matched_word)
            result = self._replace_word(result, token, fake_code)

        return result

    def _load_mapping(self) -> dict[str, str]:
        """Load the persisted mask mapping, or start with an empty one."""
        if not self.map_path.exists():
            return {}

        try:
            with self.map_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Mask map JSON is invalid: {self.map_path}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Mask map must contain a JSON object: {self.map_path}")

        return {str(real): str(fake) for real, fake in data.items()}

    def _save_mapping(self) -> None:
        """Persist the current mask mapping to disk."""
        self.map_path.parent.mkdir(parents=True, exist_ok=True)
        with self.map_path.open("w", encoding="utf-8") as file:
            json.dump(self.mapping, file, indent=2, sort_keys=True)

    def _get_or_create_fake_code(self, word: str) -> str:
        """Return the existing fake code for a word or create a new one."""
        if word not in self.mapping:
            self.mapping[word] = self._generate_unique_code()
        return self.mapping[word]

    def _generate_unique_code(self) -> str:
        """Generate a unique four-letter lowercase fake code."""
        existing_codes = set(self.mapping.values())

        while True:
            code = "".join(random.choices(string.ascii_lowercase, k=4))
            if code not in existing_codes:
                return code

    @staticmethod
    def _contains_word(text: str, word: str) -> bool:
        """Return whether text contains word as a whole token."""
        return re.search(rf"\b{re.escape(word)}\b", text) is not None

    @staticmethod
    def _replace_word(
        text: str,
        word: str,
        replacement: str,
        ignore_case: bool = False,
    ) -> str:
        """Replace whole-word occurrences of word in text."""
        flags = re.IGNORECASE if ignore_case else 0
        return re.sub(rf"\b{re.escape(word)}\b", replacement, text, flags=flags)


_default_masker = SensitiveDataMasker()


def mask(text: str) -> str:
    """Mask sensitive words using the default persistent masker."""
    return _default_masker.mask(text)


def unmask(text: str) -> str:
    """Unmask fake codes using the default persistent masker."""
    return _default_masker.unmask(text)