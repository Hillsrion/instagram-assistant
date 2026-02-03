# Phase 1+ Implementation Plan

**Status:** Ready to execute (pending Phase 0 GO decision)

**Duration:** 3-4 working sessions
**Complexity:** Medium (core infrastructure change)
**Risk Level:** Low (fully testable before production use)

## Overview

This document details the implementation roadmap for Phases 1-4 of the complexity-based model routing system. **Do not start Phase 1 until Phase 0 validation is complete and recommends GO.**

## Phase 1: ChunkComplexityAnalyzer

### Objective
Implement core complexity analysis module that computes 6 metrics and produces a score (0.0-1.0) for routing decisions.

### Files to Create

#### 1. `rag_pipeline/complexity_analyzer.py` (~300 lines)

```python
class ChunkComplexityAnalyzer:
    """Analyzes chunk complexity to determine optimal LLM model."""

    def __init__(self, config: Config = None):
        self.config = config or default_config
        # Load weights from config
        self.weights = config.complexity_weights

    def analyze(self, chunk: Chunk) -> ComplexityAnalysis:
        """
        Analyze chunk complexity.

        Returns:
            ComplexityAnalysis with score, category, and metric breakdown
        """
        metrics = self._compute_metrics(chunk)
        score = self._calculate_score(metrics)
        category = self._classify(score)

        return ComplexityAnalysis(
            score=score,
            category=category,
            metrics=metrics,
            debug_info={...}
        )
```

**Key Methods:**

| Method | Lines | Purpose |
|--------|-------|---------|
| `__init__` | 5 | Initialize with config |
| `analyze` | 20 | Main entry point |
| `_compute_metrics` | 80 | Calculate 6 metrics |
| `_calculate_score` | 15 | Weighted sum |
| `_classify` | 10 | Simple/Medium/Complex |
| `_score_participants` | 10 | Metric 1 |
| `_score_density` | 10 | Metric 2 |
| `_score_media` | 10 | Metric 3 |
| `_score_size` | 10 | Metric 4 |
| `_score_lexical_diversity` | 15 | Metric 5 (complex) |
| `_score_dialogue_patterns` | 10 | Metric 6 |

**Data Structures:**

```python
@dataclass
class ComplexityMetrics:
    """Raw complexity metrics."""
    participants: int
    message_count: int
    tokens_per_message: float
    media_density: float
    lexical_diversity: float
    dialogue_markers_per_message: float

@dataclass
class ComplexityAnalysis:
    """Result of complexity analysis."""
    score: float  # 0.0-1.0
    category: str  # "simple", "medium", "complex"
    metrics: ComplexityMetrics
    debug_info: Dict[str, float]  # Per-metric scores for debugging
```

**Testing:**

```python
def test_complexity_analyzer():
    analyzer = ChunkComplexityAnalyzer()

    # Test simple chunk
    simple = create_test_chunk(participants=2, messages=10, tokens=15)
    result = analyzer.analyze(simple)
    assert result.category == "simple"
    assert result.score < 0.35

    # Test complex chunk
    complex = create_test_chunk(participants=4, messages=40, tokens=120)
    result = analyzer.analyze(complex)
    assert result.category == "complex"
    assert result.score >= 0.65
```

### Files to Modify

#### 1. `rag_pipeline/config.py` (~40 lines added)

**Add to Config dataclass:**

```python
@dataclass
class Config:
    # ... existing fields ...

    # === Complexity-Based Routing ===
    # Light model for simple chunks
    llm_light_model: str = field(
        default_factory=lambda: os.getenv('LLM_LIGHT_MODEL', 'ministral-3:3b')
    )

    # Strategy for loading models
    model_loading_strategy: str = field(
        default_factory=lambda: os.getenv('MODEL_LOADING_STRATEGY', 'dual')
    )
    # Options: "dual" (pre-load both), "on-demand" (load/unload), "batch" (group by complexity)

    # RAM threshold for dual-load strategy
    min_ram_gb_for_dual: float = 10.0

    # Complexity classification thresholds
    complexity_simple_threshold: float = 0.35
    complexity_complex_threshold: float = 0.65

    # Behavior for medium chunks
    complexity_medium_uses_light: bool = True  # Use 3B for medium if True

    # Weights for complexity metrics (must sum to 1.0)
    complexity_weights: dict = field(default_factory=lambda: {
        "participants": 0.20,
        "density": 0.25,
        "media": 0.15,
        "size": 0.15,
        "lexical": 0.15,
        "dialogue": 0.10
    })

    # Enable/disable routing (for testing)
    enable_complexity_routing: bool = True

    # Override to force specific model (for debugging)
    force_model: Optional[str] = None
```

