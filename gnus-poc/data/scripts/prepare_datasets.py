"""
Prepare training datasets for GNUS.ai specialists
Creates clean train/val splits from source-based niches
"""

import json
import os
import sys
from pathlib import Path
from datasets import load_dataset, Dataset, DatasetDict
from collections import defaultdict
import random
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from training.tokenizer_utils import load_tokenizer, format_chat

# Load tokenizer once at module level to avoid reloading per sample
_TOKENIZER = load_tokenizer("mlx-community/Qwen3-30B-A3B-Instruct-2507-bf16")

# Configuration
SELECTED_NICHES = ['medical', 'qa_technical', 'code', 'encyclopedic', 'patents']  # All 5 for robust PoC
VAL_SPLIT = 0.1  # 10% validation
TEST_SPLIT = 0.05  # 5% test
RANDOM_SEED = 42
MAX_SAMPLES_PER_NICHE = 10000  # Cap for balanced training

OUTPUT_DIR = str(PROJECT_ROOT / 'data' / 'specialists')
os.makedirs(OUTPUT_DIR, exist_ok=True)

random.seed(RANDOM_SEED)


def load_niche_config():
    """Load the source-based niche analysis"""
    with open(str(PROJECT_ROOT / 'data' / 'analysis' / 'source_based_niches.json'), 'r') as f:
        data = json.load(f)
    return data['viable_niches'], data['extraction_config']


def extract_niche_samples(niche_name, niche_config, target_niches_config):
    """
    Extract all samples for a specific niche from Common Pile
    """
    print(f"\nExtracting {niche_name.upper()} samples...")

    # Get source list for this niche
    sources = target_niches_config['target_niches'][niche_name]['sources']
    print(f"  Target sources: {', '.join(sources)}")

    try:
        dataset = load_dataset(
            "monology/pile-uncopyrighted",
            split="train",
            streaming=True,
            trust_remote_code=True
        )
    except Exception as e:
        print(f"  Using alternative dataset...")
        dataset = load_dataset(
            "EleutherAI/pile",
            split="train",
            streaming=True,
            trust_remote_code=True
        )

    samples = []
    target_size = min(niche_config['size'] * 2, MAX_SAMPLES_PER_NICHE)  # Oversample then filter

    print(f"  Target: {target_size} samples")

    # Metadata field validation (Pitfall #4) — validate schema on first example
    _meta_validated = False
    unknown_source_count = 0

    for i, example in enumerate(dataset):
        if len(samples) >= target_size:
            break

        if i % 10000 == 0 and i > 0:
            print(f"    Scanned {i} docs, collected {len(samples)}...")

        # Check source
        meta = example.get('meta', {})
        source = meta.get('pile_set_name', meta.get('source', 'unknown'))

        # Pitfall #4: Validate metadata schema on first example
        if not _meta_validated:
            _meta_validated = True
            if isinstance(meta, dict) and meta:
                meta_keys = list(meta.keys())
                expected_fields = ['pile_set_name', 'source', 'dataset']
                found = any(k in meta_keys for k in expected_fields)
                if not found:
                    raise RuntimeError(
                        f"Common Pile metadata schema changed — expected one of "
                        f"{expected_fields} but found: {meta_keys}"
                    )
            # If meta is empty dict, that's acceptable — source will be 'unknown'

        if source == 'unknown':
            unknown_source_count += 1

        if source in sources:
            text = example.get('text', example.get('content', ''))

            # Quality filters
            if len(text) < 100:  # Too short
                continue
            if len(text) > 50000:  # Too long for LoRA training
                text = text[:50000]

            samples.append({
                'text': text,
                'source': source,
                'niche': niche_name
            })

    print(f"  ✓ Collected {len(samples)} samples")

    # Pitfall #4: Warn if >10% of samples have unknown source
    total_processed = i + 1 if samples else 0
    if total_processed > 0:
        unknown_pct = (unknown_source_count / total_processed) * 100
        if unknown_pct > 10:
            print(f"  ⚠ Warning: {unknown_source_count}/{total_processed} "
                  f"({unknown_pct:.1f}%) samples have source='unknown'. "
                  f"Metadata schema may have changed.")

    return samples


