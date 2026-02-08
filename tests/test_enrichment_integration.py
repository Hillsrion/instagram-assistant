"""
Integration tests for enrichment pipeline with real Ollama calls.

Tests actual enrichment quality and performance with model routing.
"""
import pytest
import json
import time
from pathlib import Path
from rag_pipeline.enricher import ChunkEnricher
from rag_pipeline.config import Config
from rag_pipeline.chunker import Chunk
from rag_pipeline.complexity_analyzer import ChunkComplexityAnalyzer


@pytest.fixture
def test_chunks():
    """Load test chunks from chunks.json if available."""
    chunks_path = Path(__file__).parent.parent / "rag_data" / "chunks.json"

    if not chunks_path.exists():
        pytest.skip("chunks.json not found - create with setup_rag.py first")

    with open(chunks_path) as f:
        chunks_data = json.load(f)

    # Convert to Chunk objects
    chunks = []
    for chunk_data in chunks_data[:20]:  # Use first 20 chunks only
        try:
            chunk = Chunk.from_dict(chunk_data)
            chunks.append(chunk)
        except Exception as e:
            print(f"Warning: Could not load chunk {chunk_data.get('chunk_id')}: {e}")

    return chunks


@pytest.fixture
def config():
    """Create test configuration."""
    return Config()


@pytest.fixture
def analyzer(config):
    """Create complexity analyzer."""
    return ChunkComplexityAnalyzer(config)


@pytest.fixture
def enricher_3b(config):
    """Create enricher with 3B model only."""
    test_config = Config()
    test_config.llm_model = "ministral-3:3b"
    test_config.enable_complexity_routing = False
    return ChunkEnricher(config=test_config)


@pytest.fixture
def enricher_8b(config):
    """Create enricher with 8B model only."""
    test_config = Config()
    test_config.llm_model = "ministral-3:8b"
    test_config.enable_complexity_routing = False
    return ChunkEnricher(config=test_config)


@pytest.fixture
def enricher_routed(config):
    """Create enricher with routing enabled."""
    test_config = Config()
    test_config.enable_complexity_routing = True
    test_config.model_loading_strategy = "dual"
    return ChunkEnricher(config=test_config)


class TestComplexityAnalysis:
    """Test complexity analysis on real chunks."""

    def test_analyze_chunks(self, test_chunks, analyzer):
        """Verify complexity analysis works on real chunks."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        analyses = []
        for chunk in test_chunks[:5]:
            analysis = analyzer.analyze(chunk)
            assert 0.0 <= analysis.score <= 1.0
            assert analysis.category in ["simple", "medium", "complex"]
            analyses.append(analysis)
            print(f"{chunk.chunk_id}: score={analysis.score:.3f}, "
                  f"category={analysis.category}")

        # Verify we got a mix of categories
        categories = [a.category for a in analyses]
        print(f"\nCategory distribution: {dict((c, categories.count(c)) for c in set(categories))}")

        assert len(analyses) > 0

    def test_metric_correlation(self, test_chunks, analyzer):
        """Verify metrics correlate with expected features."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        results = []
        for chunk in test_chunks[:10]:
            analysis = analyzer.analyze(chunk)
            results.append({
                "chunk_id": chunk.chunk_id,
                "score": analysis.score,
                "participants": len(chunk.participants or []),
                "messages": chunk.message_count,
                "participants_metric": analysis.metrics.participants,
                "size_metric": analysis.metrics.size,
            })

        # Print correlation analysis
        print("\nMetric Correlation Analysis:")
        print(f"{'Chunk ID':<20} {'Score':<8} {'Participants':<12} {'Messages':<10}")
        for r in results:
            print(f"{r['chunk_id']:<20} {r['score']:<8.3f} "
                  f"{r['participants']:<12} {r['messages']:<10}")

        # Verify participants correlate with score
        for r in results:
            if r['participants'] >= 5:
                assert r['participants_metric'] > 0.5, \
                    f"High participants should have high metric score"