**Add to environment variables (.env example):**

```
# Complexity routing
LLM_LIGHT_MODEL=ministral-3:3b
MODEL_LOADING_STRATEGY=dual
COMPLEXITY_SIMPLE_THRESHOLD=0.35
COMPLEXITY_COMPLEX_THRESHOLD=0.65
COMPLEXITY_MEDIUM_USES_LIGHT=true
ENABLE_COMPLEXITY_ROUTING=true
```

## Phase 2: Integration into ChunkEnricher

### Objective
Modify enricher to analyze complexity and route to appropriate model.

### Files to Modify

#### 1. `rag_pipeline/enricher.py` (~100 lines added/modified)

**Key additions:**

```python
from .complexity_analyzer import ChunkComplexityAnalyzer

class ChunkEnricher:
    def __init__(self, config: Config = None, provider: str = "ollama",
                 model_loading_strategy: str = "dual"):
        # ... existing init ...

        # Initialize complexity analyzer
        self.complexity_analyzer = ChunkComplexityAnalyzer(config)

        # Model management
        self.light_model = config.llm_light_model
        self.strong_model = config.llm_model
        self.current_loaded_model = None
        self.model_loading_strategy = model_loading_strategy or config.model_loading_strategy

        # Pre-load models if dual strategy
        if self.model_loading_strategy == "dual":
            self._preload_models()

        # Routing statistics
        self.routing_stats = {
            "simple": 0,
            "medium": 0,
            "complex": 0,
            "model_switches": 0,
            "total_load_time_ms": 0
        }

    def _preload_models(self):
        """Pre-load both models into memory (dual-load strategy)."""
        print(f"⚠️ Pre-loading models (RAM: ~8GB)...")
        start = time.time()

        # Warm-up call to force model loading
        try:
            self._call_ollama("test", model=self.light_model)
            self._call_ollama("test", model=self.strong_model)
            elapsed = (time.time() - start) * 1000
            self.routing_stats["total_load_time_ms"] = elapsed
            print(f"✅ Models pre-loaded in {elapsed:.0f}ms")
        except Exception as e:
            print(f"⚠️ Pre-load failed: {e}")
            # Continue anyway - will load on-demand

    def _ensure_model_loaded(self, model_name: str):
        """Load model if needed (on-demand strategy)."""
        if self.model_loading_strategy == "dual":
            return  # Already loaded

        if self.current_loaded_model != model_name:
            start = time.time()
            print(f"🔄 Loading {model_name}...")
            self._call_ollama("test", model=model_name)  # Warm-up
            elapsed = (time.time() - start) * 1000
            self.routing_stats["model_switches"] += 1
            self.routing_stats["total_load_time_ms"] += elapsed
            self.current_loaded_model = model_name
            print(f"✅ Loaded in {elapsed:.0f}ms")

    def _select_model_for_chunk(self, chunk: Chunk) -> str:
        """
        Determine which model to use for chunk.

        Returns:
            Model name (e.g., "ministral-3:3b" or "ministral-3:8b")
        """
        # Force override
        if self.config.force_model:
            return self.config.force_model

        # Routing disabled
        if not self.config.enable_complexity_routing:
            return self.config.llm_model  # Always use strong model

        # Analyze complexity
        analysis = self.complexity_analyzer.analyze(chunk)
        score = analysis.score
        category = analysis.category

        # Route based on category
        if category == "simple":
            self.routing_stats["simple"] += 1
            return self.light_model
        elif category == "complex":
            self.routing_stats["complex"] += 1
            return self.strong_model
        else:  # medium
            self.routing_stats["medium"] += 1
            if self.config.complexity_medium_uses_light:
                return self.light_model
            else:
                return self.strong_model

    def enrich_chunk(self, chunk: Chunk) -> Tuple[...]:
        """
        Enrich chunk with complexity-aware model selection.

        (Replaces existing implementation)
        """
        # Select model based on complexity
        selected_model = self._select_model_for_chunk(chunk)

        # Ensure model is loaded
        self._ensure_model_loaded(selected_model)

        # Original enrichment logic (using selected_model)
        # ... existing code ...

        # Update model used
        self.model = selected_model

        # Call LLM
        try:
            result = self._call_ollama(prompt, model=selected_model)
            # ... parsing logic ...
        except Exception as e:
            # Fallback to strong model on error
            print(f"⚠️ Error with {selected_model}: {e}")
            if selected_model != self.strong_model:
                print(f"   Retrying with {self.strong_model}...")
                result = self._call_ollama(prompt, model=self.strong_model)
            else:
                raise
```

