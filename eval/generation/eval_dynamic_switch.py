import time
import json
import copy
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add root to sys.path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import Chunk
from rag_pipeline.enricher import ChunkEnricher
from eval.core._output_paths import get_generation_report_path

def load_dataset_chunks(path: Path) -> List[Dict]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_chunk_from_dict(data: Dict) -> Chunk:
    """Creates a Chunk object from the dataset dictionary."""
    data_copy = data.copy()
    # Add dummy fields required by Chunk dataclass if missing
    if 'date_start' not in data_copy:
        data_copy['date_start'] = "2023-01-01 00:00:00"
    if 'date_end' not in data_copy:
        data_copy['date_end'] = "2023-01-01 00:00:00"
    if 'file_source' not in data_copy:
        data_copy['file_source'] = "dataset.txt"

    # Chunk.from_dict filters out unknown fields like 'metadata'
    return Chunk.from_dict(data_copy)

def run_performance_test(chunks_data: List[Dict], num_trials: int = 5):
    print("\n" + "="*60)
    print("🚀 PERFORMANCE EVALUATION")
    print("="*60)
    
    # Use a subset for performance testing to be faster
    test_subset = chunks_data[:num_trials]
    print(f"Testing with {len(test_subset)} chunks...")

    def progress(i, total):
        print(f"  Processed {i}/{total} chunks...", end='\r')

    # --- Run 1: Dynamic Model Switch ON ---
    print("\n[1/2] Testing Dynamic Switch ON...")
    config_dynamic = Config()
    config_dynamic.enable_complexity_routing = True
    config_dynamic.model_loading_strategy = "dual" # Assume dual loading for fair comparison if possible, or whatever default
    
    enricher_dynamic = ChunkEnricher(config=config_dynamic)
    
    # Deepcopy to avoid state pollution
    chunks_dynamic = [create_chunk_from_dict(c) for c in test_subset]
    
    start_time = time.time()
    enricher_dynamic.enrich_batch(chunks_dynamic, progress_callback=progress)
    print() # Newline after progress
    duration_dynamic = time.time() - start_time
    
    print(f"⏱️  Duration: {duration_dynamic:.2f}s")
    print(f"📊 Stats: {enricher_dynamic.routing_stats}")

    # --- Run 2: Dynamic Switch OFF (Force Strong Model) ---
    print("\n[2/2] Testing Dynamic Switch OFF (All Strong Model)...")
    config_static = Config()
    config_static.enable_complexity_routing = False
    # Static usually implies using the main 'llm_model' (8b)
    
    enricher_static = ChunkEnricher(config=config_static)
    
    # Deepcopy to avoid state pollution
    chunks_static = [create_chunk_from_dict(c) for c in test_subset]
    
    start_time = time.time()
    enricher_static.enrich_batch(chunks_static, progress_callback=progress)
    print() # Newline
    duration_static = time.time() - start_time
    
    print(f"⏱️  Duration: {duration_static:.2f}s")

    # --- Results ---
    print("\n" + "-"*30)
    print("🏆 PERFORMANCE RESULTS")
    print("-" * 30)
    print(f"Dynamic Switch: {duration_dynamic:.2f}s")
    print(f"Static (Strong): {duration_static:.2f}s")
    
    if duration_dynamic < duration_static:
        saved = duration_static - duration_dynamic
        percent = (saved / duration_static) * 100
        print(f"✅ Dynamic Switch is {percent:.1f}% faster ({saved:.2f}s saved)")
    else:
        print(f"⚠️ Dynamic Switch was slower (overhead > gain)")

