#!/usr/bin/env python3
"""Download models for offline SemesTrack usage.

Downloads the LLM and embedding model to local directories so the
application can run without internet after initial setup.

This script requires an internet connection. After running it,
SemesTrack can operate fully offline.

Usage:
    python scripts/download_models.py
    python scripts/download_models.py --llm-only
    python scripts/download_models.py --embedding-only
    python scripts/download_models.py --model-id Qwen/Qwen2.5-0.5B
"""

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def download_llm(model_id: str, output_dir: str):
    """Download LLM model files for offline use."""
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        logger.error("transformers not installed. Run: pip install transformers")
        sys.exit(1)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Downloading LLM: {model_id}")
    logger.info(f"Destination: {output_path.resolve()}")
    logger.info("This may take several minutes depending on your connection...")
    
    try:
        logger.info("Downloading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        tokenizer.save_pretrained(str(output_path))
        
        logger.info("Downloading model weights...")
        import torch
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            trust_remote_code=True,
            torch_dtype=torch.float32,
            device_map=None,
        )
        model.save_pretrained(str(output_path))
        
        logger.info(f"LLM downloaded successfully to: {output_path.resolve()}")
        
        # Verify
        logger.info("Verifying download...")
        test_tokenizer = AutoTokenizer.from_pretrained(
            str(output_path), trust_remote_code=True, local_files_only=True
        )
        test_model = AutoModelForCausalLM.from_pretrained(
            str(output_path), trust_remote_code=True, local_files_only=True,
            torch_dtype=torch.float32,
        )
        
        # Quick test
        inputs = test_tokenizer("Hello", return_tensors="pt")
        outputs = test_model.generate(**inputs, max_new_tokens=5)
        logger.info("LLM verification: PASSED ✓")
        
        del model, test_model, test_tokenizer
        
    except Exception as e:
        logger.error(f"Failed to download LLM: {e}")
        logger.error("Check your internet connection and model ID.")
        raise


def download_embedding_model(model_id: str, output_dir: str):
    """Download embedding model for offline use."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
        sys.exit(1)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Downloading embedding model: {model_id}")
    logger.info(f"Destination: {output_path.resolve()}")
    
    try:
        model = SentenceTransformer(model_id)
        model.save(str(output_path))
        
        logger.info(f"Embedding model downloaded to: {output_path.resolve()}")
        
        # Verify
        logger.info("Verifying download...")
        test_model = SentenceTransformer(str(output_path))
        test_embedding = test_model.encode(["test sentence"])
        assert test_embedding.shape[1] > 0, "Embedding dimension is 0"
        logger.info(f"Embedding verification: PASSED ✓ (dim={test_embedding.shape[1]})")
        
        del model, test_model
        
    except Exception as e:
        logger.error(f"Failed to download embedding model: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Download models for offline SemesTrack usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script requires an internet connection. After running,
SemesTrack can operate fully offline.

Disk space requirements (approximate):
  - Qwen3.5-0.8B:                   ~1.6 GB
  - sentence-transformers/all-MiniLM-L6-v2:  ~80 MB
  - Total:                           ~1.7 GB

After download, set these in your .env file:
  LLM_MODEL_PATH=./models/llm
  EMBEDDING_MODEL_PATH=./models/embeddings
        """
    )
    
    parser.add_argument("--model-id", default="Qwen/Qwen3.5-0.8B",
                        help="LLM model ID from HuggingFace Hub")
    parser.add_argument("--llm-dir", default="./models/llm",
                        help="Directory to save LLM model")
    parser.add_argument("--embedding-id", default="sentence-transformers/all-MiniLM-L6-v2",
                        help="Embedding model ID")
    parser.add_argument("--embedding-dir", default="./models/embeddings",
                        help="Directory to save embedding model")
    parser.add_argument("--llm-only", action="store_true",
                        help="Download only the LLM")
    parser.add_argument("--embedding-only", action="store_true",
                        help="Download only the embedding model")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SemesTrack Model Downloader")
    logger.info("=" * 60)
    logger.info("")
    logger.info("⚠  This requires an internet connection.")
    logger.info("   After download, SemesTrack runs fully offline.")
    logger.info("")
    
    if not args.embedding_only:
        download_llm(args.model_id, args.llm_dir)
        logger.info("")
    
    if not args.llm_only:
        download_embedding_model(args.embedding_id, args.embedding_dir)
        logger.info("")
    
    logger.info("=" * 60)
    logger.info("All models downloaded successfully!")
    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Copy .env.example to .env")
    logger.info("  2. Update LLM_MODEL_PATH and EMBEDDING_MODEL_PATH in .env")
    logger.info("  3. Start the application: python -m uvicorn backend.app.main:app")
    logger.info("  4. You can now disconnect from the internet")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
