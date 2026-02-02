#!/usr/bin/env python3
"""
Analyses précises des tokens des chunks Instagram utilisant le tokenizer réel.
Calcule les stats sur le contenu brut et sur le texte d'embedding enrichi.

Usage:
    python3 scripts/token_stats.py
"""
import sys
import os
from pathlib import Path

# Ajout du dossier racine au sys.path pour importer la pipeline
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

import json
import statistics
import argparse
from tqdm import tqdm
from typing import List, Dict
from transformers import AutoTokenizer
from rag_pipeline.config import default_config
from rag_pipeline.chunker import Chunk

def format_number(val):
    return f"{val:,.0f}".replace(",", " ")

def print_bar_chart(data: Dict[str, int], width: int = 40):
    if not data:
        return
    max_val = max(data.values())
    for label, val in sorted(data.items()):
        bar_len = int((val / max_val) * width) if max_val > 0 else 0
        bar = "█" * bar_len + "░" * (width - bar_len)
        print(f"  {label:<12} | {bar} | {val:>5}")

def main():
    parser = argparse.ArgumentParser(description="Analyse précise des tokens des chunks")
    parser.add_argument("--chunks", type=Path, default=Path("rag_data/chunks.json"), help="Chemin vers chunks.json")
    parser.add_argument("--model", type=str, default=default_config.embedding_model, help="Modèle pour le tokenizer (default: bge-m3)")
    args = parser.parse_args()

    if not args.chunks.exists():
        print(f"❌ Fichier non trouvé: {args.chunks}")
        return

    print(f"🚀 Initialisation du tokenizer : {args.model}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(args.model)
    except Exception as e:
        print(f"⚠️ Erreur chargement tokenizer, repli sur un tokenizer générique : {e}")
        tokenizer = AutoTokenizer.from_pretrained("xlm-roberta-base")

    print(f"📂 Chargement des chunks depuis {args.chunks}...")
    with open(args.chunks, "r", encoding="utf-8") as f:
        chunks_raw = json.load(f)
    
    chunks = [Chunk.from_dict(c) for c in chunks_raw]
    print(f"✅ {len(chunks)} chunks chargés.")

    stats_content = []
    stats_embedding = []
    stats_enrichment = {
        "summary": [],
        "questions": [],
        "entities": []
    }

    print("\n🔍 Analyse des tokens en cours...")
    for chunk in tqdm(chunks, desc="Tokenization"):
        # 1. Contenu pur (ce que l'utilisateur lit)
        tokens_content = len(tokenizer.encode(chunk.content))
        stats_content.append(tokens_content)

        # 2. Texte d'embedding (ce que le moteur voit)
        embedding_text = chunk.get_embedding_text()
        tokens_embedding = len(tokenizer.encode(embedding_text))
        stats_embedding.append(tokens_embedding)

        # 3. Détails enrichment
        if chunk.narrative_summary:
            stats_enrichment["summary"].append(len(tokenizer.encode(chunk.narrative_summary)))
        if chunk.hypothetical_questions:
            q_text = " ".join(chunk.hypothetical_questions)
            stats_enrichment["questions"].append(len(tokenizer.encode(q_text)))
        if chunk.entities:
            e_text = json.dumps(chunk.entities)
            stats_enrichment["entities"].append(len(tokenizer.encode(e_text)))

    # Calcul des métriques
    def get_metrics(values):
        if not values: return None
        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p95": sorted(values)[int(len(values) * 0.95)],
            "sum": sum(values)
        }

    m_content = get_metrics(stats_content)
    m_embedding = get_metrics(stats_embedding)

    # Affichage des résultats
    print("\n" + "="*80)
    print("💎 STATISTIQUES DES TOKENS (Tokenizer: " + args.model + ")")
    print("="*80)

    print(f"\n📦 VOLUME TOTAL")
    print(f"  • Chunks analysés :    {len(chunks):>10}")
    print(f"  • Tokens Contenu Brut : {format_number(m_content['sum']):>10}")
    print(f"  • Tokens RAG (Enrichi): {format_number(m_embedding['sum']):>10} (+{((m_embedding['sum']/m_content['sum'])-1)*100:.1f}% d'enrichissement)")

    print(f"\n📏 RÉPARTITION PAR CHUNK (TOKENS)")
    print(f"  {'-'*18}|{'-'*18}|{'-'*18}")
    print(f"  {'Métrique':<17} | {'Contenu Brut':<16} | {'Texte RAG (Embed)':<16}")
    print(f"  {'-'*18}|{'-'*18}|{'-'*18}")
    print(f"  {'Minimum':<17} | {m_content['min']:>16,.0f} | {m_embedding['min']:>16,.0f}")
    print(f"  {'Médiane (p50)':<17} | {m_content['median']:>16,.0f} | {m_embedding['median']:>16,.0f}")
    print(f"  {'Moyenne':<17} | {m_content['mean']:>16,.0f} | {m_embedding['mean']:>16,.0f}")
    print(f"  {'P95 (Pessimiste)':<17} | {m_content['p95']:>16,.0f} | {m_embedding['p95']:>16,.0f}")
    print(f"  {'Maximum':<17} | {m_content['max']:>16,.0f} | {m_embedding['max']:>16,.0f}")
    print(f"  {'-'*18}|{'-'*18}|{'-'*18}")

    print("\n✨ IMPACT DE L'ENRICHISSEMENT (Moyenne tokens)")
    for key, vals in stats_enrichment.items():
        if vals:
             avg = statistics.mean(vals)
             print(f"  • {key.capitalize():<12} : {avg:>5.1f} tokens")

    # Histogramme simplifié
    print(f"\n📊 RÉPARTITION DES TAILLES (RAG Tokens)")
    bins = {
        "0-250": 0,
        "251-500": 0,
        "501-750": 0,
        "751-1000": 0,
        "1001-1500": 0,
        "1501-2000": 0,
        "Over 2000": 0
    }
    for val in stats_embedding:
        if val <= 250: bins["0-250"] += 1
        elif val <= 500: bins["251-500"] += 1
        elif val <= 750: bins["501-750"] += 1
        elif val <= 1000: bins["751-1000"] += 1
        elif val <= 1500: bins["1001-1500"] += 1
        elif val <= 2000: bins["1501-2000"] += 1
        else: bins["Over 2000"] += 1
    
    print_bar_chart(bins)

    # Recommandations
    print(f"\n💡 CONSEILS CONFIGURATION")
    ctx_limit = 32768 # Standard for Ministral in this project
    p95 = m_embedding['p95']
    top_k_safe = int((ctx_limit * 0.7 - 4000) / p95) if p95 > 0 else 0
    
    print(f"  • Sur une limite de {ctx_limit} tokens (32k):")
    print(f"  • Avec un top_k={default_config.top_k}, vous utilisez environ {default_config.top_k * m_embedding['mean']:,.0f} tokens de contexte.")
    print(f"  • Capacité maximale sécurisée (70% ctx) : ~{top_k_safe} chunks à {p95:.0f} tokens.")

    print("\n" + "="*80)
    print("✅ Analyse terminée.")

if __name__ == "__main__":
    main()
