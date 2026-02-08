"""
Binary Routing System Evaluation.

Validates the new binary routing architecture (fast-path vs agent-path)
introduced in commit b3c7683. Tests routing accuracy, latency, and quality
for both paths.

Usage:
    python -m eval.eval_routing                    # Run full evaluation
    python -m eval.eval_routing --type simple_fact # Test specific types
    python -m eval.eval_routing --html             # Generate HTML report
    python -m eval.eval_routing --trials 10        # Limit test queries
"""

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.core.config import Config
from rag_pipeline.chat.agent import AgentRunner
from rag_pipeline.chat.chat import ChatBot
from rag_pipeline.query.retriever import Retriever
from rag_pipeline.indexing.embeddings import EmbeddingModel
from rag_pipeline.indexing.vector_store import VectorStore
from rag_pipeline.query.query_analyzer import QueryAnalyzer
from api.routing import should_use_agent
from eval.core import RAGASMetrics


# ============================================================
# Test Dataset - Routing-Focused Queries
# ============================================================

TEST_QUERIES = [
    # Fast-path queries (mode=retrieval, intent=specific_fact)
    {
        "query": "Est-ce qu'on a parlé de voyages ?",
        "expected_path": "fast",
        "expected_mode": "retrieval",
        "expected_intent": "specific_fact",
        "type": "simple_fact",
        "description": "Simple factual verification query"
    },
    {
        "query": "Qui est Ayoub ?",
        "expected_path": "fast",
        "expected_mode": "retrieval",
        "expected_intent": "specific_fact",
        "type": "simple_fact",
        "description": "Direct fact lookup about a person"
    },
    {
        "query": "De quoi on a parlé avec mes amis récemment ?",
        "expected_path": "fast",
        "expected_mode": "retrieval",
        "expected_intent": "specific_fact",
        "type": "simple_fact",
        "description": "Recent conversation search"
    },
    {
        "query": "J'ai déjà parlé d'un taxi ?",
        "expected_path": "fast",
        "expected_mode": "retrieval",
        "expected_intent": "specific_fact",
        "type": "simple_fact",
        "description": "Existence check (not counting)"
    },

    # Agent-path queries (analytics)
    {
        "query": "Combien de messages j'ai échangé en total ?",
        "expected_path": "agent",
        "expected_mode": "analytics",
        "expected_intent": "specific_fact",  # Analytics uses specific_fact too
        "type": "analytics",
        "description": "Global message count"
    },
    {
        "query": "Combien de fois on a parlé de sport ?",
        "expected_path": "agent",
        "expected_mode": "analytics",
        "expected_intent": "specific_fact",
        "type": "analytics",
        "description": "Topic occurrence count"
    },
    {
        "query": "Lister mes contacts",
        "expected_path": "agent",
        "expected_mode": "analytics",
        "expected_intent": "specific_fact",
        "type": "analytics",
        "description": "Contact enumeration"
    },

    # Agent-path queries (broad_summary)
    {
        "query": "Résume mes discussions récentes",
        "expected_path": "agent",
        "expected_mode": "retrieval",
        "expected_intent": "broad_summary",
        "type": "broad_summary",
        "description": "Broad conversation summary"
    },
    {
        "query": "De quoi on a parlé ce mois-ci ?",
        "expected_path": "agent",
        "expected_mode": "retrieval",
        "expected_intent": "broad_summary",
        "type": "broad_summary",
        "description": "Thematic overview query"
    },

    # Agent-path queries (complex_reasoning)
    {
        "query": "Résume mes discussions avec Marie et dis-moi combien d'échanges on a eus",
        "expected_path": "agent",
        "expected_mode": "retrieval",
        "expected_intent": "complex_reasoning",
        "type": "complex_reasoning",
        "description": "Composite query requiring multiple tools"
    },
    {
        "query": "Compare mes échanges avec Ayoub et Marie",
        "expected_path": "agent",
        "expected_mode": "retrieval",
        "expected_intent": "complex_reasoning",
        "type": "complex_reasoning",
        "description": "Multi-entity comparison"
    },

    # Edge cases
    {
        "query": "Bonjour, comment ça va ?",
        "expected_path": "agent",  # Agent handles greetings directly
        "expected_mode": "retrieval",  # Default fallback
        "expected_intent": "specific_fact",
        "type": "direct_answer",
        "description": "Greeting - no tool needed"
    },
    {
        "query": "Quelle est la date d'aujourd'hui ?",
        "expected_path": "agent",  # Requires get_todays_date tool
        "expected_mode": "retrieval",
        "expected_intent": "specific_fact",
        "type": "utility",
        "description": "Utility query requiring tool"
    },
]