**Modify `enrich_batch` to display statistics:**

```python
def enrich_batch(self, chunks: List[Chunk], ...) -> List[Chunk]:
    """
    (Existing implementation with added logging)
    """
    # ... existing batch processing ...

    # At the end, print statistics
    if hasattr(self, 'routing_stats'):
        print(f"""
📊 Routing Statistics:
  Simple chunks:   {self.routing_stats['simple']}
  Medium chunks:   {self.routing_stats['medium']}
  Complex chunks:  {self.routing_stats['complex']}
  Model switches:  {self.routing_stats['model_switches']}
""")
```

## Phase 3: Logging and Metrics

### Objective
Track routing decisions for analysis and optimization.

### Files to Create

#### 1. `rag_pipeline/enrichment_log.py` (~200 lines)

```python
import csv
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

@dataclass
class EnrichmentLogEntry:
    """Single enrichment decision log."""
    chunk_id: str
    complexity_score: float
    complexity_category: str
    selected_model: str
    enrichment_time_ms: float
    message_count: int
    participant_count: int
    timestamp: str

class EnrichmentLogger:
    """Logs enrichment decisions for analysis."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.entries: List[EnrichmentLogEntry] = []
        self._load_existing()

    def log_decision(self, entry: EnrichmentLogEntry):
        """Log a single enrichment decision."""
        self.entries.append(entry)

    def save(self):
        """Save logs to CSV."""
        if not self.entries:
            return

        with open(self.log_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[...])
            writer.writeheader()
            for entry in self.entries:
                writer.writerow(asdict(entry))

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics."""
        # Count by category and model
        # Calculate average times
        # Return breakdown
```

**Integration into enricher:**

```python
# In ChunkEnricher.enrich_chunk()
if hasattr(self, 'logger'):
    self.logger.log_decision(EnrichmentLogEntry(
        chunk_id=chunk.chunk_id,
        complexity_score=analysis.score,
        complexity_category=analysis.category,
        selected_model=selected_model,
        enrichment_time_ms=elapsed_time,
        message_count=chunk.message_count,
        participant_count=len(chunk.participants),
        timestamp=datetime.now().isoformat()
    ))

# In setup_rag.py
enricher.logger.save()
print(enricher.logger.get_stats())
```

## Phase 4: Testing and Calibration

### Objective
Verify routing works correctly and calibrate thresholds if needed.

### Files to Create

#### 1. `tests/test_complexity_analyzer.py` (~150 lines)

```python
import pytest
from rag_pipeline.complexity_analyzer import ChunkComplexityAnalyzer
from rag_pipeline.chunker import Chunk

class TestComplexityAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return ChunkComplexityAnalyzer()

    def test_simple_chunk(self, analyzer):
        """Test classification of simple chunk."""
        chunk = Chunk(...)  # 2 participants, 10 messages
        result = analyzer.analyze(chunk)
        assert result.category == "simple"

    def test_complex_chunk(self, analyzer):
        """Test classification of complex chunk."""
        chunk = Chunk(...)  # 5 participants, 40 messages
        result = analyzer.analyze(chunk)
        assert result.category == "complex"

    def test_score_range(self, analyzer):
        """Test that scores are always 0.0-1.0."""
        for _ in range(100):
            chunk = create_random_chunk()
            result = analyzer.analyze(chunk)
            assert 0.0 <= result.score <= 1.0

    def test_metric_weights(self, analyzer):
        """Test that weights sum to 1.0."""
        weights = analyzer.weights
        assert abs(sum(weights.values()) - 1.0) < 0.01
```

