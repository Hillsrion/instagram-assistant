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
from eval.enrichment.enrichment_validator import (
    EnrichmentValidator,
    EnrichmentBenchmarkReport,
    print_benchmark_report,
    ChunkEnrichmentValidationReport
)
from eval.core._output_paths import get_enrichment_report_path
from rag_pipeline.llm_provider import create_provider

def calculate_stats(results: List[Dict], models: List[str]) -> Dict:
    """Calculate aggregate statistics for models."""
    stats = {
        "models": {m: {"total_score": 0, "total_time": 0, "wins": 0, "field_scores": {}} for m in models},
        "fields": [],
        "total_chunks": len(results)
    }
    
    if not results:
        return stats
        
    # Initialize fields from first result
    first_model_res = results[0]['model_results'].get(models[0])
    if first_model_res:
         stats['fields'] = list(first_model_res['report'].field_results.keys())
    
    for m in models:
        for f in stats['fields']:
            stats['models'][m]['field_scores'][f] = 0.0

    for res in results:
        best_score = -1.0
        winner = None
        
        # Determine winner
        for m in models:
            m_res = res['model_results'].get(m)
            if not m_res: continue
            
            score = m_res['report'].overall_score
            if score > best_score:
                best_score = score
                winner = m
            elif score == best_score:
                # Tie: treat as shared win or ignore? For simplicity, first one takes it or ignore.
                pass
        
        if winner:
            stats['models'][winner]['wins'] += 1
            
        # Accumulate values
        for m in models:
            m_res = res['model_results'].get(m)
            if not m_res: continue
            
            report = m_res['report']
            stats['models'][m]['total_score'] += report.overall_score
            stats['models'][m]['total_time'] += m_res['time']
            
            for f, f_res in report.field_results.items():
                if f in stats['models'][m]['field_scores']:
                    stats['models'][m]['field_scores'][f] += f_res.score

    # Compute averages
    n = len(results)
    if n > 0:
        for m in models:
            stats['models'][m]['avg_score'] = stats['models'][m]['total_score'] / n
            stats['models'][m]['avg_time'] = stats['models'][m]['total_time'] / n
            stats['models'][m]['win_rate'] = (stats['models'][m]['wins'] / n) * 100
            
            for f in stats['fields']:
                 stats['models'][m]['field_scores'][f] /= n
    
    # Per-Complexity Stats
    stats['complexity'] = {}
    for cat in ['simple', 'medium', 'complex']:
        cat_chunks = [r for r in results if r.get('category') == cat]
        count = len(cat_chunks)
        
        cat_stats = {
            "count": count,
            "models": {m: {"avg_score": 0.0, "win_rate": 0.0, "avg_time": 0.0} for m in models}
        }
        
        if count > 0:
            for m in models:
                total_score = 0
                total_time = 0
                wins = 0
                for res in cat_chunks:
                    m_res = res['model_results'].get(m)
                    if not m_res: continue
                    total_score += m_res['report'].overall_score
                    total_time += m_res['time']
                    
                    # Recalculate winner for this chunk (could optimize by storing winner in result)
                    scores = {mod: res['model_results'][mod]['report'].overall_score for mod in models if mod in res['model_results']}
                    if scores and max(scores.values()) == scores[m] and list(scores.values()).count(max(scores.values())) == 1:
                         wins += 1
                    
                cat_stats['models'][m]['avg_score'] = total_score / count
                cat_stats['models'][m]['avg_time'] = total_time / count
                cat_stats['models'][m]['win_rate'] = (wins / count) * 100
        
        stats['complexity'][cat] = cat_stats
                 
    return stats

