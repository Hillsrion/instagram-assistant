from rag_pipeline.core.models import Chunk
"""
Unit tests for ChunkComplexityAnalyzer.
"""
import pytest
from rag_pipeline.enrichment.complexity_analyzer import ChunkComplexityAnalyzer, ComplexityAnalysis
from rag_pipeline.core.config import Config


@pytest.fixture
def analyzer():
    """Create a complexity analyzer instance."""
    return ChunkComplexityAnalyzer()


@pytest.fixture
def simple_chunk():
    """Create a simple chunk (2 participants, 10 messages, short messages)."""
    content = ""
    for i in range(5):
        content += f"[2024-01-01 10:0{i}] Alice: Hi\n"
        content += f"[2024-01-01 10:0{i+5}] Bob: Hey\n"
    
    return Chunk(
        chunk_id="test_simple_1",
        conversation_id="conv_1",
        participants=["Alice", "Bob"],
        date_start="2024-01-01",
        date_end="2024-01-02",
        message_count=10,
        content=content,
        file_source="test.json"
    )


@pytest.fixture
def medium_chunk():
    """Create a medium complexity chunk."""
    content = ""
    participants = ["Alice", "Bob", "Charlie"]
    for i in range(25):
        author = participants[i % 3]
        content += f"[2024-01-01 10:{i:02d}] {author}: Hello how are you doing today with what you have been up to? \n"
    
    return Chunk(
        chunk_id="test_medium_1",
        conversation_id="conv_2",
        participants=participants,
        date_start="2024-01-01",
        date_end="2024-01-03",
        message_count=25,
        content=content,
        file_source="test.json"
    )


@pytest.fixture
def complex_chunk():
    """Create a complex chunk (5+ participants, 40+ messages, longer messages)."""
    long_msg = (
        "This is a very long message with lots of information about the topic at hand. "
        "We need to discuss the implications and consequences. What do you think? "
        "Have you considered all the angles? Tell me more about your perspective. "
        "I really want to understand your viewpoint on this complex subject. "
    )
    content = ""
    participants = ["Alice", "Bob", "Charlie", "David", "Eve"]
    for i in range(45):
        author = participants[i % 5]
        content += f"[2024-01-01 10:{i:02d}] {author}: {long_msg}\n"

    return Chunk(
        chunk_id="test_complex_1",
        conversation_id="conv_3",
        participants=participants,
        date_start="2024-01-01",
        date_end="2024-01-05",
        message_count=45,
        content=content,
        file_source="test.json"
    )


class TestParticipantsScoring:
    """Test participant count scoring."""

    def test_two_participants_is_baseline(self, analyzer, simple_chunk):
        analysis = analyzer.analyze(simple_chunk)
        # DM baseline is 0.3
        assert analysis.metrics.participants == 0.3

    def test_three_participants_is_medium(self, analyzer, medium_chunk):
        analysis = analyzer.analyze(medium_chunk)
        assert analysis.metrics.participants == 0.6

    def test_five_participants_is_complex(self, analyzer, complex_chunk):
        analysis = analyzer.analyze(complex_chunk)
        assert analysis.metrics.participants == 1.0


class TestInformationContentScoring:
    """Test information content scoring."""

    def test_sparse_content_is_simple(self, analyzer):
        chunk = Chunk(
            chunk_id="sparse",
            conversation_id="conv",
            participants=["A", "B"],
            date_start="2024-01-01",
            date_end="2024-01-02",
            message_count=10,
            content="[2024-01-01] A: Hi\n[2024-01-01] B: Hey\n" * 10,
            file_source="test.json"
        )
        analysis = analyzer.analyze(chunk)
        assert analysis.metrics.information_content == 0.0

    def test_rich_content_is_complex(self, analyzer):
        # Create a message with many unique words
        unique_words = [f"word{i}" for i in range(200)]
        chunk = Chunk(
            chunk_id="rich",
            conversation_id="conv",
            participants=["A", "B"],
            date_start="2024-01-01",
            date_end="2024-01-02",
            message_count=1,
            content="[2024-01-01] A: " + " ".join(unique_words),
            file_source="test.json"
        )
        analysis = analyzer.analyze(chunk)
        assert analysis.metrics.information_content == 1.0


