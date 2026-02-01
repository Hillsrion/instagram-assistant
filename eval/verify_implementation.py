"""
Verification script for provider implementation.
Tests that per-model JSON files are created correctly.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from eval.llm_provider import create_provider


def test_per_model_json_generation():
    """Test that generate_per_model_json creates proper JSON files."""
    print("Testing per-model JSON generation...")

    # Import the function
    from eval.eval_generation import generate_per_model_json

    # Create mock data
    model = "qwen3:latest"
    model_results = {
        "trials": [
            {
                "answer": "Test answer",
                "time": 1.5,
                "words_per_sec": 10.0,
                "faith": {"score": 0.8, "explanation": "Good faithfulness"},
                "relev": {"score": 0.9, "explanation": "Good relevance"}
            }
        ],
        "avg_speed": 10.0
    }
    qa_pairs = [
        {
            "question": "Test question?",
            "expected_answer": "Expected answer",
            "source_chunk_ids": ["chunk_1"]
        }
    ]

    # Generate JSON
    try:
        json_path = generate_per_model_json(
            model=model,
            model_results=model_results,
            qa_pairs=qa_pairs,
            judge_model="qwen3:latest",
            provider="ollama",
            trials=1
        )

        print(f"  ✅ JSON file created: {json_path}")

        # Verify file exists and has correct structure
        with open(json_path, 'r') as f:
            data = json.load(f)

        assert "metadata" in data, "Missing metadata"
        assert "summary" in data, "Missing summary"
        assert "trials" in data, "Missing trials"
        assert "qa_pairs" in data, "Missing qa_pairs"

        assert data["metadata"]["model"] == model, "Wrong model in metadata"
        assert data["metadata"]["provider"] == "ollama", "Wrong provider in metadata"
        assert data["summary"]["avg_faithfulness"] == 0.8, "Wrong faithfulness"
        assert data["summary"]["avg_relevance"] == 0.9, "Wrong relevance"

        print(f"  ✅ JSON structure verified")
        print(f"  ✅ Metadata: {data['metadata']}")
        print(f"  ✅ Summary: {data['summary']}")

        # Clean up test file
        json_path.unlink()
        print(f"  ✅ Test file cleaned up")

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_provider_instantiation():
    """Test that providers can be instantiated for metrics."""
    print("\nTesting provider instantiation in metrics...")

    from eval.metrics import RAGASMetrics
    config = Config()

    try:
        # Test Ollama provider
        metrics_ollama = RAGASMetrics(config, provider_type="ollama")
        assert metrics_ollama.provider_type == "ollama"
        print("  ✅ Ollama metrics created successfully")

        # Test MLX provider
        metrics_mlx = RAGASMetrics(config, provider_type="mlx")
        assert metrics_mlx.provider_type == "mlx"
        print("  ✅ MLX metrics created successfully")

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli_arguments():
    """Test that CLI accepts provider argument."""
    print("\nTesting CLI argument parsing...")

    import subprocess

    try:
        # Test eval_generation help
        result = subprocess.run(
            ["python3", "-m", "eval.eval_generation", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if "--provider" in result.stdout and "{ollama,mlx}" in result.stdout:
            print("  ✅ eval_generation accepts --provider flag")
        else:
            print("  ❌ eval_generation missing --provider flag")
            return False

        # Test evaluate_summaries help
        result = subprocess.run(
            ["python3", "-m", "eval.evaluate_summaries", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if "--provider" in result.stdout and "{ollama,mlx}" in result.stdout:
            print("  ✅ evaluate_summaries accepts --provider flag")
        else:
            print("  ❌ evaluate_summaries missing --provider flag")
            return False

        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Provider Implementation Verification")
    print("=" * 60)
    print()

    results = []
    results.append(("Per-model JSON generation", test_per_model_json_generation()))
    results.append(("Provider instantiation", test_provider_instantiation()))
    results.append(("CLI argument parsing", test_cli_arguments()))

    print("\n" + "=" * 60)
    print("Verification Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")

    all_passed = all(r[1] for r in results)
    print()
    if all_passed:
        print("✅ All verification tests passed!")
        print("\nYou can now use the provider system:")
        print("  python -m eval.eval_generation --provider ollama model1 model2")
        print("  python -m eval.eval_generation --provider mlx model1 model2")
        print("  python -m eval.evaluate_summaries --provider mlx")
    else:
        print("❌ Some verification tests failed")
        sys.exit(1)
