#!/usr/bin/env python3
"""
Unified script for validating and comparing enrichment quality across models.

Usage:
    # 1. Evaluate specific models on a dataset (A/B testing)
    python -m eval.enrichment.validate_enrichment --models ministral-3:3b,ministral-3:8b --dataset eval/generation/complexity_eval_dataset.json --html

    # 2. Validate current index chunks (random sample)
    python -m eval.enrichment.validate_enrichment --sample --size 20 --model ministral-3:8b

    # 3. Validate specific chunk file
    python -m eval.enrichment.validate_enrichment --dataset path/to/chunks.json --html
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config, default_config
from rag_pipeline.chunker import Chunk, ConversationChunker
from rag_pipeline.enricher import ChunkEnricher
from eval.enrichment.eval_enrichment import (
    EnrichmentValidator,
    EnrichmentBenchmarkReport,
    print_benchmark_report,
    ChunkEnrichmentValidationReport
)
from eval.core._output_paths import get_enrichment_report_path

def load_dataset_chunks(path: Path) -> List[Dict]:
    """Load chunks from a JSON dataset."""
    if not path.exists():
        print(f"❌ Dataset not found at {path}")
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_chunk_from_dict(data: Dict) -> Chunk:
    """Creates a Chunk object from a dictionary, handling missing fields."""
    data_copy = data.copy()
    # Add dummy fields required by Chunk dataclass if missing
    if 'date_start' not in data_copy:
        data_copy['date_start'] = "2023-01-01 00:00:00"
    if 'date_end' not in data_copy:
        data_copy['date_end'] = "2023-01-01 00:00:00"
    if 'file_source' not in data_copy:
        data_copy['file_source'] = "dataset.txt"
    if 'participants' not in data_copy:
         data_copy['participants'] = []
    
    return Chunk.from_dict(data_copy)

def load_chunks_from_index(config: Config, limit: int = None) -> List[Chunk]:
    """Load chunks from the pickled chunk index."""
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    if limit and len(chunks) > limit:
        # Take random sample or just last N? 
        # Using last N is often better for checking recent work, 
        # but random is better for general validation.
        # Let's use latest for now as it's often more relevant.
        chunks = chunks[-limit:] 
    return chunks

def enrich_chunk_with_model(chunk: Chunk, model: str, config: Config) -> float:
    """
    Enrich a single chunk using a specific model.
    In-place modification of chunk.
    Returns time taken in seconds.
    """
    # Create specific config for this model to avoid auto-routing overriding it
    run_config = Config()
    # crucial: disable routing to force specific model
    run_config.enable_complexity_routing = False 
    run_config.force_model = model
    
    enricher = ChunkEnricher(config=run_config)
    
    start_time = time.time()
    try:
        # Capture return values explicitly!
        res = enricher.enrich_chunk(chunk)
        (summary, questions, intents, temporal, entities, emotions, pattern, initiative, shift, loops) = res
        
        chunk.narrative_summary = summary
        chunk.hypothetical_questions = questions
        chunk.speaker_intents = intents
        chunk.temporal_context = temporal
        chunk.entities = entities
        chunk.emotions = emotions
        chunk.interaction_pattern = pattern
        chunk.initiative = initiative
        chunk.emotional_shift = shift
        chunk.open_loops = loops
        
    except Exception as e:
        print(f"  ⚠️ Error enriching with {model}: {e}")
    
    return time.time() - start_time

def generate_comparative_html_report(
    results: List[Dict], 
    models: List[str]
) -> Path:
    """Generate a side-by-side HTML comparison report."""
    
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate grid columns based on number of models
    # If 1 model: max-w-3xl mx-auto
    # If 2 models: grid-cols-2
    # If 3+ models: grid-cols-X (might get squashed, but okay)
    grid_cols = f"grid-cols-1 lg:grid-cols-{len(models)}" if len(models) > 1 else "max-w-4xl mx-auto"
    
    html = f"""
<!DOCTYPE html>
<html lang="en" class="bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enrichment Comparison Report</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
        pre {{ font-family: 'JetBrains Mono', monospace; }}
    </style>
</head>
<body class="p-8 max-w-[95%] mx-auto">
    <div class="mb-10 text-center">
        <h1 class="text-3xl font-bold text-gray-900">🧠 Enrichment Model Comparison</h1>
        <p class="text-gray-600 mt-2">Comparing: {', '.join(models)}</p>
        <div class="mt-4 inline-flex items-center px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-sm font-medium">
            {timestamp_str}
        </div>
        <p class="mt-2 text-sm text-gray-500">{len(results)} chunks evaluated</p>
    </div>

    <div class="space-y-16">
