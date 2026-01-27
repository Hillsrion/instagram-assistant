"""
Script to compare Generation Quality of different LLMs on the evaluation dataset.
This bypasses retrieval and provides the exact source chunk as context.
Generates an interactive HTML report with Tailwind CSS and visualizations.
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
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.chunker import ConversationChunker, Chunk
from eval.metrics import RAGASMetrics

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

    # Bold: **text** -> <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Italic: *text* -> <em>text</em>
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

    # Inline code: `text` -> <code>text</code>
    text = re.sub(r'`([^`]+)`', r'<code class="bg-gray-100 px-2 py-0.5 rounded">\1</code>', text)

    # Code blocks: ```code``` -> <pre><code>code</code></pre>
    text = re.sub(r'```(.+?)```', r'<pre class="bg-gray-100 p-3 rounded overflow-x-auto"><code>\1</code></pre>', text, flags=re.DOTALL)

    # Links: [text](url) -> <a>text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="text-indigo-600 hover:underline">\1</a>', text)

    # Line breaks
    text = text.replace('\n', '<br>')

    return text

def format_chunk_as_chat(chunk: Chunk) -> str:
    """Format a chunk with its messages as a chat-like display."""
    html = f"""
    <div class="bg-slate-50 rounded-lg p-4 border border-slate-200 mb-4">
        <div class="mb-3 pb-3 border-b border-slate-200">
            <div class="text-xs font-bold text-slate-600 uppercase tracking-wide mb-1">Source du Chunk</div>
            <div class="flex flex-wrap gap-2">
                <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-indigo-100 text-indigo-800">
                    ID: {escape_html(chunk.chunk_id)}
                </span>
                <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800">
                    {', '.join(chunk.participants) if chunk.participants else 'N/A'}
                </span>
                <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-800">
                    {chunk.date_start} → {chunk.date_end}
                </span>
            </div>
        </div>

        <div class="space-y-2 max-h-96 overflow-y-auto">
    """

    # Parse the content to find messages in a structured way
    # The content typically contains newlines with timestamp and author info
    lines = chunk.content.split('\n')

    for line in lines:
        if not line.strip():
            continue

        # Try to identify message pattern (usually "Author: content" or just "content")
        # Format a reasonable display for chat-like messages
        parts = line.split(':', 1)
        if len(parts) == 2 and len(parts[0]) < 50:  # Likely author name
            author = escape_html(parts[0].strip())
            content = escape_html(parts[1].strip())

            # Alternate colors for different participants
            author_color = "bg-indigo-100 text-indigo-800" if author[0].isupper() else "bg-green-100 text-green-800"

            html += f"""
            <div class="flex gap-2 mb-2">
                <div class="text-xs font-bold {author_color} px-2 py-1 rounded whitespace-nowrap">
                    {author}
                </div>
                <div class="text-sm text-slate-700 flex-1">
                    {content}
                </div>
            </div>
            """
        else:
            html += f"""
            <div class="text-sm text-slate-600 italic pl-2 border-l-2 border-slate-300">
                {escape_html(line.strip())}
            </div>
            """

    html += """
        </div>
    </div>
    """

    return html

class AdvancedJudge:
    def __init__(self, config: Config):
        self.config = config
        self.metrics = RAGASMetrics(config)

    def judge(self, question: str, expected: str, generated: str, source: str, source_chunk: Chunk = None) -> Dict[str, Any]:
        """Get score AND explanation from judge, with source tracking."""
        faith_prompt = """Tu es un évaluateur expert. Évalue la FIDÉLITÉ (0-1).
QUESTION: {question}
RÉPONSE ATTENDUE: {expected}
RÉPONSE GÉNÉRÉE: {generated}
SOURCES: {sources}
Réponds en JSON: {{"score": float, "explanation": "..."}}"""

        relev_prompt = """Tu es un évaluateur expert. Évalue la PERTINENCE (0-1).
