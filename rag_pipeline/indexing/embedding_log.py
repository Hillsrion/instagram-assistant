"""
Logging and metrics tracking for the embedding process.

Tracks batch sizes, execution time, and hardware usage for performance analysis.
"""
import json
import csv
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class EmbeddingLogEntry:
    """Single embedding batch log entry."""
    timestamp: str
    batch_size: int
    total_texts: int
    model_name: str
    device: str
    duration_ms: float
    avg_time_per_text_ms: float


class EmbeddingLogger:
    """Logs and tracks all embedding execution metrics."""

    def __init__(self, output_dir: Path = None):
        """
        Initialize logger.

        Args:
            output_dir: Directory to save logs (default: logs)
        """
        self.output_dir = Path(output_dir or "logs")
        self.output_dir.mkdir(exist_ok=True, parents=True)

        self.log_file = self.output_dir / "embedding_log.jsonl"
        self.csv_file = self.output_dir / "embedding_log.csv"
        self.entries: List[EmbeddingLogEntry] = []

    def log_batch(
        self,
        batch_size: int,
        total_texts: int,
        model_name: str,
        device: str,
        duration_ms: float
    ):
        """
        Log a single embedding batch.

        Args:
            batch_size: Internal batch size used by the model
            total_texts: Total number of texts in this request
            model_name: Name of the model used
            device: Device used (cpu, cuda, mps)
            duration_ms: Time taken for the whole batch
        """
        avg_time = duration_ms / total_texts if total_texts > 0 else 0
        entry = EmbeddingLogEntry(
            timestamp=datetime.now().isoformat(),
            batch_size=batch_size,
            total_texts=total_texts,
            model_name=model_name,
            device=device,
            duration_ms=duration_ms,
            avg_time_per_text_ms=avg_time
        )
        self.entries.append(entry)
        
        # Auto-save to JSONL for persistence
        self.save()

    def save(self):
        """Save all logged entries to JSONL file."""
        if not self.entries:
            return
            
        with open(self.log_file, 'a') as f:
            for entry in self.entries:
                json.dump(asdict(entry), f)
                f.write('\n')
        self.entries.clear()

    def export_csv(self):
        """Export all logs to CSV for analysis."""
        all_entries = []

        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        all_entries.append(data)

        if not all_entries:
            return

        # Write to CSV
        fieldnames = [
            'timestamp',
            'batch_size',
            'total_texts',
            'model_name',
            'device',
            'duration_ms',
            'avg_time_per_text_ms'
        ]

        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for entry in all_entries:
                writer.writerow(entry)

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics from logged entries."""
        if not self.log_file.exists():
            return {"total_calls": 0}

        entries = []
        with open(self.log_file, 'r') as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))

        if not entries:
            return {"total_calls": 0}

        total_texts = sum(e.get("total_texts", 0) for e in entries)
        total_duration = sum(e.get("duration_ms", 0) for e in entries)
        
        devices = {}
        for e in entries:
            dev = e.get("device", "unknown")
            devices[dev] = devices.get(dev, 0) + 1

        return {
            "total_calls": len(entries),
            "total_texts_embedded": total_texts,
            "total_duration_ms": total_duration,
            "avg_time_per_text_ms": total_duration / total_texts if total_texts > 0 else 0,
            "devices": devices
        }

    def print_summary(self):
        """Print summary statistics."""
        stats = self.get_stats()

        if stats["total_calls"] == 0:
            print("ℹ️ No embedding logs available")
            return

        print("\n" + "="*70)
        print("📊 EMBEDDING LOGGING SUMMARY")
        print("="*70)
        print(f"Total batches processed: {stats['total_calls']}")
        print(f"Total texts embedded:   {stats['total_texts_embedded']}")
        
        avg_time = stats["avg_time_per_text_ms"]
        print(f"Average time per text:  {avg_time:.2f}ms")
        
        print(f"\nDevices used:")
        for device, count in stats["devices"].items():
            pct = 100 * count / stats["total_calls"] if stats["total_calls"] > 0 else 0
            print(f"  {device:15}: {count:6} ({pct:5.1f}%)")

        total_minutes = stats["total_duration_ms"] / (1000 * 60)
        print(f"\nTotal embedding time: {total_minutes:.2f} minutes")
        print("="*70 + "\n")