"""
    
    for res in results:
        chunk_rec = res['original_chunk']
        model_results = res['model_results']
        
        # Color badge for score
        complexity_html = ""
        if 'complexity_score' in res:
             complexity_html = f"""
             <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 border border-gray-200 ml-2">
                Complexity: {res.get('category', 'unknown')} ({res['complexity_score']:.2f})
             </span>
             """

        html += f"""
        <!-- Chunk Block -->
        <div class="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
            <div class="bg-gray-50 px-6 py-4 border-b border-gray-200 flex justify-between items-center sticky top-0 z-10">
                <div>
                    <span class="font-mono text-sm font-bold text-gray-700">ID: {chunk_rec.chunk_id}</span>
                    {complexity_html}
                </div>
            </div>

            <div class="p-6">
                 <!-- Source Content (Collapsible ideally, but kept visible for now) -->
                <div class="mb-8">
                    <h3 class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Original Content</h3>
                    <div class="bg-slate-50 p-4 rounded-lg border border-slate-200 text-sm font-mono text-slate-700 whitespace-pre-wrap max-h-40 overflow-y-auto">{chunk_rec.content}</div>
                </div>

                <!-- Comparison Grid -->
                <div class="grid {grid_cols} gap-6">
        """
        
        for model in models:
            m_res = model_results.get(model)
            if not m_res:
                html += f"""<div class="border-2 border-dashed border-gray-200 rounded-lg p-10 text-center text-gray-400">No data for {model}</div>"""
                continue
                
            report = m_res['report']
            data = m_res['data']
            time_taken = m_res['time']
            
            score = report.overall_score
            score_color = "text-green-600" if score >= 0.8 else "text-orange-600" if score >= 0.5 else "text-red-600"
            border_color = "border-green-100" if score >= 0.8 else "border-orange-100" if score >= 0.5 else "border-red-100"
            
            html += f"""
                    <!-- Model Column: {model} -->
                    <div class="flex flex-col h-full bg-white border-2 {border_color} rounded-lg overflow-hidden relative transition-all hover:shadow-md">
                        <!-- Header -->
                        <div class="bg-gray-50/50 p-4 border-b border-gray-100">
                            <div class="flex justify-between items-start mb-2">
                                <h3 class="font-bold text-gray-900 truncate" title="{model}">{model}</h3>
                                <span class="text-xs font-mono bg-gray-200 text-gray-700 px-2 py-1 rounded">{time_taken:.2f}s</span>
                            </div>
                            <div class="flex items-baseline space-x-2">
                                <span class="text-2xl font-bold {score_color}">{score:.2f}</span>
                                <span class="text-xs text-gray-500 font-medium uppercase">Score</span>
                            </div>
                             {render_warnings_html(report.warnings_count, report.field_results)}
                        </div>
                        
                        <!-- Content -->
                        <div class="p-5 space-y-6 flex-grow text-sm">
                             {render_enrichment_data_html(data, report)}
                        </div>
                    </div>
            """
            
        html += """
                </div>
            </div>
        </div>
        """

    html += """
    </div>
