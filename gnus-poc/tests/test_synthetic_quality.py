"""Tests for synthetic data quality gates (DIST-03).

Covers ``check_synthetic_quality`` in ``distill.distillation``: minimum token
length, empty/whitespace filtering, and deduplication by normalized SHA256.
"""

from distill.distillation import check_synthetic_quality


class TestSyntheticQuality:
    def test_min_length_filter(self):
        # 10 tokens is below the default min_length of 50 -> filtered out.
        short = " ".join(["word"] * 10)
        assert check_synthetic_quality([short]) == []

        # 100 tokens clears the default min_length -> kept.
        long_text = " ".join(["word"] * 100)
        kept = check_synthetic_quality([long_text])
        assert len(kept) == 1
        assert kept[0] == long_text

    def test_empty_filter(self):
        # Empty strings and whitespace-only strings are filtered.
        assert check_synthetic_quality([""]) == []
        assert check_synthetic_quality(["   "]) == []
        assert check_synthetic_quality(["", "   ", "\t\n"]) == []

    def test_dedup_by_hash(self):
        # Two texts that normalize to the same form (case + whitespace collapsed)
        # are deduplicated — only the first occurrence is kept.
        text_a = " ".join(["word"] * 60)
        text_b = "  ".join(["WORD"] * 60)  # normalizes to the same hash as text_a
        kept = check_synthetic_quality([text_a, text_b])
        assert len(kept) == 1
        assert kept[0] == text_a

    def test_valid_examples_pass(self):
        # Clean, distinct, sufficiently long examples pass all checks unchanged.
        examples = [
            " ".join(["alpha"] * 60),
            " ".join(["beta"] * 70),
            " ".join(["gamma"] * 80),
        ]
        kept = check_synthetic_quality(examples)
        assert kept == examples