def get_judge_summary(stats: Dict, judge_model: str, provider: str, config: Config) -> str:
    """Generate a global summary using the judge LLM."""
    try:
        print(f"👨‍⚖️ Generating global verdict with {judge_model}...")
        llm = create_provider(config=config, model=judge_model, provider_type=provider)
        
        prompt = "Tu es un expert en évaluation comparant des modèles d'IA pour des tâches d'enrichissement RAG.\n"
        prompt += "Analyse les statistiques de performance suivantes et fournis une comparaison définitive en FRANÇAIS.\n\n"
        
        for m, data in stats['models'].items():
            prompt += f"## Modèle: {m}\n"
            prompt += f"- Score de Qualité Moyen: {data['avg_score']:.2f}/1.0\n"
            prompt += f"- Taux de Victoire: {data['wins']}/{stats['total_chunks']} segments ({data['win_rate']:.1f}%)\n"
            prompt += f"- Temps Moyen: {data['avg_time']:.2f}s\n"
            prompt += "- Détail par métrique:\n"
            for f, s in data['field_scores'].items():
                prompt += f"  * {f}: {s:.2f}\n"
            prompt += "\n"
        
        prompt += "QUESTION: Quel modèle est le meilleur globalement ? Pourquoi ?\n"
        prompt += "CONSIGNES:\n"
        prompt += "1. Rédige ton verdict exclusivement en FRANÇAIS.\n"
        prompt += "2. Commence par déclarer clairement le vainqueur.\n"
        prompt += "3. Compare leurs forces et faiblesses en te basant sur les chiffres.\n"
        prompt += "4. Commenter le trade-off vitesse/qualité si pertinent.\n"
        prompt += "5. Sois concis (moins de 150 mots)."
        
        messages = [{"role": "user", "content": prompt}]
        response = llm.generate(messages, temperature=0.3)
        return response
    except Exception as e:
        print(f"⚠️ Could not generate judge summary: {e}")
        return "Global judge summary currently unavailable due to an error."

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
    
    chunk = Chunk.from_dict(data_copy)
    # Preserve original metadata dict if it exists in the input
    if 'metadata' in data_copy:
        chunk.metadata = data_copy['metadata']
    return chunk

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
    models: List[str],
    stats: Dict,
    judge_verdict: str
) -> Path:
    """Generate a side-by-side HTML comparison report with charts."""
    
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    grid_cols = f"grid-cols-1 lg:grid-cols-{len(models)}" if len(models) > 1 else "max-w-4xl mx-auto"
    
    # Serialize stats for JS
    stats_json = json.dumps(stats, default=str)
    
    html = f"""
<!DOCTYPE html>
<html lang="en" class="bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
        pre {{ font-family: 'JetBrains Mono', monospace; }}
        .prose {{ max-width: none; }}
        /* Ensure markdown content looks good in small cards */
        .reason-prose {{ font-size: 0.8rem; line-height: 1.4; }}
        .reason-prose p {{ margin-bottom: 0.5rem; }}
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

    <!-- Judge Verdict -->
    <div class="mb-12 bg-white rounded-xl shadow-lg border border-indigo-100 p-8">
        <h2 class="text-xl font-bold text-gray-900 flex items-center mb-4">
            👨‍⚖️ Global Judge Verdict
        </h2>
        <div id="global-verdict" class="prose prose-indigo max-w-none text-gray-700 bg-indigo-50/50 p-6 rounded-lg border border-indigo-50 leading-relaxed italic whitespace-pre-wrap" data-markdown="{judge_verdict.replace('"', '&quot;')}">
            {judge_verdict}
        </div>
    </div>

    <!-- Dashboard -->
    <div class="mb-16 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div class="bg-white p-6 rounded-xl shadow border border-gray-200">
            <h3 class="font-bold text-gray-500 text-xs uppercase mb-4 text-center">Global Win Rate (%)</h3>
            <div class="h-64"><canvas id="winRateChart"></canvas></div>
        </div>
        <div class="bg-white p-6 rounded-xl shadow border border-gray-200">
            <h3 class="font-bold text-gray-500 text-xs uppercase mb-4 text-center">Avg Speed (s)</h3>
            <div class="h-64"><canvas id="speedChart"></canvas></div>
        </div>
        <div class="bg-white p-6 rounded-xl shadow border border-gray-200">
            <h3 class="font-bold text-gray-500 text-xs uppercase mb-4 text-center">Quality Breakdown (0-1)</h3>
            <div class="h-64"><canvas id="metricsChart"></canvas></div>
        </div>
    </div>
    
    <!-- Complexity Breakdown -->
    <div class="mb-16">
        <h3 class="text-xl font-bold text-gray-800 mb-6 flex items-center">
            🧩 Performance by Complexity
        </h3>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
             <div class="bg-white p-6 rounded-xl shadow border border-gray-200">
                <h3 class="font-bold text-gray-500 text-xs uppercase mb-4 text-center">Win Rate by Complexity</h3>
                <div class="h-64"><canvas id="compWinChart"></canvas></div>
            </div>
            <div class="bg-white p-6 rounded-xl shadow border border-gray-200">
                <h3 class="font-bold text-gray-500 text-xs uppercase mb-4 text-center">Quality Score by Complexity</h3>
                <div class="h-64"><canvas id="compScoreChart"></canvas></div>
            </div>
        </div>
    </div>

    <!-- Filters -->
    <div class="sticky top-4 z-50 mb-8 flex justify-center space-x-2 bg-white/80 backdrop-blur p-2 rounded-full shadow-lg border border-gray-200 w-fit mx-auto">
        <button onclick="filterChunks('all')" class="filter-btn px-4 py-1.5 rounded-full text-sm font-medium bg-gray-900 text-white transition-colors" data-filter="all">All</button>
        <button onclick="filterChunks('simple')" class="filter-btn px-4 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-green-100 hover:text-green-800 transition-colors" data-filter="simple">Simple</button>
        <button onclick="filterChunks('medium')" class="filter-btn px-4 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-blue-100 hover:text-blue-800 transition-colors" data-filter="medium">Medium</button>
        <button onclick="filterChunks('complex')" class="filter-btn px-4 py-1.5 rounded-full text-sm font-medium bg-gray-100 text-gray-600 hover:bg-red-100 hover:text-red-800 transition-colors" data-filter="complex">Complex</button>
    </div>
    
    <script>
        const stats = {stats_json};
        const models = Object.keys(stats.models);
        
        // Win Rate Pie
        new Chart(document.getElementById('winRateChart'), {{
            type: 'doughnut',
            data: {{
                labels: models,
                datasets: [{{
                    data: models.map(m => stats.models[m].win_rate),
                    backgroundColor: ['#4ade80', '#60a5fa', '#f87171', '#fbbf24'],
                }}]
            }},
            options: {{ responsive: true, maintainAspectRatio: false }}
        }});

        // Speed Bar
        new Chart(document.getElementById('speedChart'), {{
            type: 'bar',
            data: {{
                labels: models,
                datasets: [{{
                    label: 'Seconds per Chunk',
                    data: models.map(m => stats.models[m].avg_time),
                    backgroundColor: '#e5e7eb',
                    borderColor: '#9ca3af',
                    borderWidth: 1,
                    borderRadius: 4
                }}]
            }},
            options: {{ 
                indexAxis: 'y',
                responsive: true, 
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});
        
        // Metrics Radar
        const fields = stats.fields;
        const metricsDatasets = models.map((m, i) => ({{
            label: m,
            data: fields.map(f => stats.models[m].field_scores[f]),
            borderColor: ['#16a34a', '#2563eb', '#dc2626'][i % 3],
            backgroundColor: ['rgba(22, 163, 74, 0.2)', 'rgba(37, 99, 235, 0.2)', 'rgba(220, 38, 38, 0.2)'][i % 3],
        }}));
        
        new Chart(document.getElementById('metricsChart'), {{
            type: 'radar',
            data: {{
                labels: fields.map(f => f.replace('_', ' ').replace('narrative', '').trim().substring(0, 10)),
                datasets: metricsDatasets
            }},
            options: {{ 
                responsive: true, 
                maintainAspectRatio: false,
                scales: {{
                    r: {{ min: 0, max: 1 }}
                }}
            }}
        }});
        
        // COMPLEXITY CHARTS
        const categories = ['simple', 'medium', 'complex'];
        
        // Win Rate by Complexity
        new Chart(document.getElementById('compWinChart'), {{
            type: 'bar',
            data: {{
                labels: categories,
                datasets: models.map((m, i) => ({{
                    label: m,
                    data: categories.map(c => stats.complexity[c]?.models[m]?.win_rate || 0),
                    backgroundColor: ['#4ade80', '#60a5fa', '#f87171'][i % 3],
                }}))
            }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                scales: {{ y: {{ beginAtZero: true, max: 100, title: {{display: true, text: 'Win Rate %'}} }} }}
            }}
        }});
        
        // Quality Score by Complexity
         new Chart(document.getElementById('compScoreChart'), {{
            type: 'bar',
            data: {{
                labels: categories,
                datasets: models.map((m, i) => ({{
                    label: m,
                    data: categories.map(c => stats.complexity[c]?.models[m]?.avg_score || 0),
                    backgroundColor: ['#16a34a', '#2563eb', '#dc2626'][i % 3],
                }}))
            }},
             options: {{
                responsive: true, maintainAspectRatio: false,
                scales: {{ y: {{ beginAtZero: true, max: 1.0, title: {{display: true, text: 'Avg Score (0-1)'}} }} }}
            }}
        }});

        // Filtering Logic
        function filterChunks(category) {{
            const chunks = document.querySelectorAll('.chunk-card');
            chunks.forEach(card => {{
                if (category === 'all' || card.dataset.complexity === category) {{
                    card.style.display = 'block';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
            
            // Update buttons
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                if (btn.dataset.filter === category) {{
                    btn.classList.add('bg-gray-900', 'text-white');
                    btn.classList.remove('bg-gray-100', 'text-gray-600');
                }} else {{
                    btn.classList.add('bg-gray-100', 'text-gray-600');
                }}
            }});
        }}

        // Markdown Rendering
        window.addEventListener('DOMContentLoaded', () => {{
            // Render global verdict
            const verdictEl = document.getElementById('global-verdict');
            if (verdictEl && verdictEl.dataset.markdown) {{
                verdictEl.innerHTML = marked.parse(verdictEl.dataset.markdown);
                verdictEl.classList.remove('whitespace-pre-wrap');
            }}

            // Render all reasons
            document.querySelectorAll('.reason-markdown').forEach(el => {{
                if (el.dataset.markdown) {{
                    el.innerHTML = marked.parse(el.dataset.markdown);
                }}
            }});
        }});
    </script>

    <div class="space-y-16">
"""
    
    for res in results:
        chunk_rec = res['original_chunk']
        model_results = res['model_results']
        
        # Color badge for score
        complexity_html = ""
        category = res.get('category', 'unknown')
        if 'complexity_score' in res:
             complexity_html = f"""
             <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 border border-gray-200 ml-2">
                Complexity: {category} ({res['complexity_score']:.2f})
             </span>
             """

        html += f"""
        <!-- Chunk Block -->
        <div class="chunk-card bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden" data-complexity="{category}">
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
        
        # Determine the winner for this chunk
        best_score = -1.0
        winner_model = None
        
        # First pass to find the winner
        for model in models:
            m_res = model_results.get(model)
            if m_res:
                score = m_res['report'].overall_score
                if score > best_score:
                    best_score = score
                    winner_model = model
                elif score == best_score:
                    # Tie-breaker: Time (optional, or just treat first as winner/tied)
                    pass

        for model in models:
            m_res = model_results.get(model)
            if not m_res:
                html += f"""<div class="border-2 border-dashed border-gray-200 rounded-lg p-10 text-center text-gray-400">No data for {model}</div>"""
                continue
                
            report = m_res['report']
            data = m_res['data']
            time_taken = m_res['time']
            
            score = report.overall_score
            is_winner = (model == winner_model)
            
            # Border: Green only if winner, else gray
            border_class = "border-green-500 ring-4 ring-green-50" if is_winner else "border-gray-200"
            if is_winner:
               score_color = "text-green-700" 
            elif score >= 0.8: 
               score_color = "text-gray-900" 
            elif score >= 0.5:
               score_color = "text-orange-600"
            else:
               score_color = "text-red-600"

            html += f"""
                    <!-- Model Column: {model} -->
                    <div class="flex flex-col h-full bg-white border-2 {border_class} rounded-lg overflow-hidden relative transition-all hover:shadow-md">
                        <!-- Header -->
                        <div class="bg-gray-50/50 p-4 border-b border-gray-100">
                            <div class="flex justify-between items-start mb-2">
                                <h3 class="font-bold text-gray-900 truncate" title="{model}">{model}</h3>
                                <span class="text-xs font-mono bg-gray-200 text-gray-700 px-2 py-1 rounded">{time_taken:.2f}s</span>
                            </div>
                            <div class="flex items-baseline space-x-2">
                                <span class="text-2xl font-bold {score_color}">{score:.2f}</span>
                                <span class="text-xs text-gray-500 font-medium uppercase">Score</span>
                                { '<span class="ml-2 text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full font-bold">WINNER</span>' if is_winner else '' }
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

