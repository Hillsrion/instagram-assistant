"""
Multi-model comparison dashboard.

Scans eval/results/eval_generation/*.json reports and generates
an interactive HTML dashboard comparing models across metrics.

Usage:
    python -m eval.model_dashboard [--output path]
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any

from eval.core._output_paths import EVAL_RESULTS_DIR, get_dashboard_path


def scan_reports() -> List[Dict[str, Any]]:
    """Scan eval/results/eval_generation/ for JSON reports."""
    report_dir = EVAL_RESULTS_DIR / "eval_generation"
    if not report_dir.exists():
        return []

    reports = []
    # Search recursively for JSON reports
    for path in sorted(report_dir.rglob("*.json")):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['_file'] = path.name
            reports.append(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Skipping {path.name}: {e}")
    return reports


def extract_model_metrics(reports: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Extract per-model metrics from all reports.
    Handles legacy summary, single-model reports, and consolidated comparison reports.

    Returns dict mapping model name to aggregated metrics.
    """
    model_data: Dict[str, Dict[str, List[float]]] = {}

    def add_metric(model: str, faith: float, relev: float, speed: float, report: Dict[str, Any], metadata: Dict[str, Any]):
        if model not in model_data:
            model_data[model] = {
                "faithfulness": [],
                "relevance": [],
                "speed": [],
                "reports": [],
            }
        
        model_data[model]["faithfulness"].append(faith)
        model_data[model]["relevance"].append(relev)
        model_data[model]["speed"].append(speed)
        model_data[model]["reports"].append({
            "file": report.get("_file", ""),
            "timestamp": metadata.get("timestamp", ""),
            "faithfulness": faith,
            "relevance": relev,
            "speed": speed,
            "num_questions": metadata.get("num_questions", 0),
            "judge": metadata.get("judge_model", ""),
        })

    for report in reports:
        metadata = report.get("metadata", {})
        summary = report.get("summary", {})
        
        # Case 1: Legacy by_model summary
        if "by_model" in summary:
            for model, metrics in summary["by_model"].items():
                add_metric(
                    model,
                    metrics.get("avg_faithfulness", 0),
                    metrics.get("avg_relevance", 0),
                    metrics.get("avg_speed_wps", 0),
                    report,
                    metadata
                )
        
        # Case 2: Single model report
        elif "model" in metadata and any(k in summary for k in ["avg_faithfulness", "avg_relevance", "avg_speed_wps"]):
            model = metadata["model"]
            add_metric(
                model,
                summary.get("avg_faithfulness", 0),
                summary.get("avg_relevance", 0),
                summary.get("avg_speed_wps", 0),
                report,
                metadata
            )
            
        # Case 3: Consolidated comparison report
        elif "results" in report and isinstance(report["results"], list):
            # Aggregate metrics for each model across all questions in this report
            per_report_totals: Dict[str, Dict[str, List[float]]] = {}
            
            for q_res in report["results"]:
                responses = q_res.get("model_responses", {})
                for model, res in responses.items():
                    if model not in per_report_totals:
                        per_report_totals[model] = {"f": [], "r": [], "s": []}
                    
                    # Resilience to different naming (faith/faithfulness)
                    f = res.get("faithfulness", {}).get("score", 0) if isinstance(res.get("faithfulness"), dict) else res.get("faith", 0)
                    r = res.get("relevance", {}).get("score", 0) if isinstance(res.get("relevance"), dict) else res.get("relev", 0)
                    s = res.get("wps", 0) or res.get("words_per_sec", 0)
                    
                    per_report_totals[model]["f"].append(f)
                    per_report_totals[model]["r"].append(r)
                    per_report_totals[model]["s"].append(s)
            
            # Add aggregated averages for this report
            for model, totals in per_report_totals.items():
                n = len(totals["f"])
                add_metric(
                    model,
                    sum(totals["f"]) / n if n else 0,
                    sum(totals["r"]) / n if n else 0,
                    sum(totals["s"]) / n if n else 0,
                    report,
                    metadata
                )

    # Compute overall averages across all reports
    result = {}
    for model, data in model_data.items():
        n = len(data["faithfulness"])
        result[model] = {
            "avg_faithfulness": sum(data["faithfulness"]) / n if n else 0,
            "avg_relevance": sum(data["relevance"]) / n if n else 0,
            "avg_speed": sum(data["speed"]) / n if n else 0,
            "num_reports": n,
            "reports": data["reports"],
        }

    return result


