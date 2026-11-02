from contextlib import nullcontext
import sys
import time
from types import ModuleType, SimpleNamespace

import pytest

from app.services.llm_service import GenerationTimeoutError, LLMService


def test_cpu_safe_profile_is_opt_in_and_only_applies_to_gqa(monkeypatch) -> None:
    import app.services.llm_service as llm_module

    monkeypatch.setattr(
        llm_module,
        "settings",
        SimpleNamespace(
            LLM_CPU_SAFE_PROFILE=True,
            LLM_CPU_SAFE_MAX_NEW_TOKENS=192,
            LLM_CPU_SAFE_TIMEOUT_SECONDS=180,
            MAX_NEW_TOKENS=1024,
        ),
    )
    service = LLMService()
    service.model = SimpleNamespace(
        config=SimpleNamespace(
            text_config=SimpleNamespace(
                num_attention_heads=8,
                num_key_value_heads=2,
            )
        )
    )

    assert service._cpu_safe_limits() == (192, 180.0)

    service.model.config.text_config.num_key_value_heads = 8
    assert service._cpu_safe_limits() == (None, None)

    llm_module.settings.LLM_CPU_SAFE_PROFILE = False
    service.model.config.text_config.num_key_value_heads = 2
    assert service._cpu_safe_limits() == (None, None)


def test_cpu_profile_keeps_existing_generation_budget_for_non_gqa(monkeypatch) -> None:
    import app.services.llm_service as llm_module

    monkeypatch.setattr(
        llm_module,
        "settings",
        SimpleNamespace(
            LLM_CPU_SAFE_PROFILE=True,
            LLM_CPU_SAFE_MAX_NEW_TOKENS=512,
            LLM_CPU_SAFE_TIMEOUT_SECONDS=300,
            MAX_NEW_TOKENS=1024,
        ),
    )
    service = LLMService()
    service.model = SimpleNamespace(
        config=SimpleNamespace(
            num_attention_heads=8,
            num_key_value_heads=8,
        )
    )

    assert service._cpu_safe_limits() == (None, None)


def test_local_model_validation_rejects_missing_weights(tmp_path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="weight files"):
        LLMService._validate_model_files(tmp_path)


def test_generation_deadline_stops_inside_decode_loop(monkeypatch) -> None:
    import app.services.llm_service as llm_module

    class FakeTensor:
        shape = (1, 2)
        device = "cpu"

        def to(self, _device):
            return self

    class FakeBooleanTensor:
        def __init__(self, value: bool) -> None:
            self.value = value

        def __or__(self, other):
            return FakeBooleanTensor(self.value or other.value)

    class FakeTorch(ModuleType):
        bool = object()

        @staticmethod
        def no_grad():
            return nullcontext()

        @staticmethod
        def full(_shape, value, **_kwargs):
            return FakeBooleanTensor(value)

    class FakeStoppingCriteriaList(list):
        def __call__(self, input_ids, scores=None, **kwargs):
            result = FakeBooleanTensor(False)
            for criterion in self:
                result = result | criterion(input_ids, scores, **kwargs)
            return result

    fake_transformers = ModuleType("transformers")
    fake_transformers.StoppingCriteriaList = FakeStoppingCriteriaList
    monkeypatch.setitem(sys.modules, "torch", FakeTorch("torch"))
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setattr(
        llm_module,
        "settings",
        SimpleNamespace(
            CONTEXT_WINDOW=32,
            MAX_NEW_TOKENS=1024,
            TEMPERATURE=0.7,
            TOP_P=0.9,
        ),
    )

    class FakeTokenizer:
        chat_template = None
        pad_token_id = 0
        eos_token_id = 0

        def __call__(self, *_args, **_kwargs):
            return SimpleNamespace(input_ids=FakeTensor(), attention_mask=FakeTensor())

        def decode(self, *_args, **_kwargs):
            raise AssertionError("Timed-out partial tokens must not be decoded")

    class SlowModel:
        config = SimpleNamespace(
            text_config=SimpleNamespace(
                num_attention_heads=8,
                num_key_value_heads=2,
                max_position_embeddings=32,
            )
        )

        def __init__(self) -> None:
            self.calls = 0

        def generate(self, **kwargs):
            self.calls += 1
            assert kwargs["max_new_tokens"] == 5
            time.sleep(0.02)
            should_stop = kwargs["stopping_criteria"](FakeTensor(), scores=None)
            assert should_stop.value is True
            return None

    service = LLMService()
    service.model = SlowModel()
    service.tokenizer = FakeTokenizer()
    service.model_context_limit = 7

    with pytest.raises(GenerationTimeoutError):
        service.generate("prompt", max_tokens=192, deadline=time.monotonic() + 0.005)

    assert service.model.calls == 1