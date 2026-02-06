"""
Logging and metrics tracking for enrichment decisions.

Tracks routing decisions, model selection, and enrichment timing
for analysis and optimization.
"""
import json
import csv
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class EnrichmentLogEntry:
    """Single enrichment decision log entry."""
    timestamp: str
    chunk_id: str
    complexity_score: float
    complexity_category: str
    selected_model: str
    enrichment_time_ms: float
    message_count: int
    participant_count: int

    # Optional: metadata about the routing decision
    reason: str = ""
    metrics_breakdown: Optional[Dict[str, float]] = None


class EnrichmentLogger:
    """Logs and tracks all enrichment routing decisions."""

    def __init__(self, output_dir: Path = None):
        """
        Initialize logger.

        Args:
            output_dir: Directory to save logs (default: rag_data/logs/enrichment_logs)
        """
        self.output_dir = Path(output_dir or "rag_data/logs/enrichment_logs")
        self.output_dir.mkdir(exist_ok=True, parents=True)

        self.log_file = self.output_dir / "enrichment_log.jsonl"
        self.csv_file = self.output_dir / "enrichment_log.csv"
        self.entries: List[EnrichmentLogEntry] = []

    def log_decision(
        self,
        chunk_id: str,
        complexity_score: float,
        complexity_category: str,
        selected_model: str,
        enrichment_time_ms: float,
        message_count: int,
        participant_count: int,
        reason: str = "",
        metrics_breakdown: Optional[Dict[str, float]] = None
    ):
        """
        Log a single enrichment decision.

        Args:
            chunk_id: ID of the chunk
            complexity_score: Computed complexity score (0.0-1.0)
            complexity_category: "simple", "medium", or "complex"
            selected_model: Which model was used
            enrichment_time_ms: Time taken for enrichment
            message_count: Number of messages in chunk
            participant_count: Number of participants
            reason: Optional reason for the selection
            metrics_breakdown: Optional breakdown of complexity metrics
        """
        entry = EnrichmentLogEntry(
            timestamp=datetime.now().isoformat(),
            chunk_id=chunk_id,
            complexity_score=complexity_score,
            complexity_category=complexity_category,
            selected_model=selected_model,
            enrichment_time_ms=enrichment_time_ms,
            message_count=message_count,
            participant_count=participant_count,
            reason=reason,
            metrics_breakdown=metrics_breakdown
        )
        self.entries.append(entry)

    def save(self):
        """Save all logged entries to JSONL file."""
        with open(self.log_file, 'a') as f:
            for entry in self.entries:
                json.dump(asdict(entry), f)
                f.write('\n')
        self.entries.clear()

    def export_csv(self):
        """Export all logs to CSV for analysis."""
        # Load existing entries from JSONL if file exists
        all_entries = []

        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            all_entries.append(data)
                        except json.JSONDecodeError:
                            print(f"⚠️ Skipping malformed log entry in {self.log_file}")
                            continue

        if not all_entries:
            print(f"⚠️ No entries to export to {self.csv_file}")
            return

        # Write to CSV
        fieldnames = [
            'timestamp',
            'chunk_id',
            'complexity_score',
            'complexity_category',
            'selected_model',
            'enrichment_time_ms',
            'message_count',
            'participant_count',
            'reason'
        ]

        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in all_entries:
                # Flatten metrics_breakdown and reason
                row = {
                    'timestamp': entry.get('timestamp', ''),
                    'chunk_id': entry.get('chunk_id', ''),
                    'complexity_score': entry.get('complexity_score', 0),
                    'complexity_category': entry.get('complexity_category', ''),
                    'selected_model': entry.get('selected_model', ''),
                    'enrichment_time_ms': entry.get('enrichment_time_ms', 0),
                    'message_count': entry.get('message_count', 0),
                    'participant_count': entry.get('participant_count', 0),
                    'reason': entry.get('reason', '')
                }
                writer.writerow(row)

        print(f"✅ Exported {len(all_entries)} entries to {self.csv_file}")

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics from logged entries."""
        if not self.log_file.exists():
            return {"total": 0}

        entries = []
        with open(self.log_file, 'r') as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        if not entries:
            return {"total": 0}

        # Aggregate stats
        categories = {"simple": 0, "medium": 0, "complex": 0}
        models = {}
        times_by_category = {"simple": [], "medium": [], "complex": []}
        total_time = 0

        for entry in entries:
            cat = entry.get("complexity_category", "unknown")
            if cat in categories:
                categories[cat] += 1

            model = entry.get("selected_model", "unknown")
            models[model] = models.get(model, 0) + 1

            time_ms = entry.get("enrichment_time_ms", 0)
            total_time += time_ms
            if cat in times_by_category:
                times_by_category[cat].append(time_ms)

        # Calculate averages
        avg_times = {}
        for cat, times in times_by_category.items():
            avg_times[cat] = sum(times) / len(times) if times else 0

        return {
            "total": len(entries),
            "categories": categories,
            "models": models,
            "avg_time_by_category_ms": avg_times,
            "total_time_ms": total_time,
        }

    def print_summary(self):
        """Print summary statistics."""
        stats = self.get_stats()

        if stats["total"] == 0:
            print("ℹ️ No enrichment logs available")
            return

        print("\n" + "="*70)
        print("📊 ENRICHMENT LOGGING SUMMARY")
        print("="*70)
        print(f"Total chunks processed: {stats['total']}")
        print(f"\nDistribution by complexity:")
        for cat in ["simple", "medium", "complex"]:
            count = stats["categories"].get(cat, 0)
            pct = 100 * count / stats["total"] if stats["total"] > 0 else 0
            print(f"  {cat:8}: {count:6} ({pct:5.1f}%)")

        print(f"\nAverage enrichment time by category:")
        for cat in ["simple", "medium", "complex"]:
            avg_time = stats["avg_time_by_category_ms"].get(cat, 0)
            print(f"  {cat:8}: {avg_time:7.0f}ms")

        print(f"\nModels used:")
        for model, count in stats["models"].items():
            pct = 100 * count / stats["total"] if stats["total"] > 0 else 0
            print(f"  {model:30}: {count:6} ({pct:5.1f}%)")

        total_hours = stats["total_time_ms"] / (1000 * 3600)
        print(f"\nTotal enrichment time: {total_hours:.2f} hours")
        print("="*70 + "\n")