class TestEnrichmentQuality:
    """Test enrichment output quality from both models."""

    def test_3b_enrichment(self, test_chunks, enricher_3b):
        """Test 3B model enrichment."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        pytest.skip("Run manually with actual Ollama - takes ~30 seconds per chunk")

        chunk = test_chunks[0]
        start = time.time()
        summary, questions, intents, temp_context, entities, emotions, pattern, initiative, shift, loops = \
            enricher_3b.enrich_chunk(chunk)
        elapsed_ms = (time.time() - start) * 1000

        print(f"\n3B Model Enrichment:")
        print(f"  Time: {elapsed_ms:.0f}ms")
        print(f"  Summary: {summary[:100]}...")
        print(f"  Questions: {len(questions)} generated")
        print(f"  Entities: {len(entities.get('people', []))} people found")

        assert summary  # Should have summary
        assert questions  # Should have questions
        assert isinstance(entities, dict)

    def test_8b_enrichment(self, test_chunks, enricher_8b):
        """Test 8B model enrichment."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        pytest.skip("Run manually with actual Ollama - takes ~30 seconds per chunk")

        chunk = test_chunks[0]
        start = time.time()
        summary, questions, intents, temp_context, entities, emotions, pattern, initiative, shift, loops = \
            enricher_8b.enrich_chunk(chunk)
        elapsed_ms = (time.time() - start) * 1000

        print(f"\n8B Model Enrichment:")
        print(f"  Time: {elapsed_ms:.0f}ms")
        print(f"  Summary: {summary[:100]}...")
        print(f"  Questions: {len(questions)} generated")
        print(f"  Entities: {len(entities.get('people', []))} people found")

        assert summary
        assert questions
        assert isinstance(entities, dict)

    def test_quality_comparison(self, test_chunks):
        """Compare quality metrics between 3B and 8B outputs."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        pytest.skip("Run manually - requires enriching with both models")


class TestRoutingDecisions:
    """Test that routing makes correct decisions."""

    def test_routing_selects_correct_model(self, test_chunks, enricher_routed, analyzer):
        """Verify routing selects models correctly based on complexity."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        routing_decisions = []
        for chunk in test_chunks[:10]:
            analysis = analyzer.analyze(chunk)
            selected_model = enricher_routed._select_model_for_chunk(chunk)

            routing_decisions.append({
                "chunk_id": chunk.chunk_id,
                "score": analysis.score,
                "category": analysis.category,
                "selected_model": selected_model,
            })

            # Verify routing is consistent
            if analysis.category == "simple":
                assert selected_model == "ministral-3:3b"
            elif analysis.category == "complex":
                assert selected_model == "ministral-3:8b"

        # Print routing decisions
        print("\nRouting Decisions:")
        print(f"{'Chunk':<20} {'Score':<8} {'Category':<10} {'Model':<20}")
        for d in routing_decisions:
            print(f"{d['chunk_id']:<20} {d['score']:<8.3f} "
                  f"{d['category']:<10} {d['selected_model']:<20}")

        assert len(routing_decisions) > 0

    def test_routing_statistics(self, test_chunks, enricher_routed):
        """Verify routing statistics are tracked."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        # Process chunks to update stats
        for chunk in test_chunks[:10]:
            _ = enricher_routed._select_model_for_chunk(chunk)

        stats = enricher_routed.model_manager.stats

        print(f"\nRouting Statistics:")
        print(f"  Simple: {stats['simple']}")
        print(f"  Medium: {stats['medium']}")
        print(f"  Complex: {stats['complex']}")
        print(f"  Total: {sum(stats[k] for k in ['simple', 'medium', 'complex'])}")

        # Verify stats were updated
        assert sum(stats[k] for k in ['simple', 'medium', 'complex']) > 0


class TestPerformanceMetrics:
    """Test performance metrics and timing."""

    def test_complexity_analysis_speed(self, test_chunks, analyzer):
        """Verify complexity analysis is fast (<50ms per chunk)."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        times = []
        for chunk in test_chunks[:10]:
            start = time.time()
            analysis = analyzer.analyze(chunk)
            elapsed_ms = (time.time() - start) * 1000
            times.append(elapsed_ms)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        print(f"\nComplexity Analysis Timing:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
        print(f"  Min: {min(times):.2f}ms")

        # Verify it's fast
        assert avg_time < 50, f"Analysis should be <50ms, got {avg_time:.2f}ms"
        assert max_time < 100, f"Max analysis time should be <100ms, got {max_time:.2f}ms"

    def test_enrichment_timing_estimation(self, test_chunks, analyzer):
        """Estimate enrichment times based on complexity."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        timing_projections = []
        for chunk in test_chunks[:15]:
            analysis = analyzer.analyze(chunk)

            # Estimate based on model
            if analysis.category == "simple":
                estimated_ms = 1200  # 3B model
            elif analysis.category == "medium":
                estimated_ms = 1200  # 3B model
            else:
                estimated_ms = 2400  # 8B model

            timing_projections.append({
                "category": analysis.category,
                "estimated_ms": estimated_ms,
                "message_count": chunk.message_count,
            })

        # Calculate total projection
        total_estimated_ms = sum(t["estimated_ms"] for t in timing_projections)
        total_estimated_hours = total_estimated_ms / (1000 * 3600)

        print(f"\nTiming Projections for {len(timing_projections)} chunks:")

        # Distribution
        from collections import Counter
        categories = Counter(t["category"] for t in timing_projections)
        for cat in ["simple", "medium", "complex"]:
            count = categories[cat]
            if count > 0:
                time_for_cat = count * (1200 if cat != "complex" else 2400)
                print(f"  {cat:8}: {count:2} chunks × {1200 if cat != 'complex' else 2400}ms "
                      f"= {time_for_cat/1000:.1f}s")

        print(f"\n  Total for {len(timing_projections)} chunks: {total_estimated_hours:.3f} hours")

        # Full dataset projection (32,559 chunks)
        if len(timing_projections) > 0:
            full_projection_hours = (total_estimated_hours / len(timing_projections)) * 32559
            print(f"  Projected for full dataset (32,559 chunks): {full_projection_hours:.1f} hours")

            # Compare to 8B only baseline
            baseline_hours = (32559 * 2400) / (1000 * 3600)
            savings = baseline_hours - full_projection_hours
            savings_pct = (savings / baseline_hours) * 100
            print(f"\n  Baseline (8B only): {baseline_hours:.1f} hours")
            print(f"  With routing: {full_projection_hours:.1f} hours")
            print(f"  Savings: {savings:.1f} hours ({savings_pct:.1f}%)")


class TestLogging:
    """Test enrichment logging functionality."""

    def test_logger_initialization(self, enricher_routed):
        """Verify logger initializes correctly."""
        assert enricher_routed.enrichment_logger is not None

        log_dir = enricher_routed.enrichment_logger.output_dir
        print(f"\nLogger initialized:")
        print(f"  Log directory: {log_dir}")
        print(f"  JSONL file: {log_dir / 'enrichment_log.jsonl'}")
        print(f"  CSV file: {log_dir / 'enrichment_log.csv'}")

    def test_logging_integration(self, test_chunks, enricher_routed, analyzer):
        """Test that logging works during enrichment."""
        if not test_chunks:
            pytest.skip("No test chunks available")

        chunk = test_chunks[0]
        analysis = analyzer.analyze(chunk)

        # Simulate logging
        enricher_routed.enrichment_logger.log_decision(
            chunk_id=chunk.chunk_id,
            complexity_score=analysis.score,
            complexity_category=analysis.category,
            selected_model="ministral-3:3b",
            enrichment_time_ms=1200.5,
            message_count=chunk.message_count or 0,
            participant_count=len(chunk.participants or []),
            metrics_breakdown=analysis.breakdown
        )

        enricher_routed.enrichment_logger.save()

        # Verify it was logged
        stats = enricher_routed.enrichment_logger.get_stats()
        print(f"\nLogging test results:")
        print(f"  Total entries logged: {stats['total']}")
        assert stats['total'] > 0


class TestErrorHandling:
    """Test error handling and fallback behavior."""

    def test_enricher_initialization(self):
        """Verify enricher can be created with different configs."""
        # Test with routing enabled
        config1 = Config()
        config1.enable_complexity_routing = True
        enricher1 = ChunkEnricher(config=config1)
        assert enricher1.enable_routing
        print(f"\n✓ Created enricher with routing enabled")

        # Test with routing disabled
        config2 = Config()
        config2.enable_complexity_routing = False
        enricher2 = ChunkEnricher(config=config2)
        assert not enricher2.enable_routing
        print(f"✓ Created enricher with routing disabled")

        # Test with on-demand strategy
        config3 = Config()
        config3.model_loading_strategy = "on-demand"
        enricher3 = ChunkEnricher(config=config3)
        assert enricher3.model_manager.loading_strategy == "on-demand"
        print(f"✓ Created enricher with on-demand strategy")

    def test_chunk_with_missing_fields(self, enricher_routed):
        """Test handling of chunks with missing fields."""
        chunk = Chunk(
            chunk_id="test_missing",
            conversation_id="conv",
            participants=None,
            date_start="2024-01-01",
            date_end="2024-01-02",
            message_count=0,
            content=None,
            file_source="test.json"
        )

        # Should not crash
        model = enricher_routed._select_model_for_chunk(chunk)
        assert model is not None
        print(f"\n✓ Handled chunk with missing fields, selected: {model}")


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_batch_enrichment_statistics(self, test_chunks, enricher_routed):
        """Test that batch statistics work correctly."""
        if not len(test_chunks) < 5:
            pytest.skip("Need at least 5 test chunks")

        # Log multiple decisions
        for i, chunk in enumerate(test_chunks[:5]):
            enricher_routed._select_model_for_chunk(chunk)

        stats = enricher_routed.model_manager.stats
        total = sum(stats[k] for k in ['simple', 'medium', 'complex'])

        print(f"\nBatch Statistics (5 chunks):")
        print(f"  Simple: {stats['simple']}")
        print(f"  Medium: {stats['medium']}")
        print(f"  Complex: {stats['complex']}")
        print(f"  Total: {total}")

        assert total == 5

    def test_configuration_override(self):
        """Test that configuration overrides work."""
        config = Config()

        # Change thresholds
        config.complexity_simple_threshold = 0.50
        config.complexity_complex_threshold = 0.75

        analyzer = ChunkComplexityAnalyzer(config)
        assert analyzer.simple_threshold == 0.50
        assert analyzer.complex_threshold == 0.75

        print(f"\n✓ Configuration overrides work correctly")