def generate_comparative_json_report(
    results: List[Dict], 
    models: List[str],
    stats: Dict,
    judge_verdict: str
) -> Path:
    """Generate a comparative JSON report."""
    timestamp = datetime.now()
    
    # Prepare serializable results
    serializable_results = []
    for res in results:
        res_copy = res.copy()
        # Convert Chunk objects to dicts
        res_copy['original_chunk'] = res['original_chunk'].to_dict()
        
        # Convert model results reports to dicts
        res_copy['model_results'] = {}
        for m, m_data in res['model_results'].items():
            res_copy['model_results'][m] = {
                "data": m_data['data'].to_dict(),
                "report": m_data['report'].to_dict(),
                "time": m_data['time']
            }
        serializable_results.append(res_copy)

    report_data = {
        "timestamp": timestamp.isoformat(),
        "models": models,
        "stats": stats,
        "results": serializable_results,
        "judge_verdict": judge_verdict
    }

    output_path = get_enrichment_report_path(models, timestamp=timestamp, format="json")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        
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
        <div class="flex items-center space-x-2 mb-1">
            <h4 class="text-xs font-bold text-gray-500 uppercase">Narrative Summary</h4>
            {render_field_feedback(report.field_results.get('narrative_summary'))}
        </div>
        <p class="text-gray-800 leading-relaxed">{chunk.narrative_summary or '<span class="text-gray-400 italic">Empty</span>'}</p>
    </div>
    """

    # Intents
    html += f"""
    <div>
        <div class="flex items-center space-x-2 mb-2">
            <h4 class="text-xs font-bold text-gray-500 uppercase">Intentions</h4>
            {render_field_feedback(report.field_results.get('speaker_intents'))}
        </div>
        {render_dict_list_html(chunk.speaker_intents)}
    </div>
    """

    # Entities
    html += f"""
    <div>
        <div class="flex items-center space-x-2 mb-2">
            <h4 class="text-xs font-bold text-gray-500 uppercase">Entities</h4>
            {render_field_feedback(report.field_results.get('entities'))}
        </div>
        {render_entities_html(chunk.entities)}
    </div>
    """
    
    # Emotions
    html += f"""
    <div>
        <div class="flex items-center space-x-2 mb-2">
            <h4 class="text-xs font-bold text-gray-500 uppercase">Emotions</h4>
            {render_field_feedback(report.field_results.get('emotions'))}
        </div>
        {render_dict_list_html(chunk.emotions)}
    </div>
    """

    # Temporal & Questions
    html += f"""
    <div class="grid grid-cols-1 gap-4">
        <div>
            <div class="flex items-center space-x-2 mb-1">
                <h4 class="text-xs font-bold text-gray-500 uppercase">Temporal Context</h4>
                {render_field_feedback(report.field_results.get('temporal_context'))}
            </div>
            <p class="text-gray-700">{chunk.temporal_context or '-'}</p>
        </div>
        <div>
            <div class="flex items-center space-x-2 mb-2">
                <h4 class="text-xs font-bold text-gray-500 uppercase">Hypothetical Questions</h4>
                {render_field_feedback(report.field_results.get('questions'))}
            </div>
            <ul class="list-disc list-inside text-gray-700 space-y-1">
                {''.join(f'<li>{q}</li>' for q in (chunk.hypothetical_questions or []))}
            </ul>
             { '<p class="text-gray-400 italic">None</p>' if not chunk.hypothetical_questions else ''}
        </div>
    </div>
    """

    # Social Dynamics
    html += f"""
    <div class="border-t border-gray-100 pt-4 mt-2">
        <h4 class="text-xs font-bold text-gray-400 uppercase mb-3 tracking-widest text-center">Social Dynamics</h4>
        <div class="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
            <div class="bg-gray-50 p-2 rounded border border-gray-100">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-gray-400 uppercase font-semibold">Pattern</span>
                    {render_field_feedback(report.field_results.get('interaction_pattern'))}
                </div>
                <div class="font-medium text-gray-700">{chunk.interaction_pattern or 'None'}</div>
            </div>
            <div class="bg-gray-50 p-2 rounded border border-gray-100">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-gray-400 uppercase font-semibold">Initiative</span>
                    {render_field_feedback(report.field_results.get('initiative'))}
                </div>
                <div class="font-medium text-gray-700">{chunk.initiative or 'None'}</div>
            </div>
            <div class="bg-gray-50 p-2 rounded border border-gray-100">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-gray-400 uppercase font-semibold">Shift</span>
                    {render_field_feedback(report.field_results.get('emotional_shift'))}
                </div>
                <div class="font-medium text-gray-700">{chunk.emotional_shift or 'None'}</div>
            </div>
            <div class="bg-gray-50 p-2 rounded border border-gray-100">
                <div class="flex items-center space-x-2 mb-1">
                    <span class="text-gray-400 uppercase font-semibold">Loops</span>
                    {render_field_feedback(report.field_results.get('open_loops'))}
                </div>
                <div class="font-medium text-gray-700">{", ".join(chunk.open_loops) if chunk.open_loops else "None"}</div>
            </div>
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

