from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.schemas import ExecutiveAnswer


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None


class GuardrailService:
    """Deterministic policy first, optional Guardrails AI validators second."""

    injection_patterns = [
        re.compile(r"ignore (all|previous|prior) instructions", re.I),
        re.compile(r"reveal (the )?(system|developer) prompt", re.I),
        re.compile(r"show .*chain.?of.?thought", re.I),
    ]

    def __init__(self) -> None:
        self.settings = get_settings()
        self.external_available = False
        self._input_guard = None
        self._output_guard = None
        if self.settings.guardrails_enabled:
            try:
                from guardrails import Guard
                from guardrails_ai.detect_jailbreak import DetectJailbreak
                from guardrails_ai.secrets_present import SecretsPresent

                self._input_guard = Guard().use(DetectJailbreak(on_fail="exception"))
                self._output_guard = Guard().use(SecretsPresent(on_fail="exception"))
                self.external_available = True
            except Exception:
                # External validators are additive. Deterministic controls remain active.
                self.external_available = False

    def validate_input(self, text: str) -> GuardrailResult:
        for pattern in self.injection_patterns:
            if pattern.search(text):
                return GuardrailResult(False, "Prompt-injection pattern detected")
        if self._input_guard is not None:
            try:
                self._input_guard.validate(text)
            except Exception as exc:
                return GuardrailResult(False, f"Guardrails AI input validation failed: {exc}")
        return GuardrailResult(True)

    def validate_output(self, answer: ExecutiveAnswer) -> GuardrailResult:
        joined = " ".join([answer.summary, *answer.drivers, *answer.recommended_actions])
        if "<think>" in joined.lower() or "chain of thought" in joined.lower():
            return GuardrailResult(False, "Internal reasoning leakage detected")
        if self._output_guard is not None:
            try:
                self._output_guard.validate(joined)
            except Exception as exc:
                return GuardrailResult(False, f"Guardrails AI output validation failed: {exc}")
        return GuardrailResult(True)

    @property
    def status(self) -> str:
        if self.settings.guardrails_enabled and self.external_available:
            return "deterministic + Guardrails AI"
        if self.settings.guardrails_enabled:
            return "deterministic (Guardrails AI unavailable)"
        return "deterministic"
