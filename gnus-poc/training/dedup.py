"""Cross-niche deduplication using MinHash LSH."""

import argparse
import hashlib
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Set, Tuple


def _ngrams(text: str, n: int = 5) -> Set[int]:
    text = text.lower()
    hashes = set()
    for i in range(len(text) - n + 1):
        h = hashlib.md5(text[i:i + n].encode()).digest()[:8]
        hashes.add(struct.unpack("<Q", h)[0])
    return hashes


def _minhash_signature(shingles: Set[int], num_perm: int = 128) -> List[int]:
    max_hash = 2 ** 64 - 1
    sig = [max_hash] * num_perm
    for shingle in shingles:
        for i in range(num_perm):
            a = (2 * i + 1) * 6364136223846793005
            b = (2 * i + 3) * 1442695040888963407
            h = ((shingle * a + b) % 1000000007) % max_hash
            if h < sig[i]:
                sig[i] = h
    return sig


def _estimate_jaccard(sig_a: List[int], sig_b: List[int]) -> float:
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


def compute_overlap_matrix(samples_by_niche: dict, num_perm: int = 128) -> dict:
    niches = sorted(samples_by_niche.keys())
    signatures = {}

    for niche in niches:
        all_text = " ".join(s.get("text", "") for s in samples_by_niche[niche])
        shingles = _ngrams(all_text)
        signatures[niche] = _minhash_signature(shingles, num_perm)

    matrix = {}
    for i, niche_a in enumerate(niches):
        for j, niche_b in enumerate(niches):
            if j <= i:
                continue
            overlap = _estimate_jaccard(signatures[niche_a], signatures[niche_b])
            matrix[(niche_a, niche_b)] = round(overlap, 4)

    return matrix


def deduplicate_within_niche(samples: list, jaccard_threshold: float = 0.8, num_perm: int = 128) -> list:
    if len(samples) < 2:
        return samples

    signatures = []
    for s in samples:
        shingles = _ngrams(s.get("text", ""))
        signatures.append(_minhash_signature(shingles, num_perm))

    keep = []
    for i, sig_i in enumerate(signatures):
        duplicate = False
        for j in keep:
            if _estimate_jaccard(sig_i, signatures[j]) >= jaccard_threshold:
                duplicate = True
                break
        if not duplicate:
            keep.append(i)

    return [samples[i] for i in keep]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deduplicate synthetic data for a specialist niche")
    parser.add_argument("--niche", required=True, help="Specialist niche name")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    input_path = project_root / "artifacts" / "synthetic" / f"{args.niche}.jsonl"
    if not input_path.exists():
        print(f"No synthetic data found at {input_path} — nothing to deduplicate")
        sys.exit(0)

    samples = []
    with input_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    deduped = deduplicate_within_niche(samples)
    removed = len(samples) - len(deduped)

    out_dir = project_root / "artifacts" / "dedup"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{args.niche}_hashes.json").open("w") as f:
        json.dump({"niche": args.niche, "count": len(deduped)}, f)
    with (out_dir / f"{args.niche}_dedup_log.json").open("w") as f:
        json.dump({"niche": args.niche, "original": len(samples), "deduped": len(deduped), "removed_count": removed}, f)
    print(f"Dedup {args.niche}: {len(samples)} → {len(deduped)} ({removed} removed)")
