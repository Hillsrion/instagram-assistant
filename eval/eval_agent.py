"""
Comparative Evaluation: Pipeline vs ReAct Agent.

Compares the traditional linear RAG pipeline with the new ReAct agent
across different query types to measure:
- Answer quality (faithfulness, relevance)
- Latency
- Tool usage patterns
- Failure rates

Usage:
    python -m eval.eval_agent --trials 5
    python -m eval.eval_agent --trials 10 --html
"""

import json
import sys
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_pipeline.config import Config
from rag_pipeline.agent import AgentRunner, AgentResult
from rag_pipeline.chat import ChatBot
from rag_pipeline.retriever import Retriever
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.vector_store import VectorStore
# Direct import to avoid eval/__init__.py which has broken dependencies
from eval.metrics import RAGASMetrics


# ============================================================
# Test Dataset - Mixed Query Types
# ============================================================

TEST_QUERIES = [
    # Simple queries - single tool needed
    {
        "query": "De quoi on a parlé avec mes amis récemment ?",
        "type": "simple",
        "expected_tool": "search_conversations",
        "description": "Semantic search query"
    },
    {
        "query": "Est-ce qu'on a déjà parlé de voyages ?",
        "type": "simple",
        "expected_tool": "search_conversations",
        "description": "Factual verification"
    },
    {
        "query": "Quelle est la date d'aujourd'hui ?",
        "type": "simple",
        "expected_tool": "get_todays_date",
        "description": "Date query"
    },
    
    # Analytical queries - counting/stats
    {
        "query": "Combien de messages j'ai échangé en total ?",
        "type": "analytical",
        "expected_tool": "count_messages",
        "description": "Global count query"
    },
    
    # Composite queries - multiple tools needed (agent advantage)
    {
        "query": "Résume mes discussions récentes et dis-moi combien d'échanges j'ai eus",
        "type": "composite",
        "expected_tools": ["search_conversations", "count_messages"],
        "description": "Summary + count"
    },
    
    # Direct answer - no tool needed
    {
        "query": "Bonjour, comment ça va ?",
        "type": "direct",
        "expected_tool": None,
        "description": "Greeting - no tool needed"
    },
]


@dataclass
class PipelineResult:
    """Result from the traditional pipeline."""
    answer: str
    latency: float
    success: bool
    error: Optional[str] = None


@dataclass 
class ComparisonResult:
    """Comparison result for a single query."""
    query: str
    query_type: str
    description: str
    
    # Pipeline results
    pipeline_answer: str
    pipeline_latency: float
    pipeline_success: bool
    
    # Agent results
    agent_answer: str
    agent_latency: float
    agent_steps: int
    agent_tools_used: List[str]
    agent_success: bool
    
    # Quality scores (from judge)
    pipeline_faithfulness: float = 0.0
    pipeline_relevance: float = 0.0
    agent_faithfulness: float = 0.0
    agent_relevance: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


def initialize_components(config: Config):
    """Initialize RAG components."""
    print("📦 Loading RAG components...")
    
    embedding_model = EmbeddingModel(config)
    vector_store = VectorStore(config)
    
    if not vector_store.load():
        print("❌ Vector store not found. Run setup_rag.py first.")
        sys.exit(1)
    
    retriever = Retriever(embedding_model, vector_store, config)
    chatbot = ChatBot(retriever, config)
    agent = AgentRunner(config, retriever)
    
    print(f"✅ Loaded {vector_store.size} vectors")
    return chatbot, agent, retriever


def run_pipeline(chatbot: ChatBot, query: str) -> PipelineResult:
    """Run the traditional pipeline on a query."""
    start = time.time()
    
    try:
        # Non-streaming mode for evaluation
        response = chatbot.chat(query, stream=False)
        answer = response.answer if hasattr(response, 'answer') else str(response)
        
        return PipelineResult(
            answer=answer,
            latency=time.time() - start,
            success=True
        )
    except Exception as e:
        return PipelineResult(
            answer=f"Error: {e}",
            latency=time.time() - start,
            success=False,
            error=str(e)
        )


def run_agent(agent: AgentRunner, query: str) -> AgentResult:
    """Run the ReAct agent on a query."""
    try:
        return agent.run(query)
    except Exception as e:
        return AgentResult(
            answer=f"Error: {e}",
            steps=[],
            total_time=0,
            success=False,
            error=str(e)
        )


