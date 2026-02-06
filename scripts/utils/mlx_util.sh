#!/usr/bin/env bash

# MLX Model Utility Script
# Manage MLX models from Hugging Face: list, pull, run, remove

set -euo pipefail

MLX_CACHE_DIR="${HF_HOME:-$HOME/.cache/huggingface/hub}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPT_NAME="$(basename "$0")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_error() {
    echo -e "${RED}Error:${NC} $1" >&2
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_info() {
    echo -e "${BLUE}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

check_mlx_installed() {
    if ! python3 -c "import mlx_lm" 2>/dev/null; then
        print_error "mlx-lm not installed"
        print_info "Install with: pip install mlx-lm"
        exit 1
    fi
}

get_model_cache_path() {
    local model_name="$1"
    # Convert model name to cache directory format
    # e.g., mlx-community/Ministral-3-8B-Instruct-2512-4bit -> models--mlx-community--Ministral-3-8B-Instruct-2512-4bit
    local cache_name=$(echo "$model_name" | sed 's/\//__/g' | sed 's/^/models--/')
    echo "${MLX_CACHE_DIR}/${cache_name}"
}

# Command: list
cmd_list() {
    print_info "Cached MLX models:"
    echo
    
    if [ ! -d "$MLX_CACHE_DIR" ]; then
        print_warning "No cache directory found at: $MLX_CACHE_DIR"
        return
    fi
    
    # Find all model directories
    local found_models=false
    
    printf "%-50s %10s\n" "MODEL" "SIZE"
    printf "%s\n" "$(printf '%.0s-' {1..65})"
    
    for model_dir in "$MLX_CACHE_DIR"/models--*; do
        if [ -d "$model_dir" ]; then
            found_models=true
            local model_name=$(basename "$model_dir" | sed 's/^models--//' | sed 's/__/\//g')
            local size=$(du -sh "$model_dir" 2>/dev/null | cut -f1)
            printf "%-50s %10s\n" "$model_name" "$size"
        fi
    done
    
    if [ "$found_models" = false ]; then
        print_warning "No models found in cache"
    fi
}

# Command: pull
cmd_pull() {
    if [ $# -eq 0 ]; then
        print_error "Model name required"
        echo "Usage: $SCRIPT_NAME pull <model_name>"
        echo "Example: $SCRIPT_NAME pull mlx-community/Ministral-3-8B-Instruct-2512-4bit"
        exit 1
    fi
    
    local model_name="$1"
    check_mlx_installed
    
    print_info "Downloading MLX model: ${model_name}"
    echo
    
    # Use huggingface-cli to download the model
    if command -v huggingface-cli &> /dev/null; then
        huggingface-cli download "$model_name" --local-dir-use-symlinks False
    else
        # Fallback: use Python to download
        python3 << EOF
from huggingface_hub import snapshot_download
import sys

try:
    print(f"Downloading ${model_name}...")
    snapshot_download(
        repo_id="${model_name}",
        local_files_only=False,
    )
    print("Download complete!")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Successfully downloaded ${model_name}"
    else
        print_error "Failed to download ${model_name}"
        exit 1
    fi
}

# Command: run
cmd_run() {
    if [ $# -eq 0 ]; then
        print_error "Model name required"
        echo "Usage: $SCRIPT_NAME run <model_name> [prompt]"
        echo "Example: $SCRIPT_NAME run mlx-community/Ministral-3-8B-Instruct-2512-4bit \"Hello!\""
        exit 1
    fi
    
    local model_name="$1"
    shift
    
    check_mlx_installed
    
    if [ $# -eq 0 ]; then
        # Interactive mode
        print_info "Running ${model_name} in interactive mode"
        print_info "Type your messages (Ctrl+D to exit)"
        echo
        
        python3 << EOF
import sys
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

try:
    print("Loading model...", file=sys.stderr)
    model, tokenizer = load("${model_name}")
    print("Model loaded!\n", file=sys.stderr)
    
    sampler = make_sampler(temp=0.7)
    
    while True:
        try:
            prompt = input(">>> ")
            if not prompt.strip():
                continue
            
            print()
            response = generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=2048,
                verbose=False,
                sampler=sampler
            )
            print(response)
            print()
        except EOFError:
            break
        except KeyboardInterrupt:
            print("\n")
            break
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
    else
        # Single prompt mode
        local prompt="$*"
        print_info "Running ${model_name}"
        echo
        
        python3 << EOF
import sys
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

try:
    print("Loading model...", file=sys.stderr)
    model, tokenizer = load("${model_name}")
    
    sampler = make_sampler(temp=0.7)
    
    response = generate(
        model,
        tokenizer,
        prompt="${prompt}",
        max_tokens=2048,
        verbose=False,
        sampler=sampler
    )
    print(response)
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
    fi
}

# Command: remove
cmd_remove() {
    if [ $# -eq 0 ]; then
        print_error "Model name required"
        echo "Usage: $SCRIPT_NAME remove <model_name>"
        exit 1
    fi
    
    local model_name="$1"
    local cache_path=$(get_model_cache_path "$model_name")
    
    if [ ! -d "$cache_path" ]; then
        print_error "Model not found: ${model_name}"
        print_info "Cache path: ${cache_path}"
        exit 1
    fi
    
    print_warning "Removing model: ${model_name}"
    print_info "Path: ${cache_path}"
    
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$cache_path"
        print_success "Successfully removed ${model_name}"
    else
        print_info "Cancelled"
    fi
}

# Show help
show_help() {
    cat << EOF
MLX Model Utility - Manage MLX models from Hugging Face

Usage: $SCRIPT_NAME <command> [arguments]

Commands:
    list                List cached MLX models
    pull <model>        Download a model from Hugging Face
    run <model> [text]  Run a model (interactive or with prompt)
    remove <model>      Remove a cached model
    help                Show this help message

Environment Variables:
    HF_HOME            Hugging Face cache directory (default: ~/.cache/huggingface)

Examples:
    $SCRIPT_NAME list
    $SCRIPT_NAME pull mlx-community/Ministral-3-8B-Instruct-2512-4bit
    $SCRIPT_NAME run mlx-community/Ministral-3-8B-Instruct-2512-4bit
    $SCRIPT_NAME run mlx-community/Ministral-3-8B-Instruct-2512-4bit "Explain quantum computing"
    $SCRIPT_NAME remove mlx-community/Ministral-3-8B-Instruct-2512-4bit

Popular MLX Models:
    mlx-community/Ministral-3-8B-Instruct-2512-4bit
    mlx-community/Qwen2.5-7B-Instruct-4bit
    mlx-community/Llama-3.2-3B-Instruct-4bit
    mlx-community/Phi-3-mini-4k-instruct-4bit

Note: Models are cached in $MLX_CACHE_DIR

EOF
}

# Main command dispatcher
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 1
    fi
    
    local command="$1"
    shift
    
    case "$command" in
        list|ls)
            cmd_list "$@"
            ;;
        pull|download)
            cmd_pull "$@"
            ;;
        run)
            cmd_run "$@"
            ;;
        remove|rm)
            cmd_remove "$@"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo
            show_help
            exit 1
            ;;
    esac
}

main "$@"
