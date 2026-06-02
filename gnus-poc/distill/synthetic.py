"""Synthetic data generation using DeepSeek v4 pro teacher model."""

import json
import re
from pathlib import Path
from typing import Optional

from distill.teacher import TeacherClient
from distill.teacher_errors import SyntheticDataError


QUALITY_MIN_CHARS = 200

REFUSAL_PATTERNS = [
    r"\bI cannot\b",
    r"\bI['\u2019]m unable\b",
    r"\bas an AI\b",
    r"\bI don['\u2019]t have\b",
    r"\bI do not have\b",
    r"\bI am not able\b",
    r"\bI['\u2019]m not able\b",
    r"\bsorry.*cannot\b",
    r"\bcan['\u2019]t (?:help|assist|do that|generate|create|provide)\b",
]

_refusal_re = re.compile("|".join(REFUSAL_PATTERNS), re.IGNORECASE)


class SyntheticDataGenerator:
    def __init__(self, teacher_client: TeacherClient, project_root: Optional[Path] = None):
        self._client = teacher_client
        if project_root is None:
            project_root = Path(__file__).resolve().parent.parent
        self._project_root = project_root

    def generate_for_niche(
        self,
        niche_name: str,
        system_prompt: str,
        user_prompts: list,
        num_samples: int = 500,
        keywords: Optional[list] = None,
    ) -> list:
        if not user_prompts:
            return []

        results = []
        repeats = (num_samples // len(user_prompts)) + 1
        for i, user_prompt in enumerate(user_prompts * repeats):
            if len(results) >= num_samples:
                break

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            try:
                response = self._client.generate(messages)
                content = response.choices[0].message.content

                if self._passes_quality(content, keywords):
                    results.append({
                        "text": content,
                        "source": "synthetic_deepseek_v4_pro",
                        "niche": niche_name,
                        "prompt": user_prompt,
                    })
            except Exception as e:
                raise SyntheticDataError(
                    f"Failed to generate sample {i} for niche '{niche_name}': {e}"
                ) from e

        return results

    def _passes_quality(self, text: str, keywords: Optional[list] = None) -> bool:
        if len(text) < QUALITY_MIN_CHARS:
            return False

        if _refusal_re.search(text):
            return False

        if keywords:
            text_lower = text.lower()
            if not any(kw.lower() in text_lower for kw in keywords):
                return False

        return True

    def save_to_jsonl(self, samples: list, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w") as f:
            for sample in samples:
                f.write(json.dumps(sample) + "\n")