def generate_dashboard_html(model_metrics: Dict[str, Dict[str, Any]], output_path: Path) -> Path:
    """Generate interactive HTML dashboard."""
    models = sorted(model_metrics.keys())
    faiths = [round(model_metrics[m]["avg_faithfulness"], 3) for m in models]
    relevs = [round(model_metrics[m]["avg_relevance"], 3) for m in models]
    speeds = [round(model_metrics[m]["avg_speed"], 2) for m in models]

    # Build table rows
    table_rows = ""
    for m in models:
        d = model_metrics[m]
        table_rows += f"""
            <tr class="model-row border-b border-slate-100 hover:bg-slate-50" data-model="{m}">
                <td class="px-6 py-4 font-medium text-slate-900">{m}</td>
                <td class="px-6 py-4 text-center">{d['avg_faithfulness']:.1%}</td>
                <td class="px-6 py-4 text-center">{d['avg_relevance']:.1%}</td>
                <td class="px-6 py-4 text-center">{d['avg_speed']:.1f}</td>
                <td class="px-6 py-4 text-center text-slate-500">{d['num_reports']}</td>
            </tr>
        """

    # Build checkboxes
    checkboxes = ""
    for m in models:
        checkboxes += f"""
            <label class="inline-flex items-center mr-4 mb-2 cursor-pointer">
                <input type="checkbox" class="model-checkbox rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                       data-model="{m}" checked onchange="updateCharts()">
                <span class="ml-2 text-sm font-medium text-slate-700">{m}</span>
            </label>
        """

    html = f"""<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Model Dashboard</title>
    <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; }}
    </style>
</head>
<body class="h-full">
    <div class="min-h-full py-12 px-4 sm:px-6 lg:px-8">
        <div class="max-w-7xl mx-auto">
            <!-- Header -->
            <div class="text-center mb-12">
                <h1 class="text-4xl font-extrabold text-slate-900 tracking-tight sm:text-5xl">
                    Multi-Model Dashboard
                </h1>
                <p class="mt-4 text-lg text-slate-600">
                    Comparing <span class="font-semibold text-indigo-600">{len(models)}</span> models
                    across <span class="font-semibold text-indigo-600">{sum(d['num_reports'] for d in model_metrics.values())}</span> reports
                </p>
            </div>

            <!-- Model Filters -->
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 mb-8">
                <h3 class="text-sm font-bold text-slate-700 uppercase tracking-wide mb-3">Filter Models</h3>
                <div class="flex flex-wrap">
                    {checkboxes}
                </div>
            </div>

            <!-- Charts -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6">Faithfulness</h3>
                    <div class="h-64"><canvas id="faithChart"></canvas></div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6">Relevance</h3>
                    <div class="h-64"><canvas id="relevChart"></canvas></div>
                </div>
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900 mb-6">Speed (words/sec)</h3>
                    <div class="h-64"><canvas id="speedChart"></canvas></div>
                </div>
            </div>

            <!-- Table -->
            <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                <div class="px-6 py-4 border-b border-slate-200">
                    <h3 class="text-lg font-bold text-slate-900">Details per Model</h3>
                </div>
                <table class="min-w-full divide-y divide-slate-200">
                    <thead class="bg-slate-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-bold text-slate-500 uppercase tracking-wider">Model</th>
                            <th class="px-6 py-3 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">Faithfulness</th>
                            <th class="px-6 py-3 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">Relevance</th>
                            <th class="px-6 py-3 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">Speed (w/s)</th>
                            <th class="px-6 py-3 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">Reports</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-slate-200">
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const allModels = {json.dumps(models)};
        const allFaiths = {json.dumps(faiths)};
        const allRelevs = {json.dumps(relevs)};
        const allSpeeds = {json.dumps(speeds)};

        const COLORS = [
            '#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
            '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1'
        ];

        let faithChart, relevChart, speedChart;

        function getSelectedModels() {{
            const checked = document.querySelectorAll('.model-checkbox:checked');
            return Array.from(checked).map(cb => cb.dataset.model);
        }}

        function createChart(id, label, allData, allLabels, maxY) {{
            const ctx = document.getElementById(id).getContext('2d');
            return new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: allLabels,
                    datasets: [{{
                        label: label,
                        data: allData,
                        backgroundColor: allLabels.map((_, i) => COLORS[i % COLORS.length]),
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
                            max: maxY,
                            grid: {{ display: true, color: '#f1f5f9' }},
                            ticks: {{ font: {{ size: 10 }} }}
                        }},
                        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }}
                    }}
                }}
            }});
        }}

        function updateCharts() {{
            const selected = getSelectedModels();
            const indices = selected.map(m => allModels.indexOf(m)).filter(i => i >= 0);

            const labels = indices.map(i => allModels[i]);
            const faithData = indices.map(i => allFaiths[i]);
            const relevData = indices.map(i => allRelevs[i]);
            const speedData = indices.map(i => allSpeeds[i]);
            const colors = indices.map((_, i) => COLORS[i % COLORS.length]);

            // Update chart data
            faithChart.data.labels = labels;
            faithChart.data.datasets[0].data = faithData;
            faithChart.data.datasets[0].backgroundColor = colors;
            faithChart.update();

            relevChart.data.labels = labels;
            relevChart.data.datasets[0].data = relevData;
            relevChart.data.datasets[0].backgroundColor = colors;
            relevChart.update();

            speedChart.data.labels = labels;
            speedChart.data.datasets[0].data = speedData;
            speedChart.data.datasets[0].backgroundColor = colors;
            speedChart.update();

            // Update table visibility
            document.querySelectorAll('.model-row').forEach(row => {{
                row.style.display = selected.includes(row.dataset.model) ? '' : 'none';
            }});
        }}

        // Initialize charts
        faithChart = createChart('faithChart', 'Faithfulness', allFaiths, allModels, 1);
        relevChart = createChart('relevChart', 'Relevance', allRelevs, allModels, 1);
        speedChart = createChart('speedChart', 'Speed', allSpeeds, allModels, null);
    </script>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-model comparison dashboard from eval reports"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for the HTML dashboard"
    )
    args = parser.parse_args()

    print("Scanning eval/results/eval_generation/ for JSON reports...")
    reports = scan_reports()

    if not reports:
        print("No JSON reports found in eval/results/eval_generation/")
        print("Run eval_generation first: python -m eval.eval_generation model1 model2")
        return

    print(f"Found {len(reports)} report(s)")

    model_metrics = extract_model_metrics(reports)

    if not model_metrics:
        print("No model metrics found in reports.")
        return

    print(f"Found {len(model_metrics)} unique model(s): {', '.join(sorted(model_metrics.keys()))}")

    output_path = Path(args.output) if args.output else get_dashboard_path()
    dashboard_path = generate_dashboard_html(model_metrics, output_path)
    print(f"Dashboard generated: {dashboard_path}")


if __name__ == "__main__":
    main()