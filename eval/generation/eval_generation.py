"""
Evaluate GENERATION quality: compare how different LLMs answer user questions.

This script bypasses retrieval and provides the exact source chunk as context,
isolating the LLM's generation quality from retrieval performance.

Measures: Faithfulness (answer fidelity to sources), Relevance (answer quality),
and generation speed.

Usage:
    python -m eval.eval_generation model1 model2
    python -m eval.eval_generation qwen3:latest mistral --trials 10 --html
"""

import json
import sys
import time
import argparse
import requests
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker, Chunk
from eval.core import RAGASMetrics
from eval.core._output_paths import (
    EVAL_RESULTS_DIR,
    get_generation_report_path,
    get_dashboard_path
)
from rag_pipeline.llm_provider import create_provider

def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text.replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;")
               .replace('"', "&quot;")
               .replace("'", "&#39;"))

def markdown_to_html(text: str) -> str:
    """Convert basic markdown to HTML."""
    if not text:
        return ""

    # Escape HTML first
    text = escape_html(text)

    # Headings: # → <h2>, ## → <h3>, etc.
    text = re.sub(r'^### (.+)$', r'<h4 class="text-lg font-bold text-slate-900 mt-4 mb-2">\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h3 class="text-xl font-bold text-slate-900 mt-4 mb-2">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h2 class="text-2xl font-bold text-slate-900 mt-4 mb-2">\1</h2>', text, flags=re.MULTILINE)

    # Horizontal rule: --- or ***
    text = re.sub(r'^[-\*]{3,}$', r'<hr class="my-4 border-slate-300">', text, flags=re.MULTILINE)

    # Lists: - item → <ul><li>
    text = re.sub(r'^\s*- (.+)$', r'<li class="ml-4 text-slate-700">\1</li>', text, flags=re.MULTILINE)
    # Wrap consecutive <li> in <ul>
    text = re.sub(r'(<li.+?</li>)', r'<ul class="list-disc mb-2">\1</ul>', text, flags=re.DOTALL)

    # Bold: **text** -> <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong class="font-bold text-slate-900">\1</strong>', text)

    # Italic: *text* -> <em>text</em>
    text = re.sub(r'\*(.+?)\*', r'<em class="italic">\1</em>', text)

    # Inline code: `text` -> <code>text</code>
    text = re.sub(r'`([^`]+)`', r'<code class="bg-slate-200 px-2 py-0.5 rounded font-mono text-sm">\1</code>', text)

    # Code blocks: ```code``` -> <pre><code>code</code></pre>
    text = re.sub(r'```(.+?)```', r'<pre class="bg-slate-100 p-3 rounded overflow-x-auto"><code class="text-xs">\1</code></pre>', text, flags=re.DOTALL)

    # Links: [text](url) -> <a>text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="text-indigo-600 hover:underline font-medium">\1</a>', text)

    # Wrap paragraphs instead of using <br>
    paragraphs = text.split('\n\n')
    wrapped = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Don't wrap block-level elements
        if p.startswith('<h') or p.startswith('<hr') or p.startswith('<ul') or p.startswith('<pre') or p.startswith('<li'):
            wrapped.append(p)
        else:
            # Replace single newlines within a paragraph with spaces
            p = p.replace('\n', ' ')
            wrapped.append(f'<p class="mb-2">{p}</p>')

    return '\n'.join(wrapped)

