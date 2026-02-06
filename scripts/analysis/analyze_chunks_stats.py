#!/usr/bin/env python3
"""
Analyse statistique des chunks Instagram pour dimensionnement optimal du top_k.

Usage:
    python analyze_chunks_stats.py
    python analyze_chunks_stats.py --output report.md
"""

import json
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple
from collections import Counter
import statistics


@dataclass
class ChunkStats:
    """Statistiques d'un chunk."""
    chunk_id: str
    conversation_id: str
    message_count: int
    chars: int
    tokens_estimated: float
    tokens_with_header: float
    chars_per_msg: float
    tokens_per_msg: float
    category: str  # léger, moyen, dense, chargé


class ChunkAnalyzer:
    """Analyseur statistique de chunks."""

    # Ratio moyen caractères/tokens pour français + emojis
    CHAR_TO_TOKEN_RATIO = 3.7
    HEADER_TOKENS = 35

    # Seuils de classification (tokens par chunk de 50 messages)
    THRESHOLD_LIGHT = 1100
    THRESHOLD_MEDIUM = 1300
    THRESHOLD_DENSE = 1500

    def __init__(self, chunks_path: Path):
        self.chunks_path = chunks_path
        self.chunks_data = []
        self.stats: List[ChunkStats] = []

    def load_chunks(self):
        """Charge les chunks depuis le fichier JSON."""
        print(f"📂 Chargement de {self.chunks_path}...")

        with open(self.chunks_path, 'r', encoding='utf-8') as f:
            self.chunks_data = json.load(f)

        print(f"✅ {len(self.chunks_data)} chunks chargés")

    def analyze(self):
        """Analyse tous les chunks."""
        print(f"\n🔍 Analyse en cours...")

        for chunk in self.chunks_data:
            chars = len(chunk['content'])
            msg_count = chunk['message_count']

            # Estimation tokens
            tokens_content = chars / self.CHAR_TO_TOKEN_RATIO
            tokens_total = tokens_content + self.HEADER_TOKENS

            # Stats par message
            chars_per_msg = chars / msg_count if msg_count > 0 else 0
            tokens_per_msg = tokens_content / msg_count if msg_count > 0 else 0

            # Extrapolation à 50 messages pour classification
            if msg_count > 0:
                tokens_50_msgs = (tokens_per_msg * 50) + self.HEADER_TOKENS
            else:
                tokens_50_msgs = 0

            # Catégorisation
            if tokens_50_msgs < self.THRESHOLD_LIGHT:
                category = "léger"
            elif tokens_50_msgs < self.THRESHOLD_MEDIUM:
                category = "moyen"
            elif tokens_50_msgs < self.THRESHOLD_DENSE:
                category = "dense"
            else:
                category = "chargé"

            stat = ChunkStats(
                chunk_id=chunk['chunk_id'],
                conversation_id=chunk['conversation_id'],
                message_count=msg_count,
                chars=chars,
                tokens_estimated=tokens_content,
                tokens_with_header=tokens_total,
                chars_per_msg=chars_per_msg,
                tokens_per_msg=tokens_per_msg,
                category=category
            )

            self.stats.append(stat)

        print(f"✅ Analyse terminée\n")

    def get_distribution(self) -> Dict[str, int]:
        """Retourne la distribution par catégorie."""
        categories = [s.category for s in self.stats]
        return dict(Counter(categories))

    def get_message_distribution(self) -> Dict[int, int]:
        """Retourne la distribution par nombre de messages."""
        msg_counts = [s.message_count for s in self.stats]
        return dict(Counter(msg_counts))

    def get_percentiles(self, field: str) -> Dict[str, float]:
        """Calcule les percentiles pour un champ donné."""
        values = [getattr(s, field) for s in self.stats]
        values.sort()

        return {
            'min': min(values),
            'p10': values[int(len(values) * 0.10)],
            'p25': values[int(len(values) * 0.25)],
            'p50': statistics.median(values),
            'p75': values[int(len(values) * 0.75)],
            'p90': values[int(len(values) * 0.90)],
            'p95': values[int(len(values) * 0.95)],
            'p99': values[int(len(values) * 0.99)],
            'max': max(values),
            'mean': statistics.mean(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0
        }

    def get_chunks_by_size(self) -> Dict[str, List[ChunkStats]]:
        """Groupe les chunks par taille de messages."""
        sizes = {
            '1-10': [],
            '11-20': [],
            '21-30': [],
            '31-40': [],
            '41-50': []
        }

        for stat in self.stats:
            if stat.message_count <= 10:
                sizes['1-10'].append(stat)
            elif stat.message_count <= 20:
                sizes['11-20'].append(stat)
            elif stat.message_count <= 30:
                sizes['21-30'].append(stat)
            elif stat.message_count <= 40:
                sizes['31-40'].append(stat)
            else:
                sizes['41-50'].append(stat)

        return sizes

    def print_summary(self):
        """Affiche un résumé statistique."""
        print("=" * 80)
        print("📊 STATISTIQUES GLOBALES")
        print("=" * 80)

        print(f"\n📦 Nombre total de chunks: {len(self.stats)}")

        # Distribution par catégorie
        dist = self.get_distribution()
        total = len(self.stats)

        print("\n📈 Distribution par catégorie:")
        print(f"  • Légers:   {dist.get('léger', 0):>6} ({dist.get('léger', 0)/total*100:>5.1f}%)")
        print(f"  • Moyens:   {dist.get('moyen', 0):>6} ({dist.get('moyen', 0)/total*100:>5.1f}%)")
        print(f"  • Denses:   {dist.get('dense', 0):>6} ({dist.get('dense', 0)/total*100:>5.1f}%)")
        print(f"  • Chargés:  {dist.get('chargé', 0):>6} ({dist.get('chargé', 0)/total*100:>5.1f}%)")

        # Statistiques tokens
        tokens_stats = self.get_percentiles('tokens_with_header')

        print(f"\n🎯 Tokens par chunk (avec header):")
        print(f"  • Minimum:     {tokens_stats['min']:>8.0f} tokens")
        print(f"  • P10:         {tokens_stats['p10']:>8.0f} tokens")
        print(f"  • P25:         {tokens_stats['p25']:>8.0f} tokens")
        print(f"  • Médiane:     {tokens_stats['p50']:>8.0f} tokens")
        print(f"  • Moyenne:     {tokens_stats['mean']:>8.0f} tokens")
        print(f"  • P75:         {tokens_stats['p75']:>8.0f} tokens")
        print(f"  • P90:         {tokens_stats['p90']:>8.0f} tokens")
        print(f"  • P95:         {tokens_stats['p95']:>8.0f} tokens")
        print(f"  • P99:         {tokens_stats['p99']:>8.0f} tokens")
        print(f"  • Maximum:     {tokens_stats['max']:>8.0f} tokens")
        print(f"  • Écart-type:  {tokens_stats['stdev']:>8.0f} tokens")

        # Statistiques messages
        msg_stats = self.get_percentiles('message_count')

        print(f"\n💬 Messages par chunk:")
        print(f"  • Minimum:     {msg_stats['min']:>8.0f} messages")
        print(f"  • Médiane:     {msg_stats['p50']:>8.0f} messages")
        print(f"  • Moyenne:     {msg_stats['mean']:>8.0f} messages")
        print(f"  • Maximum:     {msg_stats['max']:>8.0f} messages")

        # Tokens par message
        tokens_per_msg = self.get_percentiles('tokens_per_msg')

        print(f"\n📝 Tokens par message:")
        print(f"  • Minimum:     {tokens_per_msg['min']:>8.1f} tokens/msg")
        print(f"  • Médiane:     {tokens_per_msg['p50']:>8.1f} tokens/msg")
        print(f"  • Moyenne:     {tokens_per_msg['mean']:>8.1f} tokens/msg")
        print(f"  • Maximum:     {tokens_per_msg['max']:>8.1f} tokens/msg")

        # Distribution par nombre de messages
        msg_dist = self.get_message_distribution()

        print(f"\n📊 Distribution par taille de chunk:")
        sizes = self.get_chunks_by_size()
        for size_range, chunks in sizes.items():
            if chunks:
                avg_tokens = statistics.mean([c.tokens_with_header for c in chunks])
                print(f"  • {size_range:>8} messages: {len(chunks):>6} chunks (avg: {avg_tokens:>6.0f} tokens)")

    def calculate_top_k_recommendations(self) -> Dict:
        """Calcule les recommandations de top_k basées sur les stats réelles."""
        # Moyenne pondérée réelle
        dist = self.get_distribution()
        total = len(self.stats)

        # Tokens moyens par catégorie
        avg_by_category = {}
        for category in ['léger', 'moyen', 'dense', 'chargé']:
            chunks_in_cat = [s for s in self.stats if s.category == category]
            if chunks_in_cat:
                avg_by_category[category] = statistics.mean([c.tokens_with_header for c in chunks_in_cat])
            else:
                avg_by_category[category] = 0

        # Moyenne pondérée
        weighted_avg = 0
        for category, count in dist.items():
            weight = count / total
            weighted_avg += weight * avg_by_category.get(category, 0)

        # Budgets
        TOTAL_BUDGET = 32768
        SYSTEM_TOKENS = 2500
        QUERY_TOKENS = 100
        OUTPUT_TOKENS = 1024
        FIXED_TOKENS = SYSTEM_TOKENS + QUERY_TOKENS + OUTPUT_TOKENS

        # Calcul pour différents top_k
        recommendations = {}

        for top_k in [8, 10, 12, 15, 18, 20, 22, 25, 28, 30]:
            rag_tokens = top_k * weighted_avg
            total_used = FIXED_TOKENS + rag_tokens
            remaining = TOTAL_BUDGET - total_used
            usage_pct = (total_used / TOTAL_BUDGET) * 100
            margin_pct = (remaining / TOTAL_BUDGET) * 100

            # Scénario pessimiste (P95)
            p95_tokens = self.get_percentiles('tokens_with_header')['p95']
            rag_tokens_p95 = top_k * p95_tokens
            total_p95 = FIXED_TOKENS + rag_tokens_p95
            usage_p95 = (total_p95 / TOTAL_BUDGET) * 100

            # Status
            if usage_pct < 70:
                status = "✅ Large"
            elif usage_pct < 80:
                status = "✅ Optimal"
            elif usage_pct < 90:
                status = "✅ Bon"
            elif usage_pct < 95:
                status = "⚠️ Serré"
            elif usage_pct < 100:
                status = "⚠️ Limite"
            else:
                status = "❌ Dépasse"

            recommendations[top_k] = {
                'rag_tokens': rag_tokens,
                'total_used': total_used,
                'usage_pct': usage_pct,
                'remaining': remaining,
                'margin_pct': margin_pct,
                'usage_p95': usage_p95,
                'status': status
            }

        return {
            'weighted_avg_tokens': weighted_avg,
            'avg_by_category': avg_by_category,
            'distribution': {k: v/total*100 for k, v in dist.items()},
            'recommendations': recommendations
        }

    def print_recommendations(self):
        """Affiche les recommandations de top_k."""
        print("\n" + "=" * 80)
        print("🎯 RECOMMANDATIONS TOP_K")
        print("=" * 80)

        recs = self.calculate_top_k_recommendations()

        print(f"\n📊 Moyenne pondérée réelle: {recs['weighted_avg_tokens']:.0f} tokens/chunk")

        print("\n📈 Tokens moyens par catégorie:")
        for cat, tokens in recs['avg_by_category'].items():
            pct = recs['distribution'].get(cat, 0)
            print(f"  • {cat.capitalize():8}: {tokens:>7.0f} tokens ({pct:>5.1f}% du dataset)")

        print("\n📋 Projections pour différents top_k:")
        print(f"{'top_k':<8} {'RAG':>10} {'Total':>10} {'Usage':>8} {'Marge':>8} {'P95':>8} {'Status':<12}")
        print("-" * 80)

        for top_k, rec in recs['recommendations'].items():
            print(f"{top_k:<8} {rec['rag_tokens']:>10,.0f} {rec['total_used']:>10,.0f} "
                  f"{rec['usage_pct']:>7.1f}% {rec['margin_pct']:>7.1f}% "
                  f"{rec['usage_p95']:>7.1f}% {rec['status']:<12}")

        # Recommandation optimale
        print("\n" + "=" * 80)
        print("💡 RECOMMANDATION OPTIMALE")
        print("=" * 80)

        # Trouver le top_k optimal (usage entre 70-80%)
        optimal_top_k = None
        for top_k, rec in recs['recommendations'].items():
            if 70 <= rec['usage_pct'] <= 80:
                if optimal_top_k is None or abs(rec['usage_pct'] - 75) < abs(recs['recommendations'][optimal_top_k]['usage_pct'] - 75):
                    optimal_top_k = top_k

        if optimal_top_k:
            opt = recs['recommendations'][optimal_top_k]
            print(f"\n✅ top_k optimal: {optimal_top_k}")
            print(f"   • Usage:  {opt['usage_pct']:.1f}% ({opt['total_used']:.0f} tokens)")
            print(f"   • Marge:  {opt['margin_pct']:.1f}% ({opt['remaining']:.0f} tokens)")
            print(f"   • P95:    {opt['usage_p95']:.1f}% (scénario pessimiste)")

        # Configuration recommandée par intent
        print("\n📝 Configuration recommandée par intent:")

        # specific_fact: ~35-45% usage
        for top_k, rec in recs['recommendations'].items():
            if 35 <= rec['usage_pct'] <= 45:
                print(f"   • specific_fact:     top_k={top_k:2}  ({rec['usage_pct']:.1f}% usage)")
                break

        # complex_reasoning: ~55-65% usage
        for top_k, rec in recs['recommendations'].items():
            if 55 <= rec['usage_pct'] <= 65:
                print(f"   • complex_reasoning: top_k={top_k:2}  ({rec['usage_pct']:.1f}% usage)")
                break

        # broad_summary: ~70-80% usage
        if optimal_top_k:
            opt = recs['recommendations'][optimal_top_k]
            print(f"   • broad_summary:     top_k={optimal_top_k:2}  ({opt['usage_pct']:.1f}% usage)")

    def generate_report(self, output_path: Path = None):
        """Génère un rapport markdown détaillé."""
        recs = self.calculate_top_k_recommendations()
        dist = self.get_distribution()
        total = len(self.stats)

        report = []
        report.append("# RAPPORT STATISTIQUE - CHUNKS INSTAGRAM")
        report.append(f"\n**Dataset**: {self.chunks_path}")
        report.append(f"**Chunks analysés**: {total:,}")
        report.append(f"**Moyenne tokens/chunk**: {recs['weighted_avg_tokens']:.0f}")
        report.append("\n---\n")

        # Distribution
        report.append("## 1. DISTRIBUTION DES CHUNKS\n")
        report.append("| Catégorie | Nombre | % | Tokens Moyens |")
        report.append("|-----------|--------|---|---------------|")
        for cat in ['léger', 'moyen', 'dense', 'chargé']:
            count = dist.get(cat, 0)
            pct = count / total * 100
            avg = recs['avg_by_category'].get(cat, 0)
            report.append(f"| {cat.capitalize()} | {count:,} | {pct:.1f}% | {avg:.0f} |")

        # Percentiles
        tokens_stats = self.get_percentiles('tokens_with_header')
        report.append("\n## 2. STATISTIQUES TOKENS\n")
        report.append("| Métrique | Valeur |")
        report.append("|----------|--------|")
        for key, value in tokens_stats.items():
            report.append(f"| {key.upper()} | {value:.0f} tokens |")

        # Recommandations
        report.append("\n## 3. RECOMMANDATIONS TOP_K\n")
        report.append("| top_k | RAG Tokens | Total | Usage | Marge | Status |")
        report.append("|-------|------------|-------|-------|-------|--------|")
        for top_k, rec in recs['recommendations'].items():
            report.append(f"| {top_k} | {rec['rag_tokens']:,.0f} | {rec['total_used']:,.0f} | "
                         f"{rec['usage_pct']:.1f}% | {rec['margin_pct']:.1f}% | {rec['status']} |")

        report_text = "\n".join(report)

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"\n📄 Rapport sauvegardé: {output_path}")

        return report_text


def main():
    parser = argparse.ArgumentParser(
        description="Analyse statistique des chunks Instagram"
    )
    parser.add_argument(
        '--chunks',
        type=Path,
        default=Path('rag_data/chunks.json'),
        help="Chemin vers chunks.json (default: rag_data/chunks.json)"
    )
    parser.add_argument(
        '--output',
        type=Path,
        help="Chemin de sortie pour le rapport markdown (optionnel)"
    )

    args = parser.parse_args()

    # Vérifier que le fichier existe
    if not args.chunks.exists():
        print(f"❌ Erreur: {args.chunks} n'existe pas")
        return 1

    # Analyse
    analyzer = ChunkAnalyzer(args.chunks)
    analyzer.load_chunks()
    analyzer.analyze()

    # Affichage
    analyzer.print_summary()
    analyzer.print_recommendations()

    # Rapport
    if args.output:
        analyzer.generate_report(args.output)

    print("\n✅ Analyse terminée\n")

    return 0


if __name__ == '__main__':
    exit(main())