@dataclass
class RoutingEvalResult:
    """Evaluation result for a single query in routing context."""
    query: str
    query_type: str
    description: str

    # Expected routing
    expected_path: str
    expected_mode: str
    expected_intent: str

    # Actual analysis
    actual_mode: str
    actual_intent: str
    actual_path: str

    # Routing accuracy
    routing_correct: bool
    analysis_correct: bool

    # Execution results
    answer: str
    latency: float
    success: bool

    # Agent-specific (if agent path)
    agent_steps: int = 0
    agent_tools_used: List[str] = None

    # Quality scores
    faithfulness_score: float = 0.0
    relevance_score: float = 0.0

    # Context metadata
    sources_count: int = 0
    confidence_score: float = 0.0

    def to_dict(self) -> Dict:
        result = asdict(self)
        if result['agent_tools_used'] is None:
            result['agent_tools_used'] = []
        return result


def initialize_components(config: Config, model: str = None, provider_type: str = "ollama"):
    """Initialize RAG components for both paths."""
    print("📦 Loading RAG components...")

    if model:
        config.llm_model = model
        # For evaluation, we might want to use the same model for everything 
        # unless specifically separated.
        config.llm_model_fast = model

    embedding_model = EmbeddingModel(config)
    vector_store = VectorStore(config)

    if not vector_store.load():
        print("❌ Vector store not found. Run scripts/setup/setup_rag.py first.")
        sys.exit(1)

    retriever = Retriever(embedding_model, vector_store, config)
    chatbot = ChatBot(retriever, config, provider_type=provider_type)
    query_analyzer = QueryAnalyzer(config, provider_type=provider_type)
    agent = AgentRunner(config, retriever, provider_type=provider_type)
    metrics = RAGASMetrics(config, provider_type=provider_type)

    print(f"✅ Loaded {vector_store.size} vectors")
    return retriever, chatbot, query_analyzer, agent, metrics


def execute_fast_path(
    query: str,
    analysis,
    retriever: Retriever,
    chatbot: ChatBot
) -> Dict[str, Any]:
    """Execute the fast-path (direct retrieval) for a query."""
    start = time.time()

    try:
        # Use analysis parameters
        context = retriever.retrieve(
            query=analysis.rewritten_query,
            top_k=analysis.top_k,
            use_reranking=analysis.use_reranking,
            use_hybrid=True,
            expand_context=analysis.expand_context,
            date_start=analysis.date_start,
            date_end=analysis.date_end
        )

        # Generate answer
        response = ""
        for chunk in chatbot.chat_stream(query, context.formatted_context):
            response += chunk

        # Format sources
        sources = []
        if context.results:
            for r in context.results:
                sources.append({
                    "rank": r.rank,
                    "file": r.chunk.file_source,
                    "participants": r.chunk.participants,
                    "score": round(r.final_score, 2)
                })

        return {
            "answer": response,
            "latency": time.time() - start,
            "success": True,
            "sources": sources,
            "sources_count": len(sources),
            "confidence_score": context.max_confidence_score,
            "agent_steps": 0,
            "agent_tools_used": []
        }

    except Exception as e:
        return {
            "answer": f"Error: {e}",
            "latency": time.time() - start,
            "success": False,
            "sources": [],
            "sources_count": 0,
            "confidence_score": 0.0,
            "agent_steps": 0,
            "agent_tools_used": []
        }


