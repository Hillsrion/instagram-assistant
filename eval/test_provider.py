"""
Quick test script to verify LLM provider abstraction works.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from eval.llm_provider import create_provider, OllamaProvider, MLXProviderWrapper


def test_ollama_provider():
    """Test Ollama provider creation and basic functionality."""
    print("Testing Ollama provider...")
    config = Config()

    try:
        provider = create_provider(config, "qwen3:latest", "ollama")
        assert isinstance(provider, OllamaProvider), "Should create OllamaProvider"
        print("  ✅ Ollama provider created successfully")

        # Test a simple generation (only if Ollama is running)
        try:
            response = provider.generate(
                [{"role": "user", "content": "Say 'test successful' and nothing else."}],
                temperature=0.1,
                max_tokens=10,
                timeout=30
            )
            print(f"  ✅ Generated response: {response[:50]}")
        except Exception as e:
            print(f"  ⚠️  Ollama not available: {e}")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

    return True


def test_mlx_provider():
    """Test MLX provider creation."""
    print("\nTesting MLX provider...")
    config = Config()

    try:
        # Note: This will only work if MLX model is available
        provider = create_provider(config, "mlx-community/Ministral-3-8B-Instruct-2512-4bit", "mlx")
        assert isinstance(provider, MLXProviderWrapper), "Should create MLXProviderWrapper"
        print("  ✅ MLX provider created successfully")

        # Don't test generation as MLX models may not be available
        print("  ℹ️  Skipping generation test (MLX model may not be downloaded)")

    except Exception as e:
        print(f"  ⚠️  MLX provider test skipped: {e}")
        return False

    return True


def test_provider_interface():
    """Test that both providers have the same interface."""
    print("\nTesting provider interface consistency...")
    config = Config()

    try:
        ollama = create_provider(config, "qwen3:latest", "ollama")
        mlx = create_provider(config, "mlx-community/test", "mlx")

        # Both should have generate method
        assert hasattr(ollama, "generate"), "OllamaProvider missing generate method"
        assert hasattr(mlx, "generate"), "MLXProvider missing generate method"

        print("  ✅ Both providers have consistent interface")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Provider Tests")
    print("=" * 60)
    print()

    results = []
    results.append(("Ollama Provider", test_ollama_provider()))
    results.append(("MLX Provider", test_mlx_provider()))
    results.append(("Interface Consistency", test_provider_interface()))

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")

    all_passed = all(r[1] for r in results)
    print()
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("⚠️  Some tests failed or were skipped")