QUESTION: {question}
RÉPONSE ATTENDUE: {expected}
RÉPONSE GÉNÉRÉE: {generated}
Réponds en JSON: {{"score": float, "explanation": "..."}}"""

        faith_data = self._call_judge(faith_prompt.format(
            question=question, expected=expected, generated=generated, sources=source[:2000]
        ))
        relev_data = self._call_judge(relev_prompt.format(
            question=question, expected=expected, generated=generated
        ))

        return {
            "faithfulness": faith_data,
            "relevance": relev_data,
            "source_chunk": source_chunk
        }

    def _call_judge(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.config.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        try:
            response = requests.post(f"{self.config.ollama_url}/api/chat", json=payload, timeout=120)
            response.raise_for_status()
            content = response.json()["message"]["content"].strip()
            
            import re
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            return {"score": 0.5, "explanation": f"Erreur de jugement: {e}"}
        return {"score": 0.5, "explanation": "Impossible de parser le jugement."}

def load_qa_dataset(config: Config):
    path = config.index_dir / "eval_dataset.json"
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_html_report(results: Dict[str, Any], qa_pairs: List[Any], summary_synthesis: str, chunks_map: Dict[str, Chunk] = None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chunks_map = chunks_map or {}

    html = f"""
<!DOCTYPE html>
<html lang="fr" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport de Comparaison LLM</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
        .prose-content {{ line-height: 1.6; }}
    </style>
</head>
<body class="h-full">
    <div class="min-h-full py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-7xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-12">
                <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight sm:text-5xl">
                    📊 Rapport de Comparaison LLM
                </h1>
                <p class="mt-4 text-lg text-slate-600">
                    Généré le <span class="font-semibold text-indigo-600">{timestamp}</span> • Basé sur <span class="font-semibold text-indigo-600">{len(qa_pairs)}</span> questions de test
                </p>
            </div>

            <!-- Synthesis -->
            <div class="bg-indigo-50 border-l-4 border-indigo-500 p-8 rounded-xl shadow-sm mb-12">
                <div class="flex items-center mb-4">
                    <span class="text-2xl mr-3">📑</span>
                    <h2 class="text-2xl font-bold text-indigo-900">Conclusion du Juge</h2>
                </div>
                <div class="prose-content text-indigo-800 leading-relaxed text-lg">
                    {markdown_to_html(summary_synthesis)}
                </div>
            </div>

            <!-- Charts Container -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6 flex items-center">
                        <span class="mr-2">🎯</span> Moyenne Faithfulness
                    </h3>
                    <div class="h-64"><canvas id="faithChart"></canvas></div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6 flex items-center">
                        <span class="mr-2">⚖️</span> Moyenne Relevance
                    </h3>
                    <div class="h-64"><canvas id="relevChart"></canvas></div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6 flex items-center">
                        <span class="mr-2">⚡</span> Vitesse (mots/sec)
                    </h3>
                    <div class="h-64"><canvas id="speedChart"></canvas></div>
                </div>
            </div>

            <!-- Details Section -->
            <div class="space-y-12">
                <div class="flex items-center justify-between border-b border-slate-200 pb-4">
                    <h2 class="text-3xl font-bold text-slate-900">🔍 Détails par Question</h2>
                    <span class="bg-slate-200 text-slate-700 px-3 py-1 rounded-full text-sm font-medium">
                        {len(qa_pairs)} questions
                    </span>
                </div>

                <div class="space-y-12">
    """

    for i, qa in enumerate(qa_pairs):
        html += f"""
                    <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                        <div class="bg-slate-50 px-8 py-6 border-b border-slate-100">
                            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800 mb-2">
                                Question {i+1}
                            </span>
                            <h3 class="text-xl font-bold text-slate-900 mb-2">{escape_html(qa['question'])}</h3>
                            <div class="flex items-start text-sm text-slate-600">
                                <span class="font-bold text-slate-900 mr-2">Cible:</span>
                                <span>{escape_html(qa['expected_answer'])}</span>
                            </div>
                        </div>
        """

        # Add source context
        chunk_id = qa.get('source_chunk_id')
        if chunk_id and chunk_id in chunks_map:
            chunk = chunks_map[chunk_id]
            html += f"""
                        <div class="px-8 py-4 bg-slate-100 border-b border-slate-200">
                            <p class="text-xs font-bold text-slate-700 uppercase tracking-wide mb-2">📌 Source</p>
                            {format_chunk_as_chat(chunk)}
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
                                                {res['time']:.2f}s • {res['words_per_sec']:.1f} mots/s
                                            </span>
                                        </div>
                                    </div>
                                    <div class="flex space-x-2">
                                        <span class="px-3 py-1 rounded-lg text-sm font-bold {bg_f}">Fidélité: {score_f*100:.0f}%</span>
                                        <span class="px-3 py-1 rounded-lg text-sm font-bold {bg_r}">Pertinence: {score_r*100:.0f}%</span>
                                    </div>
                                </div>

                                <div class="flex-grow bg-white p-4 rounded-lg border border-slate-100 mb-4 shadow-sm prose-content">
                                    {markdown_to_html(res['answer'])}
                                </div>

                                <div class="mt-auto bg-indigo-50/50 p-4 rounded-lg">
                                    <p class="text-xs font-bold text-indigo-900 uppercase tracking-tighter mb-1">Observation du Juge</p>
                                    <p class="text-sm text-indigo-800 italic leading-snug">"{escape_html(res['faith']['explanation'])}"</p>
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
        createChart('speedChart', 'Mots par seconde', {json.dumps(speeds)}, '#f59e0b');
    </script>