def execute_agent_path(
    query: str,
    analysis,
    agent: AgentRunner
) -> Dict[str, Any]:
    """Execute the agent path for a query."""
    try:
        result = agent.run(query, history=[], analysis=analysis)

        # Extract tools used
        tools_used = [s.action for s in result.steps if s.action]

        return {
            "answer": result.answer,
            "latency": result.total_time,
            "success": result.success,
            "sources": result.sources,
            "sources_count": len(result.sources),
            "confidence_score": 0.0,  # Agent doesn't expose confidence directly
            "agent_steps": len(result.steps),
            "agent_tools_used": tools_used
        }

    except Exception as e:
        return {
            "answer": f"Error: {e}",
            "latency": 0.0,
            "success": False,
            "sources": [],
            "sources_count": 0,
            "confidence_score": 0.0,
            "agent_steps": 0,
            "agent_tools_used": []
        }


def evaluate_query(
    test_query: Dict,
    retriever: Retriever,
    chatbot: ChatBot,
    query_analyzer: QueryAnalyzer,
    agent: AgentRunner,
    metrics: RAGASMetrics
) -> RoutingEvalResult:
    """Evaluate a single query through the routing system."""
    query = test_query["query"]

    # Step 1: Query Analysis
    analysis = query_analyzer.analyze(query, history=[])

    # Step 2: Routing Decision
    actual_path = "agent" if should_use_agent(analysis) else "fast"

    # Step 3: Check Routing Accuracy
    routing_correct = (actual_path == test_query["expected_path"])
    analysis_correct = (
        analysis.mode == test_query["expected_mode"] and
        analysis.intent == test_query["expected_intent"]
    )

    # Step 4: Execute Appropriate Path
    if actual_path == "fast":
        exec_result = execute_fast_path(query, analysis, retriever, chatbot)
    else:
        exec_result = execute_agent_path(query, analysis, agent)

    # Step 5: Quality Evaluation (simplified - no ground truth)
    # We could enhance this by comparing against expected answer patterns
    faithfulness_score = 0.5  # Placeholder
    relevance_score = 0.5     # Placeholder

    return RoutingEvalResult(
        query=query,
        query_type=test_query["type"],
        description=test_query["description"],
        expected_path=test_query["expected_path"],
        expected_mode=test_query["expected_mode"],
        expected_intent=test_query["expected_intent"],
        actual_mode=analysis.mode,
        actual_intent=analysis.intent,
        actual_path=actual_path,
        routing_correct=routing_correct,
        analysis_correct=analysis_correct,
        answer=exec_result["answer"],
        latency=exec_result["latency"],
        success=exec_result["success"],
        agent_steps=exec_result["agent_steps"],
        agent_tools_used=exec_result["agent_tools_used"],
        faithfulness_score=faithfulness_score,
        relevance_score=relevance_score,
        sources_count=exec_result["sources_count"],
        confidence_score=exec_result["confidence_score"]
    )


def generate_html_report(results: List[RoutingEvalResult], summary: Dict) -> Path:
    """Generate HTML routing evaluation report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate metrics
    routing_accuracy = sum(1 for r in results if r.routing_correct) / len(results) * 100
    analysis_accuracy = sum(1 for r in results if r.analysis_correct) / len(results) * 100

    fast_path_results = [r for r in results if r.actual_path == "fast"]
    agent_path_results = [r for r in results if r.actual_path == "agent"]

    fast_avg_latency = sum(r.latency for r in fast_path_results) / len(fast_path_results) if fast_path_results else 0
    agent_avg_latency = sum(r.latency for r in agent_path_results) / len(agent_path_results) if agent_path_results else 0
    agent_avg_steps = sum(r.agent_steps for r in agent_path_results) / len(agent_path_results) if agent_path_results else 0

    overall_success_rate = sum(1 for r in results if r.success) / len(results) * 100

    html = f"""
