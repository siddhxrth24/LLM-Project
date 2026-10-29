# SemesTrack — Implementation Plan

## Environment Assessment
- **Python:** 3.13.3 (will use uv to create a 3.12 venv for ML compatibility)
- **Node.js:** 22.19.0 / npm 10.9.3
- **Git:** 2.51.0
- **OS:** Windows
- **GPU:** None (CPU-only)

## Design Decisions

### Model Selection
- **LLM:** `Qwen/Qwen3.5-0.8B` — small enough for CPU inference, chat-template support via transformers
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` — 80MB, fast on CPU, 384-dim embeddings
- **Fallback:** If Qwen3.5-0.8B has compatibility issues, fall back to `Qwen/Qwen2.5-0.5B` or `TinyLlama/TinyLlama-1.1B-Chat-v1.0`

### Python Version
- Use Python 3.12 via uv for maximum ML library compatibility (PyTorch, transformers, PEFT all test against 3.12)

### Key Architecture Choices
- SQLAlchemy 2.0 async with aiosqlite for non-blocking DB
- ChromaDB with persistent local storage for vector search
- SQLite FTS5 for keyword search alongside dense retrieval
- Hybrid ranking via Reciprocal Rank Fusion (RRF)
- Deterministic scheduling via topological sort (no LLM-generated calendars)
- PEFT/LoRA for fine-tuning with CPU-safe defaults

## Milestones

### M1: Project Scaffolding & Configuration
- [x] Create directory structure
- [x] Backend: pyproject.toml, FastAPI app skeleton, SQLAlchemy models, config
- [x] Frontend: Vite + React + TypeScript + Tailwind + shadcn/ui setup
- [x] .env.example, .gitignore

### M2: Database & Core API
- [ ] SQLAlchemy models: Course, Unit, Document, Chunk, Topic, StudySession
- [ ] Database initialization / migration
- [ ] CRUD API endpoints for courses, units, documents
- [ ] Pydantic schemas for all entities

### M3: Document Ingestion Pipeline
- [ ] PDF extraction (PyMuPDF) with page-level metadata
- [ ] PPTX extraction (python-pptx) with slide-level metadata
- [ ] Optional OCR (Tesseract) for scanned pages
- [ ] Text chunking with overlap, respecting model input limits
- [ ] ChromaDB embedding storage with metadata
- [ ] SQLite FTS5 indexing
- [ ] Incremental indexing, re-upload, deletion support

### M4: RAG & Hybrid Retrieval
- [ ] Dense retrieval via ChromaDB
- [ ] Keyword retrieval via FTS5
- [ ] Reciprocal Rank Fusion combining both
- [ ] Course/unit-scoped filtering
- [ ] Citation preservation (page/slide references)

### M5: Syllabus Analysis & Coverage
- [ ] Syllabus parsing into structured units/topics/subtopics
- [ ] LLM-assisted topic extraction with Pydantic validation
- [ ] Coverage classification: Covered, Partially Covered, Not Found, Needs Review
- [ ] Evidence-based matching with confidence scores
- [ ] User correction support

### M6: Deterministic Scheduling
- [ ] Directed graph of topics with prerequisites
- [ ] Topological sort with cycle detection
- [ ] Time allocation based on difficulty, duration, available hours
- [ ] Examination deadline respect, revision buffers
- [ ] Schedule recalculation on input changes
- [ ] Constraint conflict reporting

### M7: Teaching Assistant
- [ ] Topic content generation with RAG grounding
- [ ] Structured lesson format (definition, explanation, examples, etc.)
- [ ] Source attribution vs. supplemental content distinction
- [ ] Output validation and retry logic

### M8: Frontend Implementation
- [ ] Dashboard page
- [ ] Course setup page
- [ ] Unit uploads page with file management
- [ ] Coverage analysis page
- [ ] Study timeline page
- [ ] Topic learning page
- [ ] Settings page
- [ ] All pages connected to backend API

### M9: LoRA Fine-tuning Pipeline
- [ ] Training data format and sample dataset
- [ ] Dataset validation script
- [ ] Fine-tuning script with CPU-safe defaults
- [ ] Adapter loading integration in backend
- [ ] Settings UI for fine-tuning controls

### M10: Offline Setup & Testing
- [ ] Model download script
- [ ] Offline-only runtime configuration
- [ ] Unit tests for core pipelines
- [ ] Integration tests for API
- [ ] Frontend build verification
- [ ] README with complete setup instructions
