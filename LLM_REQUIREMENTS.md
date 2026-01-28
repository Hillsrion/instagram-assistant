# LLM Requirements for Chat Modes

The "Auto" and "Mode" selection features in the Instagram Assistant rely on having specific Ollama models available.
Please ensure you have pulled the following models:

## Fast Mode (Speed)
Used for simple queries and quick interactions.
```bash
ollama pull qwen3:4b
```
*Alternative: `qwen2.5:3b` or `qwen2.5:0.5b` if you have very limited RAM.*

## Regular Mode (Balanced)
The default model for most interactions.
```bash
ollama pull qwen3:latest
```
*Note: `qwen3:latest` usually points to the 7B/8B parameter version.*

## Advanced Mode (Reasoning)
Used for complex reasoning, broad summaries, and deep analysis.
```bash
ollama pull qwen3:14b
```
*Alternative: `deepseek-r1:14b` or `qwen2.5:14b`.*

## Configuration
You can override the models used for each mode by setting environment variables in your `.env` file:

```env
FAST_LLM_MODEL=qwen3:4b
REGULAR_LLM_MODEL=qwen3:latest
ADVANCED_LLM_MODEL=qwen3:14b
```