<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Routing System Evaluation</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="h-full">
    <div class="min-h-full py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-6xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-12">
                <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight">
                    🎯 Binary Routing System Evaluation
                </h1>
                <p class="mt-4 text-lg text-slate-600">
                    Generated on <span class="font-semibold text-indigo-600">{timestamp}</span> •
                    {len(results)} queries tested
                </p>
                <p class="mt-2 text-sm text-slate-500">
                    Fast-path (direct retrieval) vs Agent-path (ReAct agent)
                </p>
            </div>

            <!-- Summary Cards -->
            <div class="grid grid-cols-1 md:grid-cols-5 gap-6 mb-12">
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-medium text-slate-500 uppercase">Routing Accuracy</h3>
                    <p class="text-3xl font-bold text-green-600">{routing_accuracy:.0f}%</p>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-medium text-slate-500 uppercase">Fast-Path Latency</h3>
                    <p class="text-3xl font-bold text-slate-900">{fast_avg_latency:.2f}s</p>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-medium text-slate-500 uppercase">Agent Latency</h3>
                    <p class="text-3xl font-bold text-indigo-600">{agent_avg_latency:.2f}s</p>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-medium text-slate-500 uppercase">Avg Agent Steps</h3>
                    <p class="text-3xl font-bold text-slate-900">{agent_avg_steps:.1f}</p>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-medium text-slate-500 uppercase">Success Rate</h3>
                    <p class="text-3xl font-bold text-green-600">{overall_success_rate:.0f}%</p>
                </div>
            </div>

            <!-- Charts -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-4">⏱️ Latency by Path</h3>
                    <canvas id="latencyChart" height="200"></canvas>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-4">📊 Routing Distribution</h3>
                    <canvas id="distributionChart" height="200"></canvas>
                </div>
            </div>

            <!-- Confusion Matrix -->
            <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-12">
                <h3 class="text-lg font-bold text-slate-900 mb-4">🎯 Routing Confusion Matrix</h3>
                <table class="min-w-full divide-y divide-slate-200">
                    <thead>
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">Expected / Actual</th>
                            <th class="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase">Fast-Path</th>
                            <th class="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase">Agent-Path</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-200">
    """

    # Compute confusion matrix
    confusion = {
        "fast->fast": sum(1 for r in results if r.expected_path == "fast" and r.actual_path == "fast"),
        "fast->agent": sum(1 for r in results if r.expected_path == "fast" and r.actual_path == "agent"),
        "agent->fast": sum(1 for r in results if r.expected_path == "agent" and r.actual_path == "fast"),
        "agent->agent": sum(1 for r in results if r.expected_path == "agent" and r.actual_path == "agent"),
    }

    html += f"""
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">Fast-Path</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-green-600 font-bold">{confusion['fast->fast']}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-red-600">{confusion['fast->agent']}</td>
                        </tr>
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">Agent-Path</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-red-600">{confusion['agent->fast']}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-green-600 font-bold">{confusion['agent->agent']}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Details -->
            <div class="space-y-8">
                <h2 class="text-2xl font-bold text-slate-900 border-b border-slate-200 pb-4">
                    📝 Detailed Results
                </h2>
    """

    for i, r in enumerate(results):
        type_badge_color = {
            "simple_fact": "bg-blue-100 text-blue-800",
            "analytics": "bg-purple-100 text-purple-800",
            "broad_summary": "bg-orange-100 text-orange-800",
            "complex_reasoning": "bg-red-100 text-red-800",
            "direct_answer": "bg-green-100 text-green-800",
            "utility": "bg-yellow-100 text-yellow-800"
        }.get(r.query_type, "bg-slate-100 text-slate-800")

        path_badge = "✅" if r.routing_correct else "❌"
        path_color = "text-green-600" if r.routing_correct else "text-red-600"

        tools_str = ", ".join(r.agent_tools_used) if r.agent_tools_used else "None"

        html += f"""
                <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <div class="bg-slate-50 px-6 py-4 border-b border-slate-100">
                        <div class="flex items-center justify-between">
                            <div>
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {type_badge_color} mr-2">
                                    {r.query_type}
                                </span>
                                <span class="text-sm text-slate-500">{r.description}</span>
                            </div>
                            <span class="text-sm {path_color} font-bold">{path_badge} Routing</span>
                        </div>
                        <h3 class="text-lg font-bold text-slate-900 mt-2">{r.query}</h3>
                    </div>

                    <div class="p-6">
                        <div class="grid grid-cols-3 gap-4 mb-4">
                            <div>
                                <p class="text-xs text-slate-500">Expected Path</p>
                                <p class="text-sm font-medium text-slate-900">{r.expected_path}</p>
                            </div>
                            <div>
                                <p class="text-xs text-slate-500">Actual Path</p>
                                <p class="text-sm font-medium {path_color}">{r.actual_path}</p>
                            </div>
                            <div>
                                <p class="text-xs text-slate-500">Latency</p>
                                <p class="text-sm font-medium text-slate-900">{r.latency:.2f}s</p>
                            </div>
                        </div>

                        <div class="grid grid-cols-2 gap-4 mb-4">
                            <div>
                                <p class="text-xs text-slate-500">Analysis (mode/intent)</p>
                                <p class="text-sm font-mono text-slate-700">{r.actual_mode} / {r.actual_intent}</p>
                            </div>
                            <div>
                                <p class="text-xs text-slate-500">Agent Steps / Tools</p>
                                <p class="text-sm text-slate-700">{r.agent_steps} steps • {tools_str}</p>
                            </div>
                        </div>

                        <div>
                            <p class="text-xs text-slate-500 mb-2">Answer Preview</p>
                            <p class="text-sm text-slate-600 bg-slate-50 p-3 rounded-lg">
                                {r.answer[:300]}{'...' if len(r.answer) > 300 else ''}
                            </p>
                        </div>
                    </div>
                </div>
        """

    # Chart data
    query_labels = [f"Q{i+1}" for i in range(len(results))]
    latencies = [r.latency for r in results]
    path_colors = ['#6366f1' if r.actual_path == 'agent' else '#94a3b8' for r in results]

    # Distribution data
    fast_count = len(fast_path_results)
    agent_count = len(agent_path_results)

    html += f"""
            </div>
        </div>
    </div>

    <script>
        // Latency chart
        new Chart(document.getElementById('latencyChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(query_labels)},
                datasets: [{{
                    label: 'Latency',
                    data: {json.dumps(latencies)},
                    backgroundColor: {json.dumps(path_colors)},
                    borderRadius: 4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                return 'Latency: ' + context.parsed.y.toFixed(2) + 's';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{ beginAtZero: true, title: {{ display: true, text: 'Seconds' }} }}
                }}
            }}
        }});

        // Distribution pie chart
        new Chart(document.getElementById('distributionChart'), {{
            type: 'pie',
            data: {{
                labels: ['Fast-Path', 'Agent-Path'],
                datasets: [{{
                    data: [{fast_count}, {agent_count}],
                    backgroundColor: ['#94a3b8', '#6366f1'],
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ position: 'top' }}
                }}
            }}
        }});
    </script>