def format_chunk_as_chat(chunk: Chunk, chunk_id: str = "") -> str:
    """Format a chunk with its messages as a chat-like display with left/right alignment."""
    if not chunk_id:
        chunk_id = f"source-{chunk.chunk_id.replace('_', '-')}"

    # Parse the content to find messages
    lines = chunk.content.split('\n')
    messages = []
    current_author = None

    for line in lines:
        if not line.strip():
            continue

        parts = line.split(':', 1)
        if len(parts) == 2 and len(parts[0]) < 50:
            author = parts[0].strip()
            content = parts[1].strip()
            messages.append((author, content))
        else:
            if line.strip():
                messages.append((None, line.strip()))

    # Get unique participants for color mapping (darker shades for better text contrast)
    participants = [p for p in chunk.participants if p]
    participant_colors = {
        p: ["bg-indigo-600", "bg-purple-600", "bg-cyan-600", "bg-rose-600"][i % 4]
        for i, p in enumerate(participants)
    }

    # Build HTML with chat interface (centered, max-w-2xl)
    html = f"""
    <div class="chat-container max-w-2xl mx-auto" data-chunk="{chunk_id}">
        <div class="mb-3 pb-3 border-b border-slate-300">
            <div class="text-xs font-bold text-slate-600 uppercase tracking-wide mb-2">
                📌 Conversation • {', '.join(participants) if participants else 'N/A'} • {chunk.date_start[:10]} to {chunk.date_end[:10]}
            </div>
        </div>

        <div class="space-y-3 max-h-80 overflow-y-auto chat-messages">
    """

    for author, content in messages:
        if author is None:
            # System message or info - treat as a neutral message
            html += f"""
            <div class="flex justify-center my-3 px-2">
                <div class="text-xs text-slate-600 italic bg-slate-200 px-3 py-2 rounded-lg max-w-sm text-center border border-slate-300">
                    📌 {escape_html(content)}
                </div>
            </div>
            """
        else:
            # First participant's messages on the right ("my messages"), others on the left
            is_first = participants and author == participants[0]
            align_class = "justify-end" if is_first else "justify-start"
            color = participant_colors.get(author, "bg-indigo-500")

            html += f"""
            <div class="flex {align_class} mb-3 px-2">
                <div class="flex flex-col {'ml-2' if is_first else 'mr-2'} max-w-xs">
                    <span class="text-xs font-bold text-slate-700 mb-1 {'mr-2 text-right' if is_first else 'ml-2'}">
                        {escape_html(author)}
                    </span>
                    <div class="rounded-xl px-4 py-2 {color} text-white text-sm break-words shadow-sm">
                        {escape_html(content)}
                    </div>
                </div>
            </div>
            """

    html += """
        </div>
    </div>
    """

    return html

def get_eval_prompt(question: str, context: str) -> str:
    """
    Build the evaluation prompt for any model in French.
    """
    return f"""Réponds à la question ci-dessous en te basant UNIQUEMENT sur le contexte fourni.

Règles :
- Réponds directement et de manière concise
- N'ajoute pas d'interprétations ou de suppositions au-delà du texte
- Si l'information n'est pas dans le contexte, dis-le
- TA RÉPONSE DOIT ÊTRE EN FRANÇAIS

Contexte :
{context}

Question : {question}

Réponse :"""



def create_judge(config: Config, judge_model: str = None, provider_type: str = "ollama") -> RAGASMetrics:
    """
    Create a RAGASMetrics instance configured as a judge.

    Args:
        config: Base configuration
        judge_model: Optional model override for judging
        provider_type: "ollama" or "mlx"

    Returns:
        RAGASMetrics instance configured for judging
    """
    metrics = RAGASMetrics(config, provider_type=provider_type)
    if judge_model:
        metrics.config.llm_model = judge_model
    return metrics


def judge_response(
    metrics: RAGASMetrics,
    question: str,
    expected: str,
    generated: str,
    source: str,
    source_chunk: Chunk = None
) -> Dict[str, Any]:
    """
    Judge a response using RAGASMetrics.

    Returns dict with faithfulness, relevance (each with score and explanation),
    and source_chunk reference.
    """
    faith_data = metrics.compute_faithfulness_with_explanation(
        question=question,
        generated_answer=generated,
        source_content=source
    )
    relev_data = metrics.compute_relevance_with_explanation(
        question=question,
        expected_answer=expected,
        generated_answer=generated
    )

    return {
        "faithfulness": faith_data,
        "relevance": relev_data,
        "source_chunk": source_chunk
    }


