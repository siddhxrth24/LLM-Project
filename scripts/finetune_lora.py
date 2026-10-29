#!/usr/bin/env python3
"""Fine-tune a language model with LoRA for SemesTrack teaching assistant.

This script fine-tunes a base model using PEFT/LoRA to specialize it for:
- Generating structured educational content
- Classifying topic coverage
- Creating study plans

CPU-safe defaults are used. GPU training is supported when available.

Usage:
    python scripts/finetune_lora.py --dataset training/data/train.jsonl
    python scripts/finetune_lora.py --dataset training/data/train.jsonl --smoke-test
    python scripts/finetune_lora.py --help
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check that required packages are installed."""
    missing = []
    try:
        import torch
    except ImportError:
        missing.append("torch")
    try:
        import transformers
    except ImportError:
        missing.append("transformers")
    try:
        import peft
    except ImportError:
        missing.append("peft")
    
    if missing:
        logger.error(f"Missing required packages: {', '.join(missing)}")
        logger.error("Install with: pip install torch transformers peft")
        sys.exit(1)
    
    return True


def load_dataset(filepath: str) -> list[dict]:
    """Load and validate JSONL dataset."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {filepath}")
    
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if "instruction" not in data or "output" not in data:
                    logger.warning(f"Line {line_num}: Missing required fields, skipping")
                    continue
                examples.append(data)
            except json.JSONDecodeError:
                logger.warning(f"Line {line_num}: Invalid JSON, skipping")
    
    logger.info(f"Loaded {len(examples)} training examples from {filepath}")
    return examples


def format_training_example(example: dict, tokenizer) -> str:
    """Format a single training example into a chat-template string.
    
    Uses the model's chat template if available, otherwise uses a simple format.
    """
    instruction = example["instruction"]
    input_text = example.get("input", "")
    output = example["output"]
    
    if input_text:
        user_content = f"{instruction}\n\nContext:\n{input_text}"
    else:
        user_content = instruction
    
    messages = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": output},
    ]
    
    try:
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
    except Exception:
        # Fallback format
        text = f"### Instruction:\n{user_content}\n\n### Response:\n{output}"
    
    return text


class TrainingDataset:
    """Simple dataset class for training."""
    
    def __init__(self, texts: list[str], tokenizer, max_length: int):
        self.encodings = []
        for text in texts:
            encoded = tokenizer(
                text,
                truncation=True,
                max_length=max_length,
                padding="max_length",
                return_tensors="pt",
            )
            self.encodings.append({
                "input_ids": encoded["input_ids"].squeeze(),
                "attention_mask": encoded["attention_mask"].squeeze(),
                "labels": encoded["input_ids"].squeeze().clone(),
            })
    
    def __len__(self):
        return len(self.encodings)
    
    def __getitem__(self, idx):
        return self.encodings[idx]


def run_finetuning(args):
    """Execute the fine-tuning pipeline."""
    import torch
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        Trainer,
        DataCollatorForLanguageModeling,
    )
    from peft import LoraConfig, get_peft_model, TaskType, PeftModel
    
    device = "cuda" if torch.cuda.is_available() and not args.force_cpu else "cpu"
    logger.info(f"Using device: {device}")
    
    if device == "cpu":
        logger.warning(
            "Training on CPU. This will be SLOW. For the smoke test, expect ~5-15 minutes. "
            "Full training may take hours. Consider using a GPU for production training."
        )
    
    # Load tokenizer
    logger.info(f"Loading tokenizer from: {args.model_id}")
    model_path = args.model_path if args.model_path and Path(args.model_path).exists() else args.model_id
    
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        local_files_only=args.offline,
    )
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # Load model
    logger.info(f"Loading model from: {model_path}")
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype=torch.float32,  # CPU requires float32
        device_map=None,
        local_files_only=args.offline,
    )
    model.to(device)
    
    # Configure LoRA
    logger.info(f"Configuring LoRA: rank={args.lora_rank}, alpha={args.lora_alpha}")
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none",
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Prepare dataset
    logger.info("Preparing training data...")
    examples = load_dataset(args.dataset)
    
    if args.smoke_test:
        examples = examples[:3]
        logger.info(f"Smoke test mode: using only {len(examples)} examples")
    
    texts = [format_training_example(ex, tokenizer) for ex in examples]
    
    train_dataset = TrainingDataset(texts, tokenizer, args.max_seq_len)
    logger.info(f"Prepared {len(train_dataset)} training examples")
    
    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )
    
    # Training arguments
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    num_epochs = 1 if args.smoke_test else args.epochs
    max_steps = 5 if args.smoke_test else -1
    
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=num_epochs,
        max_steps=max_steps,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum_steps,
        learning_rate=args.learning_rate,
        weight_decay=0.01,
        warmup_steps=2 if args.smoke_test else max(1, len(train_dataset) // 10),
        logging_steps=1,
        save_steps=args.save_steps,
        save_total_limit=3,
        fp16=False,  # CPU doesn't support fp16
        bf16=False,
        report_to="none",  # No external logging
        dataloader_pin_memory=False,  # CPU training
        no_cuda=args.force_cpu,
        seed=42,
        logging_dir=str(output_dir / "logs"),
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
    )
    
    # Train
    logger.info("Starting training...")
    start_time = time.time()
    
    try:
        train_result = trainer.train(resume_from_checkpoint=args.resume_from)
        elapsed = time.time() - start_time
        
        logger.info(f"Training completed in {elapsed:.1f}s")
        logger.info(f"Training loss: {train_result.training_loss:.4f}")
        
        # Save the LoRA adapter
        adapter_path = output_dir / "adapter"
        model.save_pretrained(str(adapter_path))
        tokenizer.save_pretrained(str(adapter_path))
        
        logger.info(f"LoRA adapter saved to: {adapter_path}")
        
        # Save training info
        info = {
            "base_model": args.model_id,
            "lora_rank": args.lora_rank,
            "lora_alpha": args.lora_alpha,
            "training_loss": train_result.training_loss,
            "epochs": num_epochs,
            "max_steps": max_steps,
            "dataset": args.dataset,
            "examples": len(train_dataset),
            "elapsed_seconds": elapsed,
            "device": device,
            "smoke_test": args.smoke_test,
        }
        
        info_path = output_dir / "training_info.json"
        with open(info_path, "w") as f:
            json.dump(info, f, indent=2)
        
        logger.info(f"Training info saved to: {info_path}")
        logger.info("")
        logger.info("=" * 60)
        logger.info("To use this adapter, set these in your .env file:")
        logger.info(f"  LORA_ADAPTER_PATH={adapter_path}")
        logger.info(f"  LORA_ENABLED=true")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.warning("Training interrupted by user")
        logger.info("Saving checkpoint...")
        trainer.save_model(str(output_dir / "checkpoint-interrupted"))
        logger.info(f"Checkpoint saved to: {output_dir / 'checkpoint-interrupted'}")
    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune a language model with LoRA for SemesTrack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Smoke test (few steps, verify everything works)
  python scripts/finetune_lora.py --dataset training/data/train.jsonl --smoke-test

  # Full training with defaults
  python scripts/finetune_lora.py --dataset training/data/train.jsonl

  # Custom configuration
  python scripts/finetune_lora.py \\
    --dataset training/data/train.jsonl \\
    --model-id Qwen/Qwen3.5-0.8B \\
    --model-path ./models/llm \\
    --output-dir training/output \\
    --lora-rank 16 \\
    --epochs 5

  # Resume from checkpoint
  python scripts/finetune_lora.py \\
    --dataset training/data/train.jsonl \\
    --resume-from training/output/checkpoint-100

CPU Training Expectations:
  - Smoke test (3 examples, 5 steps): ~5-15 minutes
  - Small dataset (50 examples, 3 epochs): ~1-4 hours
  - Medium dataset (200 examples, 3 epochs): ~4-12 hours
  These estimates are for a modern CPU. Actual times depend on hardware.
        """,
    )
    
    # Model args
    parser.add_argument("--model-id", default="Qwen/Qwen3.5-0.8B",
                        help="Model ID (HuggingFace hub or local path)")
    parser.add_argument("--model-path", default="./models/llm",
                        help="Local model path (used if it exists)")
    parser.add_argument("--dataset", required=True,
                        help="Path to JSONL training dataset")
    parser.add_argument("--output-dir", default="./training/output",
                        help="Output directory for adapter and logs")
    
    # LoRA args
    parser.add_argument("--lora-rank", type=int, default=8,
                        help="LoRA rank (lower = fewer parameters)")
    parser.add_argument("--lora-alpha", type=int, default=16,
                        help="LoRA alpha (scaling factor)")
    parser.add_argument("--lora-dropout", type=float, default=0.05,
                        help="LoRA dropout rate")
    
    # Training args
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=1,
                        help="Per-device batch size")
    parser.add_argument("--grad-accum-steps", type=int, default=4,
                        help="Gradient accumulation steps")
    parser.add_argument("--learning-rate", type=float, default=2e-4,
                        help="Learning rate")
    parser.add_argument("--max-seq-len", type=int, default=512,
                        help="Maximum sequence length")
    parser.add_argument("--save-steps", type=int, default=50,
                        help="Save checkpoint every N steps")
    
    # Modes
    parser.add_argument("--smoke-test", action="store_true",
                        help="Run minimal training (3 examples, 5 steps) to verify setup")
    parser.add_argument("--force-cpu", action="store_true", default=True,
                        help="Force CPU training (default: True)")
    parser.add_argument("--offline", action="store_true", default=False,
                        help="Use only local files (no downloads)")
    parser.add_argument("--resume-from", default=None,
                        help="Resume from checkpoint directory")
    
    args = parser.parse_args()
    
    logger.info("SemesTrack LoRA Fine-tuning")
    logger.info("=" * 40)
    logger.info(f"Model:       {args.model_id}")
    logger.info(f"Dataset:     {args.dataset}")
    logger.info(f"Output:      {args.output_dir}")
    logger.info(f"LoRA rank:   {args.lora_rank}")
    logger.info(f"Epochs:      {args.epochs}")
    logger.info(f"Batch size:  {args.batch_size}")
    logger.info(f"Smoke test:  {args.smoke_test}")
    logger.info(f"Force CPU:   {args.force_cpu}")
    logger.info(f"Offline:     {args.offline}")
    logger.info("")
    
    check_dependencies()
    run_finetuning(args)


if __name__ == "__main__":
    main()
