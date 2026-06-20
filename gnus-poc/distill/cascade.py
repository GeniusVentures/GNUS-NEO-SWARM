"""Multi-teacher cascade orchestrator with benchmark-routed Level 2 escalation.

Implements a confidence-gated teacher escalation flow:

1. **Level 1 (always):** The fast, cheap teacher runs first for every request.
   When its logprobs mean confidence is at or above the configured threshold,
   the result is returned immediately — no Level 2 invocation.

2. **Benchmark-Routed Level 2:** When Level 1 confidence is below threshold,
   the best Level 2 teacher for the detected domain is selected from a
   pre-configured benchmark table.  If that teacher still falls below
   threshold, the next-highest-scoring Level 2 teacher is tried.

3. **Best-Effort Return:** The cascade never fails silently.  If all Level 2
   teachers produce below-threshold confidence, the highest-confidence result
   among them is returned.  If every teacher raises an exception,
   ``TeacherConfigError`` is raised with diagnostic details.

The benchmark table is loaded from ``teacher_benchmark`` in ``pipeline.yaml``
and maps domain keys to ``{model_name: strength_score}`` dicts.  Model names
must match keys in the ``models`` config block.
"""

import math

_DOMAIN_MAP = {
    "code": "coding",
    "medical": "medical",
    "qa_technical": "qa_technical",
    "encyclopedic": "encyclopedic",
    "patents": "patents",
}


def compute_logprob_confidence(response) -> float:
    """Compute mean token probability (confidence) from a response with logprobs.

    Extracts logprobs from an OpenAI-compatible response format::

        response.choices[0].logprobs.content[].token_logprob

    When the response is a ``_ResponseWrapper``, logprobs are accessed
    via ``response._raw_response``.  Falls back to accessing ``response``
    directly for test mocks that set logprobs on the outer object.

    Returns the exponential of the mean log probability, yielding a value in
    ``[0.0, 1.0]``.  Returns ``0.0`` when logprobs data is missing or the
    response structure is unexpected.

    Args:
        response: A ``_ResponseWrapper`` returned by
            ``TeacherClient.generate_with_logprobs()``, or a mock with
            ``.choices[0].logprobs.content[]`` directly accessible.

    Returns:
        Confidence score as a float between 0.0 and 1.0.
    """
    def _extract_logprobs(source):
        logprobs_content = source.choices[0].logprobs.content
        if not logprobs_content:
            return []
        return [token.token_logprob for token in logprobs_content]

    try:
        # Try the direct response path first (for mock objects in tests)
        token_logprobs = _extract_logprobs(response)
    except (AttributeError, IndexError, TypeError):
        try:
            # Fall back to _raw_response (real _ResponseWrapper path)
            raw = response._raw_response
            token_logprobs = _extract_logprobs(raw)
        except (AttributeError, IndexError, TypeError):
            return 0.0

    if not token_logprobs:
        return 0.0
    mean_logprob = sum(token_logprobs) / len(token_logprobs)
    return math.exp(mean_logprob)


class CascadeResult:
    """Result of a multi-teacher cascade execution.

    Attributes:
        final_content: The response text returned to the caller.
        level1_confidence: Confidence score from Level 1 (0.0 if Level 1
            failed with an exception).
        level2_confidence: Confidence score from Level 2, or ``None`` if
            no escalation occurred.
        level1_model: The Level 1 model name.
        level2_model: The Level 2 model that produced ``final_content``,
            or ``None`` if no escalation occurred.
        escalated: ``True`` if Level 2 was invoked.
        attempts: List of per-attempt records, each a dict with keys
            ``model_name``, ``confidence``, and ``error`` (str or None).
    """

    def __init__(
        self,
        final_content,
        level1_confidence,
        level2_confidence,
        level1_model,
        escalated,
        attempts,
        level2_model=None,
    ):
        self.final_content = final_content
        self.level1_confidence = level1_confidence
        self.level2_confidence = level2_confidence
        self.level1_model = level1_model
        self.level2_model = level2_model
        self.escalated = escalated
        self.attempts = attempts

    def to_dict(self):
        """Return a JSON-serialisable representation for logging."""
        return {
            "final_content": self.final_content,
            "level1_confidence": self.level1_confidence,
            "level2_confidence": self.level2_confidence,
            "level1_model": self.level1_model,
            "level2_model": self.level2_model,
            "escalated": self.escalated,
            "attempts": self.attempts,
        }