def load_qa_dataset(config: Config):
    """Load QA dataset from eval/ folder."""
    path = Path(__file__).parent / "eval_dataset.json"
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_ollama_models_available(config: Config, models: List[str]) -> Tuple[List[str], List[str]]:
    """Check which models are available on Ollama.

    Returns:
        (available_models, missing_models)
    """
    try:
        response = requests.get(f"{config.ollama_url}/api/tags", timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Could not connect to Ollama at {config.ollama_url}")
            return models, []

        available = response.json().get('models', [])
        available_names = {m['name'] for m in available}

        available_models = []
        missing_models = []

        for model in models:
            if model in available_names or any(model in m for m in available_names):
                available_models.append(model)
            else:
                missing_models.append(model)

        return available_models, missing_models

    except Exception as e:
        print(f"⚠️ Error checking Ollama models: {e}")
        return models, []

def display_missing_models_help(missing_models: List[str]):
    """Display help message for installing missing models."""
    if not missing_models:
        return

    print("\n⚠️  The following models are not installed on Ollama:")
    for model in missing_models:
        print(f"  • {model}")

    print("\n📦 To install them, run:")
    for model in missing_models:
        print(f"  ollama pull {model}")

    print("\n💡 Note: Make sure Ollama is running before installing models.")
    print("   Run 'ollama serve' in another terminal if needed.\n")


def generate_comparison_json(
    results: Dict[str, Any],
    qa_pairs: List[Any],
    judge_model: str,
    provider: str,
    num_questions: int,
    summary_synthesis: str = "",
    run_timestamp: datetime = None
) -> Path:
    """Generate a single consolidated JSON report for all models."""
    models = list(results.keys())
    
    report_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "models": models,
            "provider": provider,
            "judge_model": judge_model,
            "num_questions": num_questions
        },
        "synthesis": summary_synthesis,
        "results": []
    }

    for i, qa in enumerate(qa_pairs):
        q_entry = {
            "question": qa["question"],
            "expected_answer": qa["expected_answer"],
            "source_chunk_ids": qa.get("source_chunk_ids", [qa["source_chunk_id"]] if "source_chunk_id" in qa else []),
            "model_responses": {}
        }
        
        for model in models:
            if i < len(results[model]["trials"]):
                res = results[model]["trials"][i]
                q_entry["model_responses"][model] = {
                    "answer": res["answer"],
                    "time": res["time"],
                    "wps": res["words_per_sec"],
                    "faithfulness": res["faith"],
                    "relevance": res["relev"]
                }
        
        report_data["results"].append(q_entry)

    # Save consolidated JSON
    report_path = get_generation_report_path(models, num_questions, timestamp=run_timestamp, format="json")

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    return report_path



