"""Tests for cross-niche deduplication."""

from training.dedup import deduplicate_within_niche, compute_overlap_matrix


TEXT_A = ("Python is a high-level programming language. " * 20).strip()
TEXT_B = ("Python is a high-level programming language. " * 19 + "Extra unique content. " * 5).strip()
TEXT_C = ("Quantum mechanics describes the behavior of matter at atomic scales. " * 20).strip()


class TestDedupWithinNiche:
    def test_removes_near_duplicates(self):
        samples = [
            {"text": TEXT_A},
            {"text": TEXT_A},
            {"text": TEXT_C},
        ]
        result = deduplicate_within_niche(samples, jaccard_threshold=0.8)
        assert len(result) <= 2

    def test_keeps_all_distinct(self):
        samples = [
            {"text": TEXT_A},
            {"text": TEXT_C},
            {"text": "Something completely different " * 20},
        ]
        result = deduplicate_within_niche(samples, jaccard_threshold=0.8)
        assert len(result) == 3

    def test_empty_list(self):
        assert deduplicate_within_niche([]) == []

    def test_single_sample(self):
        samples = [{"text": TEXT_A}]
        assert deduplicate_within_niche(samples) == samples


class TestOverlapMatrix:
    def test_computes_overlap(self):
        samples_by_niche = {
            "medical": [{"text": TEXT_A} for _ in range(10)],
            "code": [{"text": TEXT_C} for _ in range(10)],
        }
        matrix = compute_overlap_matrix(samples_by_niche)
        assert ("code", "medical") in matrix or ("medical", "code") in matrix

    def test_identical_niches_have_high_overlap(self):
        samples_by_niche = {
            "niche_a": [{"text": TEXT_A} for _ in range(20)],
            "niche_b": [{"text": TEXT_A} for _ in range(20)],
        }
        matrix = compute_overlap_matrix(samples_by_niche)
        key = ("niche_a", "niche_b")
        assert matrix[key] > 0.5

    def test_dissimilar_niches_have_low_overlap(self):
        samples_by_niche = {
            "niche_a": [{"text": TEXT_A} for _ in range(20)],
            "niche_b": [{"text": TEXT_C} for _ in range(20)],
        }
        matrix = compute_overlap_matrix(samples_by_niche)
        key = ("niche_a", "niche_b")
        assert matrix[key] < 0.3