def judge_answers(
    metrics: RAGASMetrics,
    query: str,
    pipeline_answer: str,
    agent_answer: str
) -> Dict[str, float]:
    """Judge both answers using LLM-as-judge."""
    
    # For now, use simplified scoring without ground truth
    # We compare both answers against each other for relative quality
    try:
        pipeline_faith = metrics.compute_faithfulness_with_explanation(
            question=query,
            generated_answer=pipeline_answer,
            source_content="(réponse basée sur la recherche)"
        )
        
        agent_faith = metrics.compute_faithfulness_with_explanation(
            question=query,
            generated_answer=agent_answer,
            source_content="(réponse basée sur la recherche)"
        )
        
        return {
            "pipeline_faithfulness": pipeline_faith.get("score", 0.5),
            "agent_faithfulness": agent_faith.get("score", 0.5),
            "pipeline_relevance": 0.5,  # Simplified for now
            "agent_relevance": 0.5,
        }
    except Exception as e:
        print(f"  ⚠️ Judge error: {e}")
        return {
            "pipeline_faithfulness": 0.5,
            "agent_faithfulness": 0.5,
            "pipeline_relevance": 0.5,
            "agent_relevance": 0.5,
        }


def generate_html_report(results: List[ComparisonResult], summary: Dict) -> Path:
    """Generate HTML comparison report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate averages
    pipeline_avg_latency = sum(r.pipeline_latency for r in results) / len(results)
    agent_avg_latency = sum(r.agent_latency for r in results) / len(results)
    agent_avg_steps = sum(r.agent_steps for r in results) / len(results)
    
    pipeline_success_rate = sum(1 for r in results if r.pipeline_success) / len(results) * 100
    agent_success_rate = sum(1 for r in results if r.agent_success) / len(results) * 100
    
    html = f"""
<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pipeline vs Agent Comparison</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="h-full">
    <div class="min-h-full py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-6xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-12">
                <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight">
                    🔄 Pipeline vs ReAct Agent
                </h1>
                <p class="mt-4 text-lg text-slate-600">
                    Generated on <span class="font-semibold text-indigo-600">{timestamp}</span> • 
                    {len(results)} queries tested
                </p>
            </div>
            
            <!-- Summary Cards -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-sm font-medium text-slate-500 uppercase">Pipeline Latency</h3>
                    <p class="text-3xl font-bold text-slate-900">{pipeline_avg_latency:.2f}s</p>
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
                    <p class="text-3xl font-bold text-green-600">{agent_success_rate:.0f}%</p>
                </div>
            </div>
            
            <!-- Charts -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-4">⏱️ Latency Comparison</h3>
                    <canvas id="latencyChart" height="200"></canvas>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-4">📊 By Query Type</h3>
                    <canvas id="typeChart" height="200"></canvas>
                </div>
            </div>
            
            <!-- Details -->
            <div class="space-y-8">
                <h2 class="text-2xl font-bold text-slate-900 border-b border-slate-200 pb-4">
                    📝 Detailed Results
                </h2>
    """
    
    for i, r in enumerate(results):
        type_badge_color = {
            "simple": "bg-blue-100 text-blue-800",
            "analytical": "bg-purple-100 text-purple-800",
            "composite": "bg-orange-100 text-orange-800",
            "direct": "bg-green-100 text-green-800"
        }.get(r.query_type, "bg-slate-100 text-slate-800")
        
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
                            <span class="text-sm text-slate-500">Query {i+1}</span>
                        </div>
                        <h3 class="text-lg font-bold text-slate-900 mt-2">{r.query}</h3>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-100">
                        <!-- Pipeline -->
                        <div class="p-6">
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="font-bold text-slate-700">📦 Pipeline</h4>
                                <span class="text-sm text-slate-500">{r.pipeline_latency:.2f}s</span>
                            </div>
                            <p class="text-sm text-slate-600 bg-slate-50 p-3 rounded-lg">
                                {r.pipeline_answer[:300]}{'...' if len(r.pipeline_answer) > 300 else ''}
                            </p>
                        </div>
                        
                        <!-- Agent -->
                        <div class="p-6">
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="font-bold text-indigo-700">🤖 Agent ({r.agent_steps} steps)</h4>
                                <span class="text-sm text-slate-500">{r.agent_latency:.2f}s</span>
                            </div>
                            <p class="text-xs text-slate-500 mb-2">Tools: {tools_str}</p>
                            <p class="text-sm text-slate-600 bg-indigo-50 p-3 rounded-lg">
                                {r.agent_answer[:300]}{'...' if len(r.agent_answer) > 300 else ''}
                            </p>
                        </div>
                    </div>
                </div>
        """
    
    # Chart data
    query_labels = [f"Q{i+1}" for i in range(len(results))]
    pipeline_latencies = [r.pipeline_latency for r in results]
    agent_latencies = [r.agent_latency for r in results]
    
    # By type aggregation
    type_stats = {}
    for r in results:
        if r.query_type not in type_stats:
            type_stats[r.query_type] = {"pipeline": [], "agent": []}
        type_stats[r.query_type]["pipeline"].append(r.pipeline_latency)
        type_stats[r.query_type]["agent"].append(r.agent_latency)
    
    type_labels = list(type_stats.keys())
    type_pipeline_avg = [sum(v["pipeline"])/len(v["pipeline"]) for v in type_stats.values()]
    type_agent_avg = [sum(v["agent"])/len(v["agent"]) for v in type_stats.values()]
    
    html += f"""
            </div>
        </div>
    </div>
    
    <script>
        new Chart(document.getElementById('latencyChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(query_labels)},
                datasets: [
                    {{
                        label: 'Pipeline',
                        data: {json.dumps(pipeline_latencies)},
                        backgroundColor: '#94a3b8',
                        borderRadius: 4
                    }},
                    {{
                        label: 'Agent',
                        data: {json.dumps(agent_latencies)},
                        backgroundColor: '#6366f1',
                        borderRadius: 4
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ position: 'top' }} }},
                scales: {{
                    y: {{ beginAtZero: true, title: {{ display: true, text: 'Seconds' }} }}
                }}
            }}
        }});
        
        new Chart(document.getElementById('typeChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(type_labels)},
                datasets: [
                    {{
                        label: 'Pipeline Avg',
                        data: {json.dumps(type_pipeline_avg)},
                        backgroundColor: '#94a3b8',
                        borderRadius: 4
                    }},
                    {{
                        label: 'Agent Avg',
                        data: {json.dumps(type_agent_avg)},
                        backgroundColor: '#6366f1',
                        borderRadius: 4
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ position: 'top' }} }},
                scales: {{
                    y: {{ beginAtZero: true, title: {{ display: true, text: 'Seconds' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>
    """
    
    report_dir = Path(__file__).parent.parent / "eval_reports"
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"agent_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return report_path