class TestMediaScoring:
    """Test media/link ratio scoring."""

    def test_no_media_is_simple(self, analyzer, simple_chunk):
        analysis = analyzer.analyze(simple_chunk)
        assert analysis.metrics.media == 0.0

    def test_media_heavy_is_complex(self, analyzer):
        chunk = Chunk(
            chunk_id="media_heavy",
            conversation_id="conv",
            participants=["A", "B"],
            date_start="2024-01-01",
            date_end="2024-01-02",
            message_count=10,
            content="[2024-01-01] A: [Photo] Check this https://example.com photo.jpg video.mp4\n" * 10,
            file_source="test.json"
        )
        analysis = analyzer.analyze(chunk)
        assert analysis.metrics.media == 1.0


class TestSizeScoring:
    """Test chunk size (message count) scoring."""

    def test_small_chunk_is_simple(self, analyzer):
        chunk = Chunk(
            chunk_id="small",
            conversation_id="conv",
            participants=["A", "B"],
            date_start="2024-01-01",
            date_end="2024-01-02",
            message_count=10,
            content="msg\n" * 10,
            file_source="test.json"
        )
        analysis = analyzer.analyze(chunk)
        assert analysis.metrics.size == 0.0

    def test_large_chunk_is_complex(self, analyzer):
        chunk = Chunk(
            chunk_id="large",
            conversation_id="conv",
            participants=["A", "B"],
            date_start="2024-01-01",
            date_end="2024-01-02",
            message_count=40,
            content="msg\n" * 40,
            file_source="test.json"
        )
        analysis = analyzer.analyze(chunk)
        assert analysis.metrics.size == 1.0


class TestDialogueScoring:
    """Test dialogue pattern scoring."""

    def test_no_dialogue_markers_is_simple(self, analyzer, simple_chunk):
        analysis = analyzer.analyze(simple_chunk)
        assert analysis.metrics.dialogue == 0.0

    def test_emotional_dialogue_is_complex(self, analyzer):
        chunk = Chunk(
            chunk_id="emotional",
            conversation_id="conv",
            participants=["A", "B"],
            date_start="2024-01-01",
            date_end="2024-01-02",
            message_count=10,
            content="[2024-01-01] A: Really?! What?? Why!!! Amazing!!! 😊🚀\n" * 10,
            file_source="test.json"
        )
        analysis = analyzer.analyze(chunk)
        assert analysis.metrics.dialogue == 1.0


class TestComplexityScoring:
    """Test overall complexity score calculation."""

    def test_score_range(self, analyzer, simple_chunk, medium_chunk, complex_chunk):
        """All scores should be between 0.0 and 1.0."""
        for chunk in [simple_chunk, medium_chunk, complex_chunk]:
            analysis = analyzer.analyze(chunk)
            assert 0.0 <= analysis.score <= 1.0

    def test_simple_chunk_low_score(self, analyzer, simple_chunk):
        """Simple chunks should have low scores."""
        analysis = analyzer.analyze(simple_chunk)
        assert analysis.score < 0.25

    def test_complex_chunk_high_score(self, analyzer, complex_chunk):
        """Complex chunks should have high scores."""
        analysis = analyzer.analyze(complex_chunk)
        assert analysis.score > 0.40


class TestClassification:
    """Test category classification."""

    def test_simple_classification(self, analyzer, simple_chunk):
        analysis = analyzer.analyze(simple_chunk)
        assert analysis.category == "simple"

    def test_complex_classification(self, analyzer, complex_chunk):
        analysis = analyzer.analyze(complex_chunk)
        assert analysis.category in ["medium", "complex"]


class TestBreakdown:
    """Test metrics breakdown."""

    def test_breakdown_contains_all_metrics(self, analyzer, simple_chunk):
        analysis = analyzer.analyze(simple_chunk)
        assert "participants" in analysis.breakdown
        assert "information_content" in analysis.breakdown
        assert "media" in analysis.breakdown
        assert "size" in analysis.breakdown
        assert "dialogue" in analysis.breakdown

    def test_breakdown_values_match_metrics(self, analyzer, simple_chunk):
        analysis = analyzer.analyze(simple_chunk)
        assert analysis.breakdown["participants"] == analysis.metrics.participants
        assert analysis.breakdown["information_content"] == analysis.metrics.information_content
