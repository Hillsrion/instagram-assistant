#!/usr/bin/env python3
"""
Script to get statistics about conversations.
Shows message counts, date ranges, and participants, ordered by message count.

Usage:
    python3 scripts/analysis/conversation_stats.py [--limit N]
"""
import argparse
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None


def format_duration(days: int) -> str:
    """Format duration in days to human-readable string."""
    if days <= 0:
        return "-"
    
    years = days // 365
    remaining_days = days % 365
    months = remaining_days // 30
    remaining_days = remaining_days % 30
    weeks = remaining_days // 7
    
    parts = []
    if years > 0:
        parts.append(f"{years}y")
    if months > 0:
        parts.append(f"{months}mo")
    if weeks > 0 and years == 0:  # Only show weeks if less than a year
        parts.append(f"{weeks}w")
    if not parts:  # Less than a week
        parts.append(f"{days}d")
    
    return " ".join(parts[:2])  # Max 2 parts for compact display


def main():
    parser = argparse.ArgumentParser(description="Get conversation statistics")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of conversations to show")
    parser.add_argument("--min-messages", type=int, default=0, help="Only show conversations with at least N messages")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    chunks_path = Path("rag_data/chunks.json")
    
    if not chunks_path.exists():
        print("❌ No chunks.json found in rag_data/")
        return
    
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    
    # Group by conversation
    by_conversation = defaultdict(list)
    for chunk in chunks:
        conv_id = chunk.get("conversation_id", "unknown")
        by_conversation[conv_id].append(chunk)
    
    # Calculate stats for each conversation
    stats = []
    for conv_id, conv_chunks in by_conversation.items():
        # Sum message counts
        total_messages = sum(c.get("message_count", 0) for c in conv_chunks)
        
        # Get date range
        dates = []
        for c in conv_chunks:
            start = parse_date(c.get("date_start"))
            end = parse_date(c.get("date_end"))
            if start:
                dates.append(start)
            if end:
                dates.append(end)
        
        date_start = min(dates) if dates else None
        date_end = max(dates) if dates else None
        
        # Get participants
        participants = conv_chunks[0].get("participants", [])
        
        # Duration in days
        duration_days = (date_end - date_start).days if date_start and date_end else 0
        
        stats.append({
            "id": conv_id,
            "messages": total_messages,
            "chunks": len(conv_chunks),
            "participants": participants,
            "participant_count": len(participants),
            "date_start": date_start.strftime("%Y-%m-%d") if date_start else "?",
            "date_end": date_end.strftime("%Y-%m-%d") if date_end else "?",
            "duration_days": duration_days
        })
    
    # Filter and sort
    if args.min_messages > 0:
        stats = [s for s in stats if s["messages"] >= args.min_messages]
    
    stats.sort(key=lambda x: x["messages"], reverse=True)
    
    # Apply limit
    if args.limit:
        stats = stats[:args.limit]
    
    # Output
    if args.json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return
    
    # Header
    total_messages = sum(s["messages"] for s in stats)
    total_conversations = len(by_conversation)
    
    print("=" * 80)
    print("CONVERSATION STATISTICS")
    print("=" * 80)
    print(f"  Total conversations: {total_conversations}")
    print(f"  Total messages: {sum(c.get('message_count', 0) for c in chunks):,}")
    print(f"  Total chunks: {len(chunks):,}")
    
    if args.limit:
        print(f"\n  Showing top {args.limit} by message count:")
    else:
        print(f"\n  All conversations ordered by message count:")
    
    print("\n" + "-" * 80)
    print(f"{'#':<4} {'Messages':>8} {'Chunks':>6} {'Duration':>10} {'Date Range':<23} Participants")
    print("-" * 80)
    
    for i, s in enumerate(stats, 1):
        participants_str = ", ".join(s["participants"][:3])
        if len(s["participants"]) > 3:
            participants_str += f" (+{len(s['participants'])-3})"
        
        # Truncate if too long
        if len(participants_str) > 50:
            participants_str = participants_str[:47] + "..."
        
        duration_str = format_duration(s["duration_days"])
        date_range = f"{s['date_start']} → {s['date_end']}"
        
        print(f"{i:<4} {s['messages']:>8,} {s['chunks']:>6} {duration_str:>10} {date_range:<23} {participants_str}")
    
    print("-" * 80)
    
    # Summary
    if stats:
        avg_messages = sum(s["messages"] for s in stats) / len(stats)
        max_conv = stats[0]
        print(f"\n📊 Top conversation: {max_conv['id']}")
        print(f"   Messages: {max_conv['messages']:,} | Duration: {format_duration(max_conv['duration_days'])}")
        print(f"   Participants: {', '.join(max_conv['participants'][:5])}")
        print(f"\n📈 Average messages per conversation: {avg_messages:,.0f}")


if __name__ == "__main__":
    main()