def render_field_feedback(field_res):
    if not field_res:
        return ""
    
    # Always show the badge, but only show reasoning if available
    has_reason = 'judge_reason' in field_res.metadata
    reason = field_res.metadata.get('judge_reason', "Aucune observation détaillée (mode heuristique).")
    score = field_res.metadata.get('judge_score', field_res.score)
    
    score_color = "bg-green-100 text-green-800" if score >= 0.8 else "bg-orange-100 text-orange-800" if score >= 0.5 else "bg-red-100 text-red-800"
    
    return f"""
    <div class="group relative flex items-center">
        <span class="cursor-help px-1.5 py-0.5 {score_color} rounded text-[10px] font-bold border border-current opacity-70 hover:opacity-100 transition-opacity">
            {score:.2f}
        </span>
        <div class="pointer-events-none absolute bottom-full left-0 mb-2 w-64 bg-slate-800 text-white text-xs p-3 rounded-lg shadow-xl opacity-0 group-hover:pointer-events-auto group-hover:opacity-100 transition-all z-50 ring-1 ring-white/10">
            <div class="font-bold mb-1 border-b border-white/10 pb-1 flex justify-between">
                <span>{'Juge LLM' if has_reason else 'Heuristique'}</span>
                <span class="text-indigo-300">{score:.2f}</span>
            </div>
            <div class="reason-markdown prose prose-invert reason-prose" data-markdown="{reason.replace('"', '&quot;')}">
                {reason}
            </div>
        </div>
    </div>
    """

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
    parser.add_argument("--json", action="store_true", help="Generate JSON report")
    parser.add_argument("--judge", type=str, default="ministral-3:14b", help="LLM model to use as judge (default: 'ministral-3:14b')")
    parser.add_argument("--provider", type=str, default="ollama", choices=["ollama", "mlx"], help="LLM provider for the judge")
    parser.add_argument("--fast", "--heuristic", action="store_true", dest="fast", help="Use fast heuristic validation instead of LLM judge")
    
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
    if not args.fast:
        print(f"👨‍⚖️  Judge: {args.judge} ({args.provider})")
    else:
        print("⚡️ Validation Mode: Fast (Heuristic)")
    
    # Phase 1: Generation (One model at a time for all chunks)
    validator = EnrichmentValidator(config)
    results = []
    # Initialize results structure
    for original_chunk in chunks:
        meta = getattr(original_chunk, 'metadata', {}) or {}
        results.append({
            "original_chunk": original_chunk,
            "complexity_score": meta.get('complexity_score', 0.0), 
            "category": meta.get('complexity_category', 'unknown'),
            "model_results": {}
        })

    for model in models:
        print(f"\n🚀 Running Generation for model: {model}")
        for chunk_res in results:
            original_chunk = chunk_res["original_chunk"]
            print(f"  🤖 Processing {original_chunk.chunk_id}...", end="", flush=True)
            
            test_chunk = create_chunk_from_dict(original_chunk.to_dict())
            time_taken = enrich_chunk_with_model(test_chunk, model, config)
            
            chunk_res["model_results"][model] = {
                "data": test_chunk,
                "time": time_taken
            }
            print(f" Done ({time_taken:.2f}s)")

    # Phase 2: Validation (Run judge once generation is complete)
    print("\n" + "="*60)
    print("⚖️  PHASE: VALIDATION & JUDGING")
    print("="*60)
    
    for i, chunk_res in enumerate(results):
        print(f"\n[{i+1}/{len(results)}] Judging chunk {chunk_res['original_chunk'].chunk_id}")
        for model in models:
            m_res = chunk_res["model_results"].get(model)
            if not m_res: continue
            
            print(f"  👨‍⚖️  Judging {model}...", end="", flush=True)
            if not args.fast:
                report = validator.validate_chunk_with_llm(m_res["data"], args.judge, args.provider)
            else:
                report = validator.validate_chunk(m_res["data"])
            
            m_res["report"] = report
            print(f" Score: {report.overall_score:.2f}")

    # 4. Report
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    # Calculate stats
    stats = calculate_stats(results, models)
    
    for model in models:
        m_stats = stats['models'][model]
        print(f"Model: {model:<20} | Avg Score: {m_stats['avg_score']:.2f} | Avg Time: {m_stats['avg_time']:.2f}s | Win Rate: {m_stats['win_rate']:.1f}%")
        
    if args.html:
        judge_verdict = ""
        if not args.fast:
             # Just use the config that was loaded
            judge_verdict = get_judge_summary(stats, args.judge, args.provider, config)
        else:
            judge_verdict = "Global verdict not available in heuristic mode. Use LLM judge for detailed analysis."
            
        report_path = generate_comparative_html_report(results, models, stats, judge_verdict)
        print(f"\n✅ HTML Report generated: {report_path}")
        print(f"👉 Open it: open {report_path}")

    if args.json:
        # Re-calculate judge verdict if not already done for HTML
        if not args.html:
             if not args.fast:
                judge_verdict = get_judge_summary(stats, args.judge, args.provider, config)
             else:
                judge_verdict = "Heuristic mode: no LLM verdict."

        report_path = generate_comparative_json_report(results, models, stats, judge_verdict)
        print(f"\n✅ JSON Report generated: {report_path}")

if __name__ == "__main__":
    main()