def create_splits(samples, niche_name):
    """
    Create train/val/test splits
    """
    random.shuffle(samples)

    n = len(samples)
    test_size = int(n * TEST_SPLIT)
    val_size = int(n * VAL_SPLIT)
    train_size = n - test_size - val_size

    splits = {
        'train': samples[:train_size],
        'validation': samples[train_size:train_size + val_size],
        'test': samples[train_size + val_size:]
    }

    print(f"  Splits: train={train_size}, val={val_size}, test={test_size}")

    return splits


def format_for_training(samples, niche_name):
    """
    Format samples for Qwen3 instruction tuning using tokenizer.apply_chat_template().

    Per FOUND-01: Uses the actual tokenizer's native chat template (Qwen3 format)
    instead of hand-rolled <|im_start|> strings that cause Qwen2.5/Qwen3 mismatch.
    """
    formatted = []

    for sample in samples:
        text = sample.get('text', '')
        meta = sample.get('meta', {})

        # Build messages list with system/user/assistant roles
        if niche_name == 'medical':
            context_end = min(1000, len(text) // 2)
            response_end = min(context_end + 1500, len(text))
            messages = [
                {"role": "system", "content": "You are a medical research specialist."},
                {"role": "user", "content": f"Provide medical or biomedical information based on the following research:\n{text[:context_end]}"},
                {"role": "assistant", "content": text[context_end:response_end]},
            ]

        elif niche_name == 'qa_technical':
            # Pitfall #16 fix: Check metadata for StackExchange Q&A structure first
            if isinstance(meta, dict) and 'question' in meta and 'answer' in meta:
                question = meta['question']
                answer = meta['answer']
            elif isinstance(meta, dict) and 'Question' in meta and 'Answer' in meta:
                question = meta['Question']
                answer = meta['Answer']
            elif 'Q:' in text and 'A:' in text:
                parts = text.split('A:', 1)
                question = parts[0].replace('Q:', '').strip()
                answer = parts[1].strip() if len(parts) > 1 else text
            else:
                question = "Explain this technical concept:"
                answer = text[:2000]
            messages = [
                {"role": "system", "content": "You are a technical Q&A specialist."},
                {"role": "user", "content": question[:500]},
                {"role": "assistant", "content": answer[:1500]},
            ]

        elif niche_name == 'code':
            messages = [
                {"role": "system", "content": "You are a programming and code documentation specialist."},
                {"role": "user", "content": "Explain or document this code:"},
                {"role": "assistant", "content": text[:2000]},
            ]

        elif niche_name == 'encyclopedic':
            # Extract title if present (Wikipedia format)
            lines = text.split('\n', 2)
            title = lines[0].strip() if len(lines) > 0 and lines[0].strip() else "this topic"
            content = lines[1] if len(lines) > 1 else text
            messages = [
                {"role": "system", "content": "You are an encyclopedic knowledge specialist."},
                {"role": "user", "content": f"Provide information about {title}:"},
                {"role": "assistant", "content": content[:2000]},
            ]

        elif niche_name == 'patents':
            messages = [
                {"role": "system", "content": "You are a patent and technical innovation specialist."},
                {"role": "user", "content": "Explain this invention or technical innovation:"},
                {"role": "assistant", "content": text[:2000]},
            ]

        else:
            messages = [
                {"role": "user", "content": text[:2000]},
            ]

        # Use tokenizer's native chat template — NOT hand-rolled <|im_start|> format
        formatted_text = format_chat(messages, _TOKENIZER)

        formatted.append({
            'text': formatted_text,
            'source': sample.get('source', 'unknown'),
            'niche': niche_name
        })

    return formatted


def save_datasets(niche_name, splits):
    """
    Save as Hugging Face datasets for easy loading
    """
    date_version = datetime.now().strftime('%Y%m%d%H%M')
    niche_dir = f"{OUTPUT_DIR}/{niche_name}_v{date_version}"
    os.makedirs(niche_dir, exist_ok=True)

    dataset_dict = {}
    for split_name, samples in splits.items():
        formatted = format_for_training(samples, niche_name)
        dataset_dict[split_name] = Dataset.from_list(formatted)

    dataset = DatasetDict(dataset_dict)
    dataset.save_to_disk(niche_dir)

    print(f"  ✓ Saved to {niche_dir}")

    # Also save metadata
    metadata = {
        'niche': niche_name,
        'train_size': len(splits['train']),
        'val_size': len(splits['validation']),
        'test_size': len(splits['test']),
        'total': sum(len(s) for s in splits.values())
    }

    with open(f"{niche_dir}/metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    return metadata


def main():
    print("GNUS.AI Dataset Preparation")
    print("=" * 80)

    # Load configuration
    viable_niches, extraction_config = load_niche_config()
    niche_lookup = {n['name']: n for n in viable_niches}

    print(f"\nPreparing datasets for ALL 5 SPECIALISTS:")
    for niche in SELECTED_NICHES:
        if niche in niche_lookup:
            print(f"  • {niche.upper()}: ~{niche_lookup[niche]['size']:,} samples available")

    print(
        f"\nSplits: {(1 - VAL_SPLIT - TEST_SPLIT) * 100:.0f}% train, {VAL_SPLIT * 100:.0f}% val, {TEST_SPLIT * 100:.0f}% test")
    print(f"Max samples per niche: {MAX_SAMPLES_PER_NICHE:,}\n")

    all_metadata = {}

    for niche_name in SELECTED_NICHES:
        if niche_name not in niche_lookup:
            print(f"⚠ Skipping {niche_name} - not in viable niches")
            continue

        print(f"\n{'=' * 80}")
        print(f"Processing {niche_name.upper()} Specialist")
        print(f"{'=' * 80}")

        niche_config = niche_lookup[niche_name]

        # Extract samples
        samples = extract_niche_samples(niche_name, niche_config, extraction_config)

        if len(samples) < 1000:
            print(f"  ⚠ Only {len(samples)} samples - may be insufficient for training")
            continue

        # Create splits
        splits = create_splits(samples, niche_name)

        # Save
        metadata = save_datasets(niche_name, splits)
        all_metadata[niche_name] = metadata

    # Summary
    print("\n" + "=" * 80)
    print("DATASET PREPARATION COMPLETE")
    print("=" * 80)

    total_train = 0
    total_val = 0
    total_test = 0

    for niche_name, meta in all_metadata.items():
        print(f"\n{niche_name.upper()}:")
        print(f"  Train: {meta['train_size']:,} samples")
        print(f"  Val:   {meta['val_size']:,} samples")
        print(f"  Test:  {meta['test_size']:,} samples")
        print(f"  Total: {meta['total']:,} samples")

        total_train += meta['train_size']
        total_val += meta['val_size']
        total_test += meta['test_size']

    print(f"\n{'=' * 80}")
    print(f"GRAND TOTAL:")
    print(f"  Train: {total_train:,} samples across {len(all_metadata)} specialists")
    print(f"  Val:   {total_val:,} samples")
    print(f"  Test:  {total_test:,} samples")
    print(f"  Total: {total_train + total_val + total_test:,} samples")

    print(f"\n✓ All datasets saved to {OUTPUT_DIR}/")
    print("\nNext steps:")
    print("  1. Review datasets in data/specialists/")
    print("  2. Run specialist training script (train_specialists.py)")
    print("  3. Validate specialist differentiation")
    print("\nEstimated training time (with LoRA):")
    print(f"  ~{len(all_metadata) * 30}-{len(all_metadata) * 60} minutes on Mac Studio M2 Ultra")


if __name__ == "__main__":
    main()