</body>
</html>
    """

    report_path = Path("rag_data/comparison_report.html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return report_path

def run_comparison():
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--html", action="store_true")
    args = parser.parse_args()

    config = Config()
    judge = AdvancedJudge(config)
    chunker = ConversationChunker(config)
    chunks = chunker.load_chunks()
    chunks_map = {c.chunk_id: c for c in chunks}

    dataset = load_qa_dataset(config)
    if not dataset:
        print("Erreur: Dataset non trouvé.")
        return

    qa_pairs = dataset['qa_pairs'][:args.trials]
    results = {m: {"trials": [], "avg_speed": 0} for m in args.models}

    for i, qa in enumerate(qa_pairs):
        print(f"\n[{i+1}/{len(qa_pairs)}] Question: {qa['question']}")

        # Find the chunk
        chunk = chunks_map.get(qa['source_chunk_id'])
        content = chunk.content if chunk else ""

        for model in args.models:
            print(f"  🤖 {model}...", end="", flush=True)

            start = time.time()
            try:
                resp = requests.post(f"{config.ollama_url}/api/chat", json={
                    "model": model,
                    "messages": [{"role": "user", "content": f"Contexte:\n{content}\n\nQuestion: {qa['question']}"}],
                    "stream": False
                }, timeout=180).json()
            except Exception as e:
                print(f" Failed ({e})")
                results[model]["trials"].append({
                    "answer": f"Error: {e}",
                    "time": 0,
                    "words_per_sec": 0,
                    "faith": {"score": 0, "explanation": "Request failed"},
                    "relev": {"score": 0, "explanation": "Request failed"}
                })
                continue

            duration = time.time() - start
            answer = resp["message"]["content"]

            word_count = len(answer.split())
            wps = word_count / duration if duration > 0 else 0

            # Judge with source chunk
            j_res = judge.judge(qa['question'], qa['expected_answer'], answer, content, chunk)

            results[model]["trials"].append({
                "answer": answer,
                "time": duration,
                "words_per_sec": wps,
                "faith": j_res["faithfulness"],
                "relev": j_res["relevance"]
            })
            print(f" Done ({wps:.1f} words/s)")

    # Final Synthesis
    print("\n✍️ Génération de la synthèse finale...")
    synth_prompt = f"Tu es un juge expert. Compare ces résultats pour {args.models} et donne une conclusion humaine et détaillée sur leurs forces et faiblesses respectives basées sur ces tests.\n\nDonnées: {json.dumps(results)}"
    synth_resp = requests.post(f"{config.ollama_url}/api/chat", json={
        "model": "qwen3:latest",
        "messages": [{"role": "user", "content": synth_prompt}],
        "stream": False
    }).json()["message"]["content"]

    # Calculate avg speed
    for m in args.models:
        results[m]["avg_speed"] = sum(t["words_per_sec"] for t in results[m]["trials"]) / len(qa_pairs)

    if args.html:
        path = generate_html_report(results, qa_pairs, synth_resp, chunks_map)
        print(f"\n✅ Rapport HTML généré: {path}")

    print("\n" + synth_resp)

if __name__ == "__main__":
    run_comparison()
