"""Tests for ManifestBuilder."""

import json

from quantize.manifest import ManifestBuilder


class TestManifestBuilder:
    def test_build_manifest(self, tmp_path):
        builder = ManifestBuilder(project_root=tmp_path)
        fp4_bin = tmp_path / "artifacts" / "fp4" / "code" / "code.fp4"
        fp4_bin.parent.mkdir(parents=True)
        fp4_bin.write_bytes(b"test binary data")

        manifest = builder.build(
            niche_name="code",
            base_model="mlx-community/Qwen3-Coder-30B-A3B-Instruct-bf16",
            training_metadata={
                "iters": 1000, "batch_size": 4,
                "lora_parameters": {"rank": 16},
                "training_duration_minutes": 45.0,
                "trained_at": "2026-05-27T12:00:00",
            },
            fp4_bin_path=fp4_bin,
            fp4_stats={"num_blocks": 4, "fp4_blocks": 3, "t158_blocks": 1, "shape": [128, 128]},
            eval_results={"perplexity": 5.2, "bleu_score": 0.45},
        )

        assert manifest["manifest_version"] == "1.0"
        assert manifest["niche"] == "code"
        assert "sha256" in manifest["fp4_binary"]
        assert manifest["training"]["lora_rank"] == 16
        assert manifest["evaluation"]["perplexity"] == 5.2

    def test_save_manifest(self, tmp_path):
        builder = ManifestBuilder(project_root=tmp_path)
        builder.save({"niche": "test", "manifest_version": "1.0"}, "test")
        out = tmp_path / "artifacts" / "manifests" / "test_manifest.json"
        assert out.exists()

    def test_save_catalog(self, tmp_path):
        builder = ManifestBuilder(project_root=tmp_path)
        manifests = [
            {"niche": "code"},
            {"niche": "medical"},
        ]
        builder.save_catalog(manifests)
        cat = tmp_path / "artifacts" / "manifests" / "catalog.json"
        assert cat.exists()
        data = json.loads(cat.read_text())
        assert data["num_specialists"] == 2
        assert "code" in data["specialists"]
        assert "medical" in data["specialists"]