</body>
</html>
    """

    report_dir = Path(__file__).parent / "results" / "eval_routing"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"routing_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return report_path


def run_evaluation(
    trials: int = None,
    query_type: str = None,
    generate_html: bool = False,
    model: str = None,
    provider_type: str = "ollama"
):
    """Run the routing system evaluation."""
    print("=" * 60)
    print("Binary Routing System Evaluation")
    print("=" * 60)
    print()

    config = Config()
    retriever, chatbot, query_analyzer, agent, metrics = initialize_components(
        config, model=model, provider_type=provider_type
    )

    # Select queries for evaluation
    queries = TEST_QUERIES.copy()

    # Filter by type if specified
    if query_type:
        queries = [q for q in queries if q["type"] == query_type]
        if not queries:
            print(f"❌ No queries found for type: {query_type}")
            sys.exit(1)

    # Limit trials if specified
    if trials and trials < len(queries):
        queries = queries[:trials]

    print(f"\n🧪 Running {len(queries)} test queries...\n")

    results: List[RoutingEvalResult] = []

    for i, test in enumerate(queries):
        query = test["query"]
        print(f"[{i+1}/{len(queries)}] {test['type'].upper()}: {query[:50]}...")

        result = evaluate_query(test, retriever, chatbot, query_analyzer, agent, metrics)

        # Show routing decision
        routing_emoji = "✅" if result.routing_correct else "❌"
        print(f"  {routing_emoji} Expected: {result.expected_path} | Actual: {result.actual_path}")
        print(f"  ⏱️  Latency: {result.latency:.2f}s", end="")
        if result.actual_path == "agent":
            print(f" ({result.agent_steps} steps)")
        else:
            print()

        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    routing_correct = sum(1 for r in results if r.routing_correct)
    analysis_correct = sum(1 for r in results if r.analysis_correct)
    routing_accuracy = routing_correct / len(results) * 100
    analysis_accuracy = analysis_correct / len(results) * 100

    fast_results = [r for r in results if r.actual_path == "fast"]
    agent_results = [r for r in results if r.actual_path == "agent"]

    print(f"\n🎯 Routing Metrics:")
    print(f"   - Routing Accuracy: {routing_accuracy:.1f}% ({routing_correct}/{len(results)})")
    print(f"   - Analysis Accuracy: {analysis_accuracy:.1f}% ({analysis_correct}/{len(results)})")

    if fast_results:
        fast_avg = sum(r.latency for r in fast_results) / len(fast_results)
        fast_success = sum(1 for r in fast_results if r.success)
        print(f"\n⚡ Fast-Path ({len(fast_results)} queries):")
        print(f"   - Avg latency: {fast_avg:.2f}s")
        print(f"   - Success rate: {fast_success}/{len(fast_results)}")

    if agent_results:
        agent_avg = sum(r.latency for r in agent_results) / len(agent_results)
        agent_steps = sum(r.agent_steps for r in agent_results) / len(agent_results)
        agent_success = sum(1 for r in agent_results if r.success)
        print(f"\n🤖 Agent-Path ({len(agent_results)} queries):")
        print(f"   - Avg latency: {agent_avg:.2f}s")
        print(f"   - Avg steps: {agent_steps:.1f}")
        print(f"   - Success rate: {agent_success}/{len(agent_results)}")

    # Latency comparison
    if fast_results and agent_results:
        fast_avg = sum(r.latency for r in fast_results) / len(fast_results)
        agent_avg = sum(r.latency for r in agent_results) / len(agent_results)
        latency_diff = ((agent_avg - fast_avg) / fast_avg) * 100
        print(f"\n⚖️  Latency difference (agent vs fast): {latency_diff:+.1f}%")

    summary = {
        "routing_accuracy": routing_accuracy,
        "analysis_accuracy": analysis_accuracy,
        "fast_path_count": len(fast_results),
        "agent_path_count": len(agent_results),
        "fast_avg_latency": sum(r.latency for r in fast_results) / len(fast_results) if fast_results else 0,
        "agent_avg_latency": sum(r.latency for r in agent_results) / len(agent_results) if agent_results else 0,
        "agent_avg_steps": sum(r.agent_steps for r in agent_results) / len(agent_results) if agent_results else 0
    }

    # Save JSON report
    report_dir = Path(__file__).parent / "results" / "eval_routing"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"routing_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": summary,
            "results": [r.to_dict() for r in results]
        }, f, ensure_ascii=False, indent=2)

    print(f"\n📄 JSON report: {json_path}")

    # Generate HTML report if requested
    if generate_html:
        html_path = generate_html_report(results, summary)
        print(f"📊 HTML report: {html_path}")

    return results, summary


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate binary routing system (fast-path vs agent-path)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help="Number of test queries (default: all)"
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["simple_fact", "analytics", "broad_summary", "complex_reasoning", "direct_answer", "utility"],
        help="Filter by query type"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model name to evaluate"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["ollama", "mlx"],
        default="ollama",
        help="LLM provider (default: ollama)"
    )
    args = parser.parse_args()

    run_evaluation(
        trials=args.trials, 
        query_type=args.type, 
        generate_html=args.html,
        model=args.model,
        provider_type=args.provider
    )


if __name__ == "__main__":
    main()