def run_quality_eval(chunks_data: List[Dict], num_samples: int = 3):
    print("\n" + "="*60)
    print("🧠 QUALITY EVALUATION (3B vs 8B)")
    print("="*60)

    # Convert to valid Chunk objects but keep metadata for filtering
    simple_chunks_data = [c for c in chunks_data if c.get('metadata', {}).get('complexity_category') == 'simple']
    medium_chunks_data = [c for c in chunks_data if c.get('metadata', {}).get('complexity_category') == 'medium']

    # Take samples
    selected_samples = []
    selected_samples.extend(simple_chunks_data[:num_samples])
    selected_samples.extend(medium_chunks_data[:num_samples])
    
    print(f"Selected {len(selected_samples)} samples ({len(simple_chunks_data[:num_samples])} Simple, {len(medium_chunks_data[:num_samples])} Medium)")

    results = []

    # Initialize generic config
    config = Config()
    
    # Define models to compare
    model_3b = config.llm_light_model # e.g. ministral-3:3b
    model_8b = config.llm_model # e.g. ministral-3:8b
    
    print(f"Comparing {model_3b} (Small) vs {model_8b} (Large)...")

    for i, data in enumerate(selected_samples):
        chunk_input = create_chunk_from_dict(data)
        category = data.get('metadata', {}).get('complexity_category', 'unknown')
        score = data.get('metadata', {}).get('complexity_score', 0)
        
        print(f"\n[{i+1}/{len(selected_samples)}] Processing chunk {chunk_input.chunk_id[:15]}... ({category})")

        # --- Run 3B ---
        print(f"  🤖 Running {model_3b}...", end="", flush=True)
        config_3b = Config()
        config_3b.enable_complexity_routing = False # Disable routing to force model
        config_3b.force_model = model_3b
        enricher_3b = ChunkEnricher(config=config_3b)
        
        chunk_3b = create_chunk_from_dict(data) # Fresh copy
        start = time.time()
        # Capture returns!
        res_3b = enricher_3b.enrich_chunk(chunk_3b) 
        (summary, questions, intents, temporal, entities, emotions, pattern, initiative, shift, loops) = res_3b
        
        chunk_3b.narrative_summary = summary
        chunk_3b.hypothetical_questions = questions
        chunk_3b.speaker_intents = intents
        chunk_3b.temporal_context = temporal
        chunk_3b.entities = entities
        chunk_3b.emotions = emotions
        
        time_3b = time.time() - start
        print(f" Done ({time_3b:.2f}s)")

        # --- Run 8B ---
        print(f"  🤖 Running {model_8b}...", end="", flush=True)
        config_8b = Config()
        config_8b.enable_complexity_routing = False
        config_8b.force_model = model_8b
        enricher_8b = ChunkEnricher(config=config_8b)
        
        chunk_8b = create_chunk_from_dict(data) # Fresh copy
        start = time.time()
        # Capture returns!
        res_8b = enricher_8b.enrich_chunk(chunk_8b)
        (summary, questions, intents, temporal, entities, emotions, pattern, initiative, shift, loops) = res_8b
        
        chunk_8b.narrative_summary = summary
        chunk_8b.hypothetical_questions = questions
        chunk_8b.speaker_intents = intents
        chunk_8b.temporal_context = temporal
        chunk_8b.entities = entities
        chunk_8b.emotions = emotions
        
        time_8b = time.time() - start
        print(f" Done ({time_8b:.2f}s)")

        results.append({
            "chunk_id": chunk_input.chunk_id,
            "content": chunk_input.content,
            "category": category, 
            "complexity_score": score,
            "model_3b": {
                "name": model_3b,
                "summary": chunk_3b.narrative_summary,
                "intents": chunk_3b.speaker_intents,
                "questions": chunk_3b.hypothetical_questions,
                "entities": chunk_3b.entities,
                "emotions": chunk_3b.emotions,
                "temporal": chunk_3b.temporal_context,
                "time": time_3b
            },
            "model_8b": {
                "name": model_8b,
                "summary": chunk_8b.narrative_summary,
                "intents": chunk_8b.speaker_intents,
                "questions": chunk_8b.hypothetical_questions,
                "entities": chunk_8b.entities,
                "emotions": chunk_8b.emotions,
                "temporal": chunk_8b.temporal_context,
                "time": time_8b
            }
        })

    # Generate Report
    generate_quality_report(results)