def run_evaluation(trials: int = 5, generate_html: bool = False):
    """Run the comparative evaluation."""
    print("=" * 60)
    print("Pipeline vs ReAct Agent Evaluation")
    print("=" * 60)
    print()
    
    config = Config()
    chatbot, agent, retriever = initialize_components(config)
    
    # Select queries for evaluation
    queries = TEST_QUERIES[:trials] if trials < len(TEST_QUERIES) else TEST_QUERIES
    
    print(f"\n🧪 Running {len(queries)} test queries...\n")
    
    results: List[ComparisonResult] = []
    
    for i, test in enumerate(queries):
        query = test["query"]
        print(f"[{i+1}/{len(queries)}] {test['type'].upper()}: {query[:50]}...")
        
        # Run pipeline
        print("  📦 Pipeline...", end="", flush=True)
        pipeline_result = run_pipeline(chatbot, query)
        print(f" {pipeline_result.latency:.2f}s")
        
        # Run agent
        print("  🤖 Agent...", end="", flush=True)
        agent_result = run_agent(agent, query)
        tools_used = [s.action for s in agent_result.steps if s.action]
        print(f" {agent_result.total_time:.2f}s ({len(agent_result.steps)} steps)")
        
        # Create comparison result
        result = ComparisonResult(
            query=query,
            query_type=test["type"],
            description=test["description"],
            pipeline_answer=pipeline_result.answer,
            pipeline_latency=pipeline_result.latency,
            pipeline_success=pipeline_result.success,
            agent_answer=agent_result.answer,
            agent_latency=agent_result.total_time,
            agent_steps=len(agent_result.steps),
            agent_tools_used=tools_used,
            agent_success=agent_result.success
        )
        results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    pipeline_avg = sum(r.pipeline_latency for r in results) / len(results)
    agent_avg = sum(r.agent_latency for r in results) / len(results)
    agent_steps_avg = sum(r.agent_steps for r in results) / len(results)
    
    print(f"\n📦 Pipeline:")
    print(f"   - Avg latency: {pipeline_avg:.2f}s")
    print(f"   - Success rate: {sum(1 for r in results if r.pipeline_success)}/{len(results)}")
    
    print(f"\n🤖 Agent:")
    print(f"   - Avg latency: {agent_avg:.2f}s")
    print(f"   - Avg steps: {agent_steps_avg:.1f}")
    print(f"   - Success rate: {sum(1 for r in results if r.agent_success)}/{len(results)}")
    
    latency_diff = ((agent_avg - pipeline_avg) / pipeline_avg) * 100
    print(f"\n⚡ Latency difference: {latency_diff:+.1f}%")
    
    summary = {
        "pipeline_avg_latency": pipeline_avg,
        "agent_avg_latency": agent_avg,
        "agent_avg_steps": agent_steps_avg,
        "latency_diff_percent": latency_diff
    }
    
    # Save JSON report
    report_dir = Path(__file__).parent.parent / "eval_reports"
    report_dir.mkdir(exist_ok=True)
    json_path = report_dir / f"agent_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
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
        description="Compare Pipeline vs ReAct Agent performance",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="Number of test queries (default: 5)"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report"
    )
    args = parser.parse_args()
    
    run_evaluation(trials=args.trials, generate_html=args.html)


if __name__ == "__main__":
    main()
