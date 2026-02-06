#!/bin/bash
# Starts the VLLM Audio Server (Voxtral)

# Configuration
MODEL="mistralai/Voxtral-Mini-4B-Realtime-2602"
PORT=8001
GPU_UTILIZATION=0.9
MAX_MODEL_LEN=8192  # Adjust based on your GPU memory

echo "🚀 Starting Voxtral Audio Server on port $PORT..."
echo "Model: $MODEL"

# Check if vllm is installed
if ! command -v vllm &> /dev/null; then
    echo "❌ Error: vllm is not installed. Run 'pip install vllm'"
    exit 1
fi

# Run VLLM
# --trust-remote-code might be needed for some new models, check model card.
# Voxtral is Mistral, usually standard architecture but safe to trust if needed.
# --dtype auto uses bfloat16 if available
vllm serve $MODEL \
    --port $PORT \
    --dtype auto \
    --gpu-memory-utilization $GPU_UTILIZATION \
    --max-model-len $MAX_MODEL_LEN \
    --trust-remote-code

# Note: If you have multiple GPUs, add --tensor-parallel-size N