def generate_quality_report(results: List[Dict]):
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f"""
<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dynamic Switch Quality Eval</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>body {{ font-family: 'Inter', sans-serif; }}</style>
</head>
<body class="h-full">
    <div class="min-h-full py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-7xl mx-auto">
            <div class="text-center mb-12">
                <h1 class="text-3xl font-bold text-slate-900">🔍 Dynamic Switch Quality Evaluation</h1>
                <p class="mt-2 text-slate-600">Comparing 3B vs 8B enrichment quality for Simple/Medium chunks</p>
                <p class="text-sm text-slate-500">{timestamp_str}</p>
            </div>

            <div class="space-y-12">
    """

    for res in results:
        cat_color = "bg-green-100 text-green-800" if res['category'] == 'simple' else "bg-yellow-100 text-yellow-800"
        
        html += f"""
                <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <div class="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center">
                        <div>
                            <span class="font-mono text-xs text-slate-500 block mb-1">{res['chunk_id']}</span>
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold {cat_color} uppercase tracking-wide">
                                {res['category']} (Score: {res['complexity_score']:.2f})
                            </span>
                        </div>
                    </div>
                    
                    <div class="p-6">
                        <div class="mb-6 bg-slate-50 p-4 rounded-lg border border-slate-200">
                            <h4 class="text-xs font-bold text-slate-500 uppercase mb-2">Source Content</h4>
                            <pre class="text-xs text-slate-700 whitespace-pre-wrap font-mono">{res['content']}</pre>
                        </div>

                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <!-- 3B Model -->
                            <div class="border border-slate-200 rounded-lg p-5 hover:border-indigo-300 transition-colors">
                                <div class="flex items-center justify-between mb-4 border-b border-slate-100 pb-2">
                                    <h3 class="font-bold text-indigo-700">{res['model_3b']['name']}</h3>
                                    <span class="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded">{res['model_3b']['time']:.2f}s</span>
                                </div>
                                <div class="space-y-4">
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Summary</h4>
                                        <p class="text-sm text-slate-700">{res['model_3b']['summary']}</p>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Temporal</h4>
                                        <p class="text-sm text-slate-700">{res['model_3b']['temporal']}</p>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Intents</h4>
                                        <ul class="text-sm text-slate-700 list-disc ml-4">
                                            {format_dict(res['model_3b']['intents'])}
                                        </ul>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Entities</h4>
                                        <ul class="text-sm text-slate-700 list-disc ml-4">
                                            {format_dict(res['model_3b']['entities'])}
                                        </ul>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Emotions</h4>
                                        <ul class="text-sm text-slate-700 list-disc ml-4">
                                            {format_dict(res['model_3b']['emotions'])}
                                        </ul>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Questions</h4>
                                        <ul class="text-sm text-slate-700 list-disc ml-4">
                                            {format_list(res['model_3b']['questions'])}
                                        </ul>
                                    </div>
                                </div>
                            </div>

                            <!-- 8B Model -->
                            <div class="border border-slate-200 rounded-lg p-5 hover:border-emerald-300 transition-colors">
                                <div class="flex items-center justify-between mb-4 border-b border-slate-100 pb-2">
                                    <h3 class="font-bold text-emerald-700">{res['model_8b']['name']}</h3>
                                    <span class="text-xs bg-emerald-50 text-emerald-700 px-2 py-1 rounded">{res['model_8b']['time']:.2f}s</span>
                                </div>
                                <div class="space-y-4">
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Summary</h4>
                                        <p class="text-sm text-slate-700">{res['model_8b']['summary']}</p>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Temporal</h4>
                                        <p class="text-sm text-slate-700">{res['model_8b']['temporal']}</p>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Intents</h4>
                                        <ul class="text-sm text-slate-700 list-disc ml-4">
                                            {format_dict(res['model_8b']['intents'])}
                                        </ul>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Entities</h4>
                                        <ul class="text-sm text-slate-700 list-disc ml-4">
                                            {format_dict(res['model_8b']['entities'])}
                                        </ul>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Emotions</h4>
                                        <ul class="text-sm text-slate-700 list-disc ml-4">
                                            {format_dict(res['model_8b']['emotions'])}
                                        </ul>
                                    </div>
                                    <div>
                                        <h4 class="text-xs font-bold text-slate-900 uppercase">Questions</h4>
                                        <ul class="text-sm text-slate-700 list-disc ml-4">
                                            {format_list(res['model_8b']['questions'])}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
        """

    html += """
            </div>
        </div>
    </div>
</body>
</html>
    """
    
    output_path = Path(__file__).parent / f"dynamic_switch_eval_{int(time.time())}.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ Report generated: {output_path}")
    print(f"   Open: open {output_path}")

def format_dict(d: Dict) -> str:
    if not d: return "<li>(None)</li>"
    return "".join([f"<li><b>{k}:</b> {v}</li>" for k, v in d.items()])

def format_list(l: List) -> str:
    if not l: return "<li>(None)</li>"
    return "".join([f"<li>{item}</li>" for item in l])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Dynamic Model Switching")
    parser.add_argument("--perf-trials", type=int, default=10, help="Number of chunks for performance test")
    parser.add_argument("--quality-samples", type=int, default=3, help="Number of samples per category for quality test")
    parser.add_argument("--skip-perf", action="store_true")
    parser.add_argument("--skip-quality", action="store_true")
    
    args = parser.parse_args()
    
    path = Path(__file__).parent / "complexity_eval_dataset.json"
    if not path.exists():
        print(f"Error: Dataset not found at {path}")
        sys.exit(1)
        
    chunks_data = load_dataset_chunks(path)
    print(f"Loaded {len(chunks_data)} chunks from dataset")

    if not args.skip_perf:
        run_performance_test(chunks_data, args.perf_trials)
        
    if not args.skip_quality:
        run_quality_eval(chunks_data, args.quality_samples)