</body>
</html>
    """
    
    # Use standardized path generator
    output_path = get_enrichment_report_path(models, timestamp=timestamp, format="html")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
        
    return output_path

def render_warnings_html(count, field_results):
    if count == 0:
        return ""
    
    warnings_list = ""
    for field, res in field_results.items():
        if res.warnings:
            for w in res.warnings:
                warnings_list += f"<li><span class='font-semibold'>{field}:</span> {w}</li>"
    
    return f"""
    <div class="mt-3 bg-orange-50 text-orange-800 text-xs p-2 rounded border border-orange-100">
        <div class="font-bold flex items-center mb-1">
             ⚡ {count} Warnings
        </div>
        <ul class="list-disc list-inside space-y-0.5 opacity-90">{warnings_list}</ul>
    </div>
    """

def render_enrichment_data_html(chunk, report):
    html = ""
    
    # Helper to check score and color
    def get_bg(field):
        res = report.field_results.get(field)
        if not res: return "bg-gray-50"
        return "bg-red-50 border-red-100" if res.score < 0.5 else "bg-gray-50 border-gray-100"

    # Narrative Summary
    html += f"""
    <div class="{get_bg('narrative_summary')} p-3 rounded border">
        <h4 class="text-xs font-bold text-gray-500 uppercase mb-1">Narrative Summary</h4>
        <p class="text-gray-800 leading-relaxed">{chunk.narrative_summary or '<span class="text-gray-400 italic">Empty</span>'}</p>
    </div>
    """

    # Intents
    html += f"""
    <div>
        <h4 class="text-xs font-bold text-gray-500 uppercase mb-2">Intentions</h4>
        {render_dict_list_html(chunk.speaker_intents)}
    </div>
    """

    # Entities
    html += f"""
    <div>
        <h4 class="text-xs font-bold text-gray-500 uppercase mb-2">Entities</h4>
        {render_entities_html(chunk.entities)}
    </div>
    """
    
    # Emotions
    html += f"""
    <div>
        <h4 class="text-xs font-bold text-gray-500 uppercase mb-2">Emotions</h4>
        {render_dict_list_html(chunk.emotions)}
    </div>
    """

    # Temporal & Questions
    html += f"""
    <div class="grid grid-cols-1 gap-4">
        <div>
            <h4 class="text-xs font-bold text-gray-500 uppercase mb-1">Temporal Context</h4>
            <p class="text-gray-700">{chunk.temporal_context or '-'}</p>
        </div>
        <div>
            <h4 class="text-xs font-bold text-gray-500 uppercase mb-2">Hypothetical Questions</h4>
            <ul class="list-disc list-inside text-gray-700 space-y-1">
                {''.join(f'<li>{q}</li>' for q in (chunk.hypothetical_questions or []))}
            </ul>
             { '<p class="text-gray-400 italic">None</p>' if not chunk.hypothetical_questions else ''}
        </div>
    </div>
    """
    
    return html

def render_dict_list_html(d):
    if not d:
        return '<p class="text-gray-400 italic">None</p>'
    return '<ul class="list-disc list-inside text-gray-700 space-y-1">' + \
           ''.join(f'<li><span class="font-semibold text-gray-600">{k}:</span> {v}</li>' for k, v in d.items()) + \
           '</ul>'

def render_entities_html(entities):
    if not entities:
        return '<p class="text-gray-400 italic">None</p>'
    
    html = '<div class="space-y-2">'
    has_items = False
    for cat, items in entities.items():
        if items:
            has_items = True
            html += f"""
            <div class="flex items-start">
                <span class="w-16 flex-shrink-0 text-gray-400 text-xs uppercase pt-1">{cat}</span>
                <div class="flex flex-wrap gap-1">
                    {''.join(f'<span class="px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded text-xs border border-blue-100">{item}</span>' for item in items)}
                </div>
            </div>
            """
    html += '</div>'
    return html if has_items else '<p class="text-gray-400 italic">Empty categories</p>'


def main():
    parser = argparse.ArgumentParser(
        description="Validate and compare enrichment quality across models.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dataset", type=str, help="Path to JSON dataset (for consistent A/B testing)")
    group.add_argument("--sample", action="store_true", help="Sample random chunks from the RAG index")
    
    parser.add_argument("--models", type=str, help="Comma-separated list of models to evaluate (e.g., 'ministral-3:3b,ministral-3:8b')")
    parser.add_argument("--size", "--samples", type=int, default=10, dest="size", help="Number of chunks to evaluate")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    
    args = parser.parse_args()
    
    config = Config()
    
    # 1. Load Data
    chunks = []
    if args.dataset:
        print(f"📂 Loading dataset from {args.dataset}...")
        raw_data = load_dataset_chunks(Path(args.dataset))
        # Support both list of dicts or {"chunks": [...]}
        if isinstance(raw_data, dict) and "chunks" in raw_data:
            raw_data = raw_data["chunks"]
        
        # Take samples
        sample_data = raw_data[:args.size]
        # Convert to chunks
        chunks = [create_chunk_from_dict(d) for d in sample_data]
        
    elif args.sample:
        print(f"🎲 Loading random sample from index (size={args.size})...")
        chunks = load_chunks_from_index(config, limit=args.size)
        
    if not chunks:
        print("❌ No chunks found.")
        return

    print(f"✅ Loaded {len(chunks)} chunks.")

    # 2. Determine Models
    models = []
    if args.models:
        models = [m.strip() for m in args.models.split(',') if m.strip()]
    else:
        # Default to configured models if not specified
        models = [config.llm_model]
        print(f"ℹ️  No models specified, using default: {models[0]}")

    print(f"🚀 Evaluating models: {', '.join(models)}")
    
    # 3. Evaluation Loop
    validator = EnrichmentValidator(config)
    results = []
    
    for i, original_chunk in enumerate(chunks):
        print(f"\n[{i+1}/{len(chunks)}] Processing chunk {original_chunk.chunk_id}")
        
        chunk_result = {
            "original_chunk": original_chunk,
            "complexity_score": getattr(original_chunk, 'complexity_score', 0) if hasattr(original_chunk, 'complexity_score') else 0, # might come from dataset metadata
            "model_results": {}
        }
        
        # Determine metadata if available (from dataset)
        # Note: Chunk object created from dictionary doesn't strictly preserve 'metadata' dict in attributes unless we hack it
        # But we can try to infer simple/medium/complex from length if missing
        
        for model in models:
            print(f"  🤖 Run {model}...", end="", flush=True)
            
            # Create a fresh copy to avoid polluting other model runs
            # We must manually copy because dataclass copy might not deep copy everything
            test_chunk = create_chunk_from_dict(original_chunk.to_dict())
            
            # Enrich
            time_taken = enrich_chunk_with_model(test_chunk, model, config)
            
            # Validate
            report = validator.validate_chunk(test_chunk)
            
            chunk_result["model_results"][model] = {
                "data": test_chunk,
                "report": report,
                "time": time_taken
            }
            
            print(f" Done ({time_taken:.2f}s) | Score: {report.overall_score:.2f}")
            
        results.append(chunk_result)

    # 4. Report
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    for model in models:
        avg_score = sum(r['model_results'][model]['report'].overall_score for r in results) / len(results)
        avg_time = sum(r['model_results'][model]['time'] for r in results) / len(results)
        print(f"Model: {model:<20} | Avg Score: {avg_score:.2f} | Avg Time: {avg_time:.2f}s")
        
    if args.html:
        report_path = generate_comparative_html_report(results, models)
        print(f"\n✅ HTML Report generated: {report_path}")
        print(f"👉 Open it: open {report_path}")

if __name__ == "__main__":
    main()