class TeacherCascade:
    """Multi-teacher cascade orchestrator with benchmark-routed escalation.

    Constructor arguments map directly to config values so that
    ``TeacherClient.__init__`` can wire them from ``pipeline.yaml``::

        cascade = TeacherCascade(
            teacher_client=self,
            benchmark_table=config["teacher_benchmark"],
            level1_model=config["teacher"]["level1"],
            confidence_threshold=config["teacher"]["confidence_threshold"],
        )
    """

    def __init__(self, teacher_client, benchmark_table, level1_model, confidence_threshold):
        """Initialise the cascade orchestrator.

        Args:
            teacher_client: A ``TeacherClient`` instance whose
                ``generate_with_logprobs()`` method is used for all
                teacher calls within the cascade.
            benchmark_table: The ``teacher_benchmark`` dict from
                ``pipeline.yaml`` — domain key → ``{model: score}``.
            level1_model: The always-first teacher model name
                (e.g. ``"deepseek-v4-fast"``).
            confidence_threshold: Minimum logprobs confidence
                (0.0–1.0) to avoid Level 2 escalation.
        """
        self._teacher = teacher_client
        self._benchmark_table = benchmark_table
        self._level1_model = level1_model
        self._confidence_threshold = confidence_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, messages, domain, **kwargs):
        """Run the confidence-gated teacher cascade.

        Args:
            messages: List of message dicts (OpenAI format).
            domain: Specialist niche name (e.g. ``"code"``, ``"medical"``).
                Mapped to a benchmark table key via ``_DOMAIN_MAP``.
            **kwargs: Extra parameters forwarded to
                ``TeacherClient.generate_with_logprobs()``.

        Returns:
            ``CascadeResult`` with the best-available response.

        Raises:
            TeacherConfigError: If every teacher in the cascade raises an
                exception (no response could be produced).
        """
        from distill.teacher_errors import TeacherConfigError

        attempts = []

        # -- Step 1: Level 1 (always) ---------------------------------------
        level1_confidence = 0.0
        level1_content = None
        try:
            l1_response = self._teacher.generate_with_logprobs(
                self._level1_model, messages, **kwargs
            )
            level1_confidence = compute_logprob_confidence(l1_response)
            level1_content = l1_response.choices[0].message.content
            attempts.append(
                {
                    "model_name": self._level1_model,
                    "confidence": round(level1_confidence, 4),
                    "error": None,
                }
            )
        except Exception as exc:
            attempts.append(
                {
                    "model_name": self._level1_model,
                    "confidence": 0.0,
                    "error": str(exc),
                }
            )
            level1_confidence = 0.0

        # -- Step 2: Confidence check ---------------------------------------
        if level1_confidence >= self._confidence_threshold and level1_content is not None:
            return CascadeResult(
                final_content=level1_content,
                level1_confidence=level1_confidence,
                level2_confidence=None,
                level1_model=self._level1_model,
                escalated=False,
                attempts=attempts,
            )

        # -- Step 3: Benchmark routing → Level 2 ----------------------------
        benchmark_key = _DOMAIN_MAP.get(domain)
        if benchmark_key is None or benchmark_key not in self._benchmark_table:
            # Unknown domain — fall back to the first available domain key
            if self._benchmark_table:
                benchmark_key = next(iter(self._benchmark_table.keys()))
            elif level1_content is not None:
                # No benchmark table at all — return Level 1 result as-is
                return CascadeResult(
                    final_content=level1_content,
                    level1_confidence=level1_confidence,
                    level2_confidence=None,
                    level1_model=self._level1_model,
                    escalated=False,
                    attempts=attempts,
                )
            else:
                raise TeacherConfigError(
                    f"No benchmark table entries for domain '{domain}' "
                    f"and Level 1 produced no content."
                )

        domain_scores = self._benchmark_table[benchmark_key]
        # Sort Level 2 models by strength score descending (best first)
        sorted_models = sorted(
            domain_scores.items(), key=lambda item: item[1],
            reverse=True,
        )

        best_l2_content = None
        best_l2_confidence = 0.0
        best_l2_model = None

        for model_name, _score in sorted_models:
            try:
                l2_response = self._teacher.generate_with_logprobs(
                    model_name, messages, **kwargs
                )
                l2_confidence = compute_logprob_confidence(l2_response)
                l2_content = l2_response.choices[0].message.content
                attempts.append(
                    {
                        "model_name": model_name,
                        "confidence": round(l2_confidence, 4),
                        "error": None,
                    }
                )

                if l2_confidence > best_l2_confidence:
                    best_l2_confidence = l2_confidence
                    best_l2_content = l2_content
                    best_l2_model = model_name

                if l2_confidence >= self._confidence_threshold:
                    return CascadeResult(
                        final_content=l2_content,
                        level1_confidence=level1_confidence,
                        level2_confidence=l2_confidence,
                        level1_model=self._level1_model,
                        level2_model=model_name,
                        escalated=True,
                        attempts=attempts,
                    )
            except Exception as exc:
                attempts.append(
                    {
                        "model_name": model_name,
                        "confidence": 0.0,
                        "error": str(exc),
                    }
                )

        # -- Step 4: Return best-available result ---------------------------
        if best_l2_content is not None:
            return CascadeResult(
                final_content=best_l2_content,
                level1_confidence=level1_confidence,
                level2_confidence=best_l2_confidence,
                level1_model=self._level1_model,
                level2_model=best_l2_model,
                escalated=True,
                attempts=attempts,
            )

        # Every teacher failed
        raise TeacherConfigError(
            f"All teachers failed for cascade on domain '{domain}'"
        )