#### 2. `scripts/test_routing_integration.py` (~200 lines)

```python
#!/usr/bin/env python3
"""
Test complexity routing on small batch of chunks.
"""

def test_routing_on_sample(sample_size=100):
    """
    Test enrichment with routing on small sample.
    """
    # Load sample chunks
    # Enable complexity routing
    # Enrich batch
    # Verify:
    #   - All chunks enriched successfully
    #   - Distribution of simple/medium/complex is reasonable
    #   - Model switching works (if on-demand)
    #   - Output quality acceptable
```

### Testing Checklist

- [ ] Unit tests pass: `pytest tests/test_complexity_analyzer.py`
- [ ] Integration test passes: `python scripts/test_routing_integration.py --sample 100`
- [ ] Routing statistics printed correctly
- [ ] On-demand loading works (if enabled)
- [ ] Dual-load strategy works (if enabled)
- [ ] Model selection matches expected categories
- [ ] Logging captures all decisions
- [ ] Quality check: Sample enrichments reviewed

## Implementation Sequence

### Session 1: Phase 1 (ChunkComplexityAnalyzer)
- Create `complexity_analyzer.py` (~300 lines)
- Add config parameters
- Write unit tests
- **Deliverable:** `ChunkComplexityAnalyzer` working standalone

### Session 2: Phase 2 (Integration)
- Modify `enricher.py` (~100 lines)
- Add routing logic
- Test with mock models
- **Deliverable:** Enricher with complexity routing, tested on 10 chunks

### Session 3: Phase 3+4 (Logging and Testing)
- Create `enrichment_log.py`
- Add logging to enricher
- Create integration test
- Test on 100-500 chunk sample
- **Deliverable:** Full system tested, ready for production

### Session 4: Production Deployment (Optional)
- Run full indexing: `python setup_rag.py`
- Monitor logs and statistics
- Verify quality on sample
- Document results

## Fallback Plan

If issues arise during implementation:

1. **Routing selects wrong model?**
   - Adjust `complexity_simple_threshold` and `complexity_complex_threshold`
   - Re-run calibration on 100-chunk sample

2. **Quality degradation?**
   - Classify more chunks as "complex"
   - Increase thresholds (e.g., 0.40 instead of 0.35)

3. **Memory issues?**
   - Switch to "on-demand" strategy
   - Accept 15s per model switch overhead

4. **Performance not meeting expectations?**
   - Verify actual distribution matches assumptions
   - May need to optimize for actual dataset skew

## Success Criteria

**Phase 1 Complete When:**
- ✅ `ChunkComplexityAnalyzer` class implemented
- ✅ All 6 metrics computed correctly
- ✅ Unit tests passing
- ✅ Config parameters added

**Phase 2 Complete When:**
- ✅ Enricher integrates complexity analyzer
- ✅ Model routing works
- ✅ Loading strategies (dual/on-demand) implemented
- ✅ Statistics tracked

**Phase 3 Complete When:**
- ✅ Logging system captures decisions
- ✅ CSV export working
- ✅ Integration tests pass

**Phase 4 Complete When:**
- ✅ 100-500 chunk sample enriched successfully
- ✅ Quality verified on sample
- ✅ Statistics show expected distribution
- ✅ Ready for production use

## Estimated Effort

| Phase | Estimate | Notes |
|-------|----------|-------|
| 1 | 1-2 hours | Core analyzer, straightforward |
| 2 | 1-2 hours | Integration, need model handling care |
| 3 | 1 hour | Logging infrastructure |
| 4 | 1-2 hours | Testing, debugging, calibration |
| **Total** | **4-7 hours** | Spread across 2-3 sessions |

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Routing chooses wrong model | Validate metrics against sample labels |
| Quality degradation | Keep 8B for complex chunks, careful thresholds |
| Memory issues | Support on-demand and batch strategies |
| Model loading fails | Graceful fallback to strong model |
| Logging overhead | Async/batch logging if performance critical |

## Code Quality Standards

- All methods documented with docstrings
- Type hints on all functions
- Config parameters with defaults
- Error handling with graceful fallbacks
- Logging at key decision points
- Unit tests with >80% coverage

---

**Next:** Return to Phase 0 validation. Proceed with Phase 1 only after GO decision confirmed.