def generate_html_report(results: Dict[str, Any], qa_pairs: List[Any], summary_synthesis: str, judge_model: str, chunks_map: Dict[str, Chunk] = None, models: List[str] = None, trials: int = 0, run_timestamp: datetime = None):
    timestamp_str = run_timestamp.strftime("%Y-%m-%d %H:%M:%S") if run_timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chunks_map = chunks_map or {}

    html = f"""
<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Comparison Report</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
        .prose-content {{ line-height: 1.6; }}
        .prose-content strong {{ font-weight: 600; color: #334155; }}
        .prose-content em {{ font-style: italic; color: #475569; }}
        .prose-content code {{ background-color: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: 'Monaco', monospace; }}
        .prose-content a {{ color: #4f46e5; text-decoration: underline; }}
        .prose-content a:hover {{ color: #4338ca; }}
        .chat-messages {{ display: flex; flex-direction: column; }}
        .chat-messages > div {{ animation: slideIn 0.3s ease-out; }}
        @keyframes slideIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body class="h-full">
    <div class="min-h-full py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-7xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-12">
                <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight sm:text-5xl">
                    📊 LLM Comparison Report
                </h1>
                <p class="mt-4 text-lg text-slate-600">
                    Generated on <span class="font-semibold text-indigo-600">{timestamp_str}</span> • Based on <span class="font-semibold text-indigo-600">{len(qa_pairs)}</span> test questions • Judge: <span class="font-semibold text-indigo-600">{escape_html(judge_model)}</span>
                </p>
            </div>

            <!-- Synthesis -->
            <div class="bg-indigo-50 border-l-4 border-indigo-500 p-8 rounded-xl shadow-sm mb-12">
                <div class="flex items-center mb-4">
                    <span class="text-2xl mr-3">📑</span>
                    <h2 class="text-2xl font-bold text-indigo-900">Judge's Conclusion</h2>
                </div>
                <div class="prose-content text-indigo-800 leading-relaxed text-base prose prose-indigo">
                    {markdown_to_html(summary_synthesis)}
                </div>
            </div>

            <!-- Charts Container -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6 flex items-center">
                        <span class="mr-2">🎯</span> Avg Faithfulness
                    </h3>
                    <div class="h-64"><canvas id="faithChart"></canvas></div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6 flex items-center">
                        <span class="mr-2">⚖️</span> Avg Relevance
                    </h3>
                    <div class="h-64"><canvas id="relevChart"></canvas></div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6 flex items-center">
                        <span class="mr-2">⚡</span> Speed (words/sec)
                    </h3>
                    <div class="h-64"><canvas id="speedChart"></canvas></div>
                </div>
            </div>

            <!-- Details Section -->
            <div class="space-y-12">
                <div class="flex items-center justify-between border-b border-slate-200 pb-4">
                    <h2 class="text-3xl font-bold text-slate-900">🔍 Details per Question</h2>
                    <span class="bg-slate-200 text-slate-700 px-3 py-1 rounded-full text-sm font-medium">
                        {len(qa_pairs)} questions
                    </span>
                </div>

                <div class="space-y-12">
    """

    for i, qa in enumerate(qa_pairs):
        chunk_ids = qa.get('source_chunk_ids', [qa['source_chunk_id']] if 'source_chunk_id' in qa else [])
        chunk_id = next((cid for cid in chunk_ids if cid in chunks_map), None) if chunk_ids else None
        source_button_id = f"source-toggle-{i}"
        source_content_id = f"source-content-{i}"

        html += f"""
                    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                        <div class="bg-slate-50 px-8 py-6 border-b border-slate-100">
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800 mb-2">
                                Question {i+1}
                            </span>
                            <div class="flex flex-col space-y-1 text-sm text-slate-600">
                                <div><span class="font-bold text-slate-900 mr-2">Cible :</span>{escape_html(qa['expected_answer'])}</div>
                            </div>

        """

        # Add source toggle button
        if chunk_id and chunk_id in chunks_map:
            html += f"""
                            <button class="mt-4 px-3 py-1 text-xs font-medium bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg transition" onclick="toggleSource('{source_content_id}', this)">
                                📌 Show source ({chunk_id[:20]}...)
                            </button>
            """

        html += """
                        </div>
        """

        # Add hidden source context
        if chunk_id and chunk_id in chunks_map:
            chunk = chunks_map[chunk_id]
            html += f"""
                        <div id="{source_content_id}" class="hidden px-8 py-4 bg-slate-100 border-b border-slate-200">
                            <p class="text-xs font-bold text-slate-700 uppercase tracking-wide mb-3">💬 Source Conversation</p>
                            {format_chunk_as_chat(chunk, source_content_id)}
                        </div>
            """

        html += """
                        <div class="p-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
        """
        for model in results.keys():
            res = results[model]['trials'][i]
            score_f = res['faith']['score']
            score_r = res['relev']['score']

            # Badge colors
            bg_f = "bg-green-100 text-green-800" if score_f > 0.8 else ("bg-yellow-100 text-yellow-800" if score_f > 0.4 else "bg-red-100 text-red-800")
            bg_r = "bg-green-100 text-green-800" if score_r > 0.8 else ("bg-yellow-100 text-yellow-800" if score_r > 0.4 else "bg-red-100 text-red-800")

            html += f"""
                            <div class="flex flex-col h-full bg-slate-50/50 rounded-xl p-6 border border-slate-100 hover:border-indigo-200 transition-colors">
                                <div class="flex items-center justify-between mb-4">
                                    <div class="flex items-center">
                                        <div class="h-10 w-10 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-lg mr-3 shadow-indigo-200 shadow-lg">
                                            🤖
                                        </div>
                                        <div>
                                            <h4 class="font-bold text-slate-900 leading-none">{escape_html(model)}</h4>
                                            <span class="text-xs text-slate-500 mt-1 block">
                                                {res['time']:.2f}s • {res['words_per_sec']:.1f} words/s
                                            </span>
                                        </div>
                                    </div>
                                    <div class="flex space-x-2">
                                        <span class="px-3 py-1 rounded-lg text-sm font-bold {bg_f}">Faithfulness: {score_f*100:.0f}%</span>
                                        <span class="px-3 py-1 rounded-lg text-sm font-bold {bg_r}">Relevance: {score_r*100:.0f}%</span>
                                    </div>
                                </div>

                                <div class="flex-grow bg-white p-4 rounded-lg border border-slate-100 mb-4 shadow-sm prose-content">
                                    {markdown_to_html(res['answer'])}
                                </div>

                                <div class="mt-auto space-y-2">
                                    <div class="bg-indigo-50/50 p-4 rounded-lg">
                                        <p class="text-xs font-bold text-indigo-900 uppercase tracking-tighter mb-1">Fidélité (Judge)</p>
                                        <p class="text-sm text-indigo-800 italic leading-snug">"{escape_html(res['faith']['explanation'])}"</p>
                                    </div>
                                    {f'''<div class="bg-emerald-50/50 p-4 rounded-lg">
                                        <p class="text-xs font-bold text-emerald-900 uppercase tracking-tighter mb-1">Pertinence (Judge)</p>
                                        <p class="text-sm text-emerald-800 italic leading-snug">"{escape_html(res['relev']['explanation'])}"</p>
                                    </div>''' if res['relev'].get('explanation') else ''}
                                </div>

                            </div>
            """
        html += """
                        </div>
                    </div>
        """

    # Add Charts Script
    models = list(results.keys())
    faiths = [sum(r['faith']['score'] for r in results[m]['trials'])/len(qa_pairs) for m in models]
    relevs = [sum(r['relev']['score'] for r in results[m]['trials'])/len(qa_pairs) for m in models]
    speeds = [results[m]['avg_speed'] for m in models]

    html += f"""
                </div>
            </div>
        </div>
    </div>

    <script>
        // Toggle source visibility
        function toggleSource(elementId, button) {{
            const element = document.getElementById(elementId);
            const isHidden = element.classList.contains('hidden');

            if (isHidden) {{
                element.classList.remove('hidden');
                button.textContent = button.textContent.replace('Show', 'Hide');
            }} else {{
                element.classList.add('hidden');
                button.textContent = button.textContent.replace('Hide', 'Show');
            }}
        }}

        const models = {json.dumps(models)};
        const createChart = (id, label, data, color) => {{
            new Chart(document.getElementById(id), {{
                type: 'bar',
                data: {{
                    labels: models,
                    datasets: [{{
                        label: label,
                        data: data,
                        backgroundColor: color,
                        borderRadius: 8,
                        borderWidth: 0
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: id === 'speedChart' ? null : 1,
                            grid: {{ display: true, color: '#f1f5f9' }},
                            ticks: {{ font: {{ size: 10 }} }}
                        }},
                        x: {{ grid: {{ display: false }} }}
                    }}
                }}
            }});
        }};
        createChart('faithChart', 'Faithfulness', {json.dumps(faiths)}, '#4f46e5');
        createChart('relevChart', 'Relevance', {json.dumps(relevs)}, '#10b981');
        createChart('speedChart', 'Words per second', {json.dumps(speeds)}, '#f59e0b');
    </script>
</body>
</html>
    """

    report_path = get_generation_report_path(models or list(results.keys()), trials or len(qa_pairs), timestamp=run_timestamp, format="html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return report_path

def run_comparison():
    parser = argparse.ArgumentParser(
        description="Evaluate GENERATION quality: compare how different LLMs answer questions (bypasses retrieval)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This evaluates LLM response quality independently from retrieval.
Each LLM receives the exact source chunk as context.

Metrics:
  - Faithfulness: How well the answer reflects the source content
  - Relevance: How well the answer addresses the question
  - Speed: Words per second generation rate

Examples:
    python -m eval.eval_generation                        # Use defaults
    python -m eval.eval_generation mistral neural-chat
    python -m eval.eval_generation qwen3:latest mistral --trials 20 --html
    python -m eval.eval_generation --models mistral,qwen3:latest --judge qwen3:latest
        """
    )
    parser.add_argument(
        "models",
        nargs="*",
        help="Model names to compare (space-separated). Default: qwen3:latest qwen2.5:3b"
    )
    parser.add_argument(
        "--models",
        type=str,
        dest="models_option",
        metavar="MODEL[,MODEL...]",
        help="Models to compare (comma-separated alternative syntax)"
    )
    parser.add_argument(
        "--num-questions",
        "--trials",
        type=int,
        default=3,
        help="Number of questions to evaluate (default: 3)"
    )

    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report"
    )
    parser.add_argument(
        "--judge",
        type=str,
        help="Model to use as judge (default: from config)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["ollama", "mlx"],
        default="ollama",
        help="LLM provider for run models (default: ollama)"
    )
    parser.add_argument(
        "--judge-provider",
        type=str,
        choices=["ollama", "mlx"],
        default=None,
        dest="judge_provider",
        help="LLM provider for judge model (default: same as --provider)"
    )
    args = parser.parse_args()

    # Parse models from either positional or --models argument
    models = args.models if args.models else []
    if args.models_option:
        models = args.models_option.split(',')

    # Default models if none provided
    if not models:
        models = ["qwen3:latest", "qwen2.5:3b"]
        print("ℹ️  No models specified. Using defaults: qwen3:latest, qwen2.5:3b")
        print()

    # Clean up model names (remove whitespace)
    models = [m.strip() for m in models if m.strip()]

    # Check that we have at least 2 models
    if len(models) < 2:
        parser.print_help()
        print("\n Error: Must specify at least 2 models to compare")
        print("   Example: python -m eval.eval_generation qwen3:latest mistral")
        return

    print("=" * 60)
    print("RAG Evaluation - Generation Quality")
    print("=" * 60)
    print()

    config = Config()

    # Judge model & provider
    judge_model = args.judge if args.judge else config.llm_model
    judge_provider_type = args.judge_provider if args.judge_provider else args.provider

    # Check Ollama availability for run models
    if args.provider == "ollama":
        print(f"Checking Ollama run models at {config.ollama_url}...")
        available, missing = check_ollama_models_available(config, models)

        if missing:
            display_missing_models_help(missing)
            available_test_models = [m for m in models if m in available]
            if not available_test_models:
                print("Error: No test models available. Please install at least one model.")
                return
            print(f"Continuing with available models: {', '.join(available_test_models)}\n")
            models = available_test_models
    else:
        print(f"Using {args.provider} provider for run models - skipping Ollama availability check")

    # Check Ollama availability for judge model
    if judge_provider_type == "ollama":
        _, judge_missing = check_ollama_models_available(config, [judge_model])
        if judge_missing:
            display_missing_models_help(judge_missing)
            print(f"❌ Error: Judge model '{judge_model}' is not available on Ollama.")
            return
    else:
        print(f"Using {judge_provider_type} provider for judge - skipping Ollama availability check")

    print(f"Using models: {', '.join(models)}")
    print(f"Using judge: {judge_model}")
    print(f"Run provider: {args.provider} | Judge provider: {judge_provider_type}")
    print()

    judge_metrics = create_judge(config, judge_model=judge_model, provider_type=judge_provider_type)
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    chunks_map = {c.chunk_id: c for c in chunks}

    dataset = load_qa_dataset(config)
    if not dataset:
        print("Error: Dataset not found. Run: python -m eval.generate_dataset 10")
        return

    num_questions = args.num_questions
    qa_pairs = dataset['qa_pairs'][:num_questions]
    results = {m: {"trials": [], "avg_speed": 0} for m in models}

    # Create provider instances
    providers = {m: create_provider(config, m, args.provider) for m in models}
    judge_provider = create_provider(config, judge_model, judge_provider_type)

    # Phase 1: Generation
    print("\n" + "="*60)
    print("🚀 PHASE 1: GENERATION (Batch per model)")
    print("="*60)

    # Initialize result structure
    for model in models:
        for _ in range(len(qa_pairs)):
            results[model]["trials"].append({
                "answer": "",
                "time": 0,
                "words_per_sec": 0,
                "faith": {},
                "relev": {}
            })

    for model in models:
        print(f"\n🤖 Running Generation for model: {model}")
        provider_instance = providers[model]
        
        for i, qa in enumerate(qa_pairs):
            print(f"  Question [{i+1}/{len(qa_pairs)}]...", end="", flush=True)
            
            # Find the chunk
            chunk_ids = qa.get('source_chunk_ids', [qa['source_chunk_id']] if 'source_chunk_id' in qa else [])
            chunk = next((chunks_map[cid] for cid in chunk_ids if cid in chunks_map), None)
            content = chunk.content if chunk else ""
            
            start = time.time()
            try:
                prompt = get_eval_prompt(qa['question'], content)
                answer = provider_instance.generate(
                    [{"role": "user", "content": prompt}],
                    timeout=180
                )
                duration = time.time() - start
                word_count = len(answer.split())
                wps = word_count / duration if duration > 0 else 0
                
                results[model]["trials"][i].update({
                    "answer": answer,
                    "time": duration,
                    "words_per_sec": wps
                })
                print(f" Done ({duration:.2f}s)")
                
            except Exception as e:
                print(f" Failed ({e})")
                results[model]["trials"][i].update({
                    "answer": f"Error: {e}",
                    "time": 0,
                    "words_per_sec": 0
                })

    # Phase 2: Judging
    print("\n" + "="*60)
    print("⚖️  PHASE 2: JUDGING (Batch)")
    print("="*60)

    for i, qa in enumerate(qa_pairs):
        print(f"\n[{i+1}/{len(qa_pairs)}] Judging Question: {qa['question']}")
        
        # Find the chunk
        chunk_ids = qa.get('source_chunk_ids', [qa['source_chunk_id']] if 'source_chunk_id' in qa else [])
        chunk = next((chunks_map[cid] for cid in chunk_ids if cid in chunks_map), None)
        content = chunk.content if chunk else ""
        
        for model in models:
            res_entry = results[model]["trials"][i]
            answer = res_entry["answer"]
            
            if answer.startswith("Error:"):
                # Skip judging errors
                res_entry["faith"] = {"score": 0, "explanation": "Generation failed"}
                res_entry["relev"] = {"score": 0, "explanation": "Generation failed"}
                continue
                
            print(f"  👨‍⚖️  Judging {model}...", end="", flush=True)
            
            try:
                j_res = judge_response(judge_metrics, qa['question'], qa['expected_answer'], answer, content, chunk)
                res_entry["faith"] = j_res["faithfulness"]
                res_entry["relev"] = j_res["relevance"]
                print(f" Faith: {j_res['faithfulness']['score']:.2f} | Relev: {j_res['relevance']['score']:.2f}")
            except Exception as e:
                print(f" Failed ({e})")
                res_entry["faith"] = {"score": 0, "explanation": f"Judge error: {e}"}
                res_entry["relev"] = {"score": 0, "explanation": f"Judge error: {e}"}

    # Final Synthesis in French
    print("\n✍️ Génération de la synthèse finale...")
    synth_prompt = f"Tu es un juge expert. Compare ces résultats pour les modèles {models} et fournis une conclusion humaine détaillée sur leurs forces et faiblesses respectives basées sur ces tests de génération RAG.\n\nDonnées : {json.dumps(results)}"
    synth_resp = judge_provider.generate(
        [{"role": "user", "content": synth_prompt}],
        timeout=180
    )


    # Calculate avg speed
    for m in models:
        results[m]["avg_speed"] = sum(t["words_per_sec"] for t in results[m]["trials"]) / len(qa_pairs)

    # Use a single timestamp for all reports in this run
    run_timestamp = datetime.now()

    # Generate consolidated JSON report
    print("\n📊 Génération du rapport JSON consolidé...")
    json_path = generate_comparison_json(results, qa_pairs, judge_model, args.provider, num_questions, synth_resp, run_timestamp=run_timestamp)
    print(f"  ✅ Rapport JSON enregistré : {json_path}")

    # Optionally generate HTML report
    if args.html:
        html_path = generate_html_report(results, qa_pairs, synth_resp, judge_model, chunks_map, models=models, trials=num_questions, run_timestamp=run_timestamp)
        print(f"✅ Rapport HTML généré : {html_path}")


    print("\n" + synth_resp)

if __name__ == "__main__":
    run_comparison()