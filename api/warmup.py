"""
AI Model Warmup
"""
import asyncio
from typing import Set

from rag_pipeline.core.config import Config
from rag_pipeline.core.llm_provider import create_provider
from rag_pipeline.core.logger import get_logger

logger = get_logger()


async def warmup_models(config: Config):
    """
    Sends a dummy request to configured models to load them into memory.
    Runs silently in the background during application startup.
    """
    models_to_warmup: Set[str] = set()
    
    # Add configured models based on strategy
    if config.llm_model:
        models_to_warmup.add(config.llm_model)
        
    if config.llm_model_fast:
        models_to_warmup.add(config.llm_model_fast)

    if config.model_loading_strategy == "dual":
        if config.llm_light_model:
            models_to_warmup.add(config.llm_light_model)

    # Remove duplicates or empty strings
    models_to_warmup = {m for m in models_to_warmup if m}

    if not models_to_warmup:
        return

    logger.info(f"🔥 Starting background warmup for models: {', '.join(models_to_warmup)}")
    
    async def warmup_single(model: str):
        try:
            logger.info(f"⏳ Warming up {model}...")
            # Using ollama as it's the default backend provider for chat
            provider = create_provider(config, model, provider_type="ollama")
            
            messages = [{"role": "user", "content": "Wake up."}]
            
            # Run generate in a thread to prevent blocking the async event loop
            await asyncio.to_thread(provider.generate, messages, max_tokens=1, temperature=0.1)
            logger.info(f"✅ Model {model} is warmed up.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to warmup model {model}: {e}")

    # Start warmups concurrently
    await asyncio.gather(*(warmup_single(model) for model in models_to_warmup))
