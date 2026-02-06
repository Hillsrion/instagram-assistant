import json
from datetime import datetime
from pathlib import Path

def calculate_time(log_path):
    log_file = Path(log_path)
    if not log_file.exists():
        print(f"Error: {log_path} not found.")
        return

    timestamps = []
    total_enrichment_ms = 0
    count = 0

    with open(log_file, "r") as f:
        for line in f:
            try:
                data = json.loads(line)
                ts = datetime.fromisoformat(data["timestamp"])
                timestamps.append(ts)
                total_enrichment_ms += data.get("enrichment_time_ms", 0)
                count += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    if not timestamps:
        print("No valid log entries found.")
        return

    first_ts = min(timestamps)
    last_ts = max(timestamps)
    wall_clock_duration = last_ts - first_ts
    
    total_enrichment_sec = total_enrichment_ms / 1000

    print(f"Enrichment Statistics for {log_path}:")
    print(f"-----------------------------------")
    print(f"Total chunks processed: {count}")
    print(f"First entry:           {first_ts}")
    print(f"Last entry:            {last_ts}")
    print(f"Wall-clock duration:   {wall_clock_duration}")
    print(f"Sum of enrichment:     {total_enrichment_sec:.2f}s ({total_enrichment_sec/60:.2f}m)")
    
    if count > 0:
        print(f"Average per chunk:     {total_enrichment_sec/count:.2f}s")

if __name__ == "__main__":
    calculate_time("enrichment_logs/enrichment_log.jsonl")
