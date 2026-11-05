import json
import re
import time
from typing import Any, Optional, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import logger

T = TypeVar("T", bound=BaseModel)


class GenerationTimeoutError(TimeoutError):
    """Raised when decoding exceeds its configured wall-clock deadline."""


class _GenerationDeadline:
    def __init__(self, deadline: float, torch_module: Any) -> None:
        self.deadline = deadline
        self.torch = torch_module
        self.timed_out = False

    def __call__(self, input_ids: Any, scores: Any, **kwargs: Any) -> Any:
        self.timed_out = self.timed_out or time.monotonic() >= self.deadline
        return self.torch.full(
            (input_ids.shape[0],),
            self.timed_out,
            dtype=self.torch.bool,
            device=input_ids.device,
        )


class LLMService:
    """Singleton service for local CPU-based LLM inference and structured output parsing."""

    _instance: Optional["LLMService"] = None

    def __init__(self) -> None:
        self.model: Any = None
        self.tokenizer: Any = None
        self.lora_loaded: bool = False
        self.active_adapter_path: Optional[str] = None
        self.model_context_limit: Optional[int] = None

    @staticmethod
    def _validate_model_files(local_path) -> None:
        if not (local_path / "config.json").is_file():
            raise FileNotFoundError(f"Model configuration is missing from {local_path}.")
        if not any(
            (local_path / filename).is_file()
            for filename in ("tokenizer.json", "tokenizer_config.json", "tokenizer.model")
        ):
            raise FileNotFoundError(f"Tokenizer files are missing from {local_path}.")
        has_weights = any(local_path.glob("*.safetensors")) or any(
            local_path.glob("pytorch_model*.bin")
        ) or any(local_path.glob("model*.bin"))
        if not has_weights:
            raise FileNotFoundError(f"Model weight files are missing from {local_path}.")

    def _text_config(self) -> Any:
        config = getattr(self.model, "config", None)
        return getattr(config, "text_config", config)

    def _context_limit(self) -> Optional[int]:
        config = self._text_config()
        value = getattr(config, "max_position_embeddings", None)
        if value is None:
            value = getattr(config, "max_sequence_length", None)
        return int(value) if value else None

    def _uses_gqa(self) -> bool:
        config = self._text_config()
        attention_heads = getattr(config, "num_attention_heads", None)
        key_value_heads = getattr(config, "num_key_value_heads", None)
        return bool(
            attention_heads
            and key_value_heads
            and int(key_value_heads) < int(attention_heads)
        )

    def _cpu_safe_limits(self) -> tuple[Optional[int], Optional[float]]:
        if not settings.LLM_CPU_SAFE_PROFILE or not self._uses_gqa():
            return None, None
        token_limit = int(settings.LLM_CPU_SAFE_MAX_NEW_TOKENS)
        timeout = float(settings.LLM_CPU_SAFE_TIMEOUT_SECONDS)
        if token_limit <= 0 or timeout <= 0:
            raise ValueError("CPU-safe token and timeout limits must be positive.")
        return min(token_limit, settings.MAX_NEW_TOKENS), timeout

    def cpu_safe_profile_active(self) -> bool:
        return self._cpu_safe_limits()[0] is not None

    @classmethod
    def get_instance(cls) -> "LLMService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_loaded(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def load_model(self) -> bool:
        """
        Load causal LLM model and tokenizer from local path on CPU.
        Returns True if loaded, False otherwise.
        """
        if self.is_loaded():
            return True

        local_path = settings.resolved_llm_model_path
        try:
            has_local_model = local_path.is_dir() and any(local_path.iterdir())
        except OSError:
            has_local_model = False
        if not has_local_model:
            logger.warning(f"LLM model files are unavailable locally at {local_path}.")
            return False

        logger.info(f"Loading LLM model from '{local_path}' (CPU inference)...")
        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

            self._validate_model_files(local_path)
            model_config = AutoConfig.from_pretrained(
                str(local_path),
                trust_remote_code=True,
                local_files_only=True,
            )
            text_config = getattr(model_config, "text_config", model_config)
            context_limit = getattr(text_config, "max_position_embeddings", None)
            if context_limit and not 0 < settings.CONTEXT_WINDOW <= int(context_limit):
                raise ValueError(
                    f"CONTEXT_WINDOW={settings.CONTEXT_WINDOW} exceeds the model limit "
                    f"of {context_limit} tokens."
                )

            self.tokenizer = AutoTokenizer.from_pretrained(
                str(local_path),
                trust_remote_code=True,
                local_files_only=True,
            )
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.model = AutoModelForCausalLM.from_pretrained(
                str(local_path),
                config=model_config,
                torch_dtype=torch.float32,
                device_map="cpu",
                trust_remote_code=True,
                local_files_only=True,
            )
            self.model.eval()
            self.model_context_limit = self._context_limit()

            # Load LoRA adapter if configured and enabled
            if settings.LORA_ENABLED and settings.resolved_lora_path:
                self.load_lora_adapter(str(settings.resolved_lora_path))

            logger.info("LLM model successfully initialized on CPU.")
            return True
        except Exception as exc:
            logger.warning(
                f"LLM model could not be loaded from '{local_path}': {exc}. "
                f"To run AI generation offline, download the model files to {local_path}."
            )
            self.model = None
            self.tokenizer = None
            self.model_context_limit = None
            return False

    def load_lora_adapter(self, adapter_path: str) -> bool:
        """Merge a PEFT LoRA adapter with the base model."""
        if self.model is None:
            logger.warning("Cannot load LoRA adapter without base model.")
            return False

        try:
            from peft import PeftModel

            logger.info(f"Applying LoRA adapter from {adapter_path}...")
            peft_model = PeftModel.from_pretrained(self.model, adapter_path)
            self.model = peft_model.merge_and_unload()
            self.lora_loaded = True
            self.active_adapter_path = adapter_path
            logger.info("LoRA adapter merged successfully.")
            return True
        except Exception as exc:
            logger.error(f"Failed to load LoRA adapter from {adapter_path}: {exc}")
            return False

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        deadline: Optional[float] = None,
    ) -> str:
        """
        Generate text output from the model using tokenization and model.generate().
        Does NOT use pipeline wrapper.
        """
        if not self.is_loaded():
            loaded = self.load_model()
            if not loaded or not self.is_loaded():
                raise RuntimeError(
                    f"LLM model is not loaded. Model not found at '{settings.resolved_llm_model_path}'. "
                    f"Please download the model files for offline inference."
                )

        if settings.CONTEXT_WINDOW <= 0:
            raise ValueError("CONTEXT_WINDOW must be a positive token count.")

        import torch

        # Format prompt with chat template if supported
        if hasattr(self.tokenizer, "chat_template") and self.tokenizer.chat_template:
            messages = [{"role": "user", "content": prompt}]
            try:
                formatted_prompt = self.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                formatted_prompt = prompt
        else:
            formatted_prompt = prompt

        inputs = self.tokenizer(
            formatted_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=settings.CONTEXT_WINDOW,
        )
        input_ids = inputs.input_ids.to("cpu")
        attention_mask = inputs.attention_mask.to("cpu")
        input_len = input_ids.shape[1]

        context_limit = self.model_context_limit or self._context_limit()
        if context_limit is not None and input_len >= context_limit:
            raise ValueError(
                f"The prompt uses {input_len} tokens, leaving no room in the model's "
                f"{context_limit}-token context window for a response."
            )

        max_new = max_tokens or settings.MAX_NEW_TOKENS
        if context_limit is not None:
            max_new = min(max_new, context_limit - input_len)
        temp = temperature if temperature is not None else settings.TEMPERATURE
        do_sample = temp > 0.0

        gen_kwargs: dict[str, Any] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "max_new_tokens": max_new,
            "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
            "do_sample": do_sample,
        }
        if do_sample:
            gen_kwargs["temperature"] = temp
            gen_kwargs["top_p"] = settings.TOP_P

        deadline_criteria = None
        if deadline is not None:
            from transformers import StoppingCriteriaList

            deadline_criteria = _GenerationDeadline(deadline, torch)
            gen_kwargs["stopping_criteria"] = StoppingCriteriaList([deadline_criteria])

        with torch.no_grad():
            outputs = self.model.generate(**gen_kwargs)

        if deadline_criteria and deadline_criteria.timed_out:
            raise GenerationTimeoutError("Local model generation exceeded its time limit.")
        if deadline is not None and time.monotonic() >= deadline:
            raise GenerationTimeoutError("Local model generation exceeded its time limit.")

        new_tokens = outputs[0][input_len:]
        response_text = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        return response_text

    def generate_structured(
        self,
        prompt: str,
        pydantic_model: type[T],
        max_retries: int = 1,
        compact_output: bool = True,
    ) -> T:
        """
        Enforce structured JSON output matching a Pydantic schema from the LLM.
        """
        schema = pydantic_model.model_json_schema()
        schema_json = json.dumps(schema, separators=(",", ":"))
        safe_token_limit, safe_timeout = self._cpu_safe_limits()
        instruction = (
            f"{prompt}\n\n"
            f"IMPORTANT: Respond ONLY with a valid JSON object matching the JSON Schema below. "
            f"Do not include any intro text, markdown explanation, or trailing comments.\n"
            f"JSON Schema:\n{schema_json}\n"
        )
        if safe_token_limit is not None and compact_output:
            instruction += (
                "CPU output budget is limited. Return compact valid JSON with every schema key. "
                "Keep each string field to one short sentence and lists to at most two short items. "
            )
            if "practice_questions" in schema.get("properties", {}):
                instruction += "Include exactly one concise practice question. "
            instruction += "Do not repeat the schema or add text outside the JSON object.\n"

        last_error = ""
        current_prompt = instruction
        deadline = time.monotonic() + safe_timeout if safe_timeout is not None else None

        for attempt in range(max_retries + 1):
            if deadline is not None and time.monotonic() >= deadline:
                raise GenerationTimeoutError(
                    "Structured generation exceeded its total time limit."
                )
            raw_output = self.generate(
                current_prompt,
                temperature=0.0 if safe_token_limit is not None else 0.1,
                max_tokens=safe_token_limit,
                deadline=deadline,
            )

            # Extract json substring
            json_str = self._extract_json_string(raw_output)
            try:
                parsed_data = json.loads(json_str)
                return pydantic_model.model_validate(parsed_data)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    f"Structured output parsing failed (attempt {attempt+1}/{max_retries+1}): {exc}"
                )
                if attempt < max_retries:
                    current_prompt = (
                        f"{instruction}\n\n"
                        f"The previous response failed validation: {last_error}. "
                        f"Return only the corrected valid JSON object matching the schema."
                    )

        raise ValueError(
            f"Failed to generate structured output for {pydantic_model.__name__} after {max_retries+1} attempts. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _extract_json_string(text: str) -> str:
        """Extract JSON code block or outermost braces from text."""
        # 1. Check for markdown code blocks ```json ... ```
        block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if block_match:
            return block_match.group(1).strip()

        # 2. Find outermost { ... } or [ ... ]
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace : last_brace + 1].strip()

        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            return text[first_bracket : last_bracket + 1].strip()

        return text.strip()

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic status of LLM engine."""
        return {
            "llm_loaded": self.is_loaded(),
            "llm_model_id": settings.LLM_MODEL_ID,
            "llm_model_path": str(settings.resolved_llm_model_path),
            "llm_device": "cpu",
            "lora_adapter_path": self.active_adapter_path or (str(settings.resolved_lora_path) if settings.resolved_lora_path else None),
            "lora_loaded": self.lora_loaded,
            "context_window": settings.CONTEXT_WINDOW,
            "max_new_tokens": settings.MAX_NEW_TOKENS,
        }


def get_llm_service() -> LLMService:
    return LLMService.get_instance()
