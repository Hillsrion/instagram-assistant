
    def validate_chunk_with_llm(self, chunk: Chunk, judge_model: str, provider_type: str = "ollama") -> ChunkEnrichmentValidationReport:
        """
        Validate enrichment quality using an LLM judge.
        
        This method sends the chunk content and its enrichment to an LLM
        to evaluate the quality, accuracy, and relevance of the enriched metadata.
        """
        from rag_pipeline.llm_provider import create_provider
        
        provider = create_provider(self.config, judge_model, provider_type)
        
        # Prepare the context for the judge
        enrichment_data = {
            "narrative_summary": chunk.narrative_summary,
            "hypothetical_questions": chunk.hypothetical_questions,
            "speaker_intents": chunk.speaker_intents,
            "temporal_context": chunk.temporal_context,
            "entities": chunk.entities,
            "emotions": chunk.emotions,
            "interaction_pattern": chunk.interaction_pattern,
            "initiative": chunk.initiative,
            "emotional_shift": chunk.emotional_shift,
            "open_loops": chunk.open_loops
        }
        
        prompt = f"""You are an expert AI judge evaluating the quality of metadata extraction from conversation chunks.
        
        TASK:
        Evaluate how well the extracted metadata (Enrichment) reflects the original Conversation Chunk.
        
        ORIGINAL CONVERSATION CHUNK:
        ---
        {chunk.content}
        ---
        
        EXTRACTED ENRICHMENT METADATA:
        ---
        {json.dumps(enrichment_data, indent=2, ensure_ascii=False)}
        ---
        
        EVALUATION CRITERIA:
        1. Accuracy: Does the summary and metadata factually reflect the conversation?
        2. Completeness: Are all key entities, emotions, and intents captured?
        3. Relevance: Are the hypothetical questions relevant and answerable from the text?
        4. hallucination: Are there any invented details not present in the text?
        
        OUTPUT FORMAT:
        Return a JSON object with evaluation for each field.
        {{
            "narrative_summary": {{ "score": 0.0-1.0, "reason": "..." }},
            "questions": {{ "score": 0.0-1.0, "reason": "..." }},
            "speaker_intents": {{ "score": 0.0-1.0, "reason": "..." }},
            "entities": {{ "score": 0.0-1.0, "reason": "..." }},
            "emotions": {{ "score": 0.0-1.0, "reason": "..." }},
            "temporal_context": {{ "score": 0.0-1.0, "reason": "..." }},
            "social_dynamics": {{ "score": 0.0-1.0, "reason": "..." }}
        }}
        
        Ensure strictly valid JSON output.
        """
        
        try:
            response = provider.generate([{"role": "user", "content": prompt}], temperature=0.1)
            # Find JSON in response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end != -1:
                eval_json = json.loads(response[start:end])
            else:
                eval_json = json.loads(response) # Try direct parse
                
            # Create report based on LLM feedback
            report = ChunkEnrichmentValidationReport(
                chunk_id=chunk.chunk_id,
                conversation_id=chunk.conversation_id,
                content_preview=chunk.content[:200]
            )
            
            # Map LLM scores to FieldValidationResults
            field_mapping = {
                "narrative_summary": EnrichmentFieldType.NARRATIVE_SUMMARY,
                "questions": EnrichmentFieldType.QUESTIONS,
                "speaker_intents": EnrichmentFieldType.SPEAKER_INTENTS,
                "entities": EnrichmentFieldType.ENTITIES,
                "emotions": EnrichmentFieldType.EMOTIONS,
                "temporal_context": EnrichmentFieldType.TEMPORAL_CONTEXT,
                # Group social dynamics
                "interaction_pattern": EnrichmentFieldType.INTERACTION_PATTERN,
                "initiative": EnrichmentFieldType.INITIATIVE,
                "emotional_shift": EnrichmentFieldType.EMOTIONAL_SHIFT,
                "open_loops": EnrichmentFieldType.OPEN_LOOPS
            }
            
            # Helper to set result
            def set_result(field_key, json_key):
                if json_key in eval_json:
                    data = eval_json[json_key]
                    score = float(data.get("score", 0.0))
                    reason = data.get("reason", "")
                    
                    res = FieldValidationResult(
                        field_type=field_key,
                        field_value=getattr(chunk, field_key.value, None),
                        is_valid=score >= 0.5,
                        score=score
                    )
                    if score < 0.7:
                        res.warnings.append(reason)
                    if score < 0.4:
                        res.issues.append(f"Low quality: {reason}")
                    
                    res.metadata["judge_feedback"] = reason
                    report.field_results[field_key.value] = res
                else:
                    # Fallback if LLM missed it or grouped it
                    # Use heuristic validation as fallback? Or just mark as unchecked?
                    # Let's map social dynamics to the 'social_dynamics' score if available
                    if json_key == "social_dynamics" and "social_dynamics" in eval_json:
                         data = eval_json["social_dynamics"]
                         score = float(data.get("score", 0.0))
                         reason = data.get("reason", "")
                         res = FieldValidationResult(
                            field_type=field_key,
                            field_value=getattr(chunk, field_key.value, None),
                            is_valid=score >= 0.5,
                            score=score
                         )
                         if score < 0.7: res.warnings.append(reason)
                         report.field_results[field_key.value] = res

            
            set_result(EnrichmentFieldType.NARRATIVE_SUMMARY, "narrative_summary")
            set_result(EnrichmentFieldType.QUESTIONS, "questions")
            set_result(EnrichmentFieldType.SPEAKER_INTENTS, "speaker_intents")
            set_result(EnrichmentFieldType.ENTITIES, "entities")
            set_result(EnrichmentFieldType.EMOTIONS, "emotions")
            set_result(EnrichmentFieldType.TEMPORAL_CONTEXT, "temporal_context")
            
            # Map social dynamics fields to the single social score
            set_result(EnrichmentFieldType.INTERACTION_PATTERN, "social_dynamics")
            set_result(EnrichmentFieldType.INITIATIVE, "social_dynamics")
            set_result(EnrichmentFieldType.EMOTIONAL_SHIFT, "social_dynamics")
            set_result(EnrichmentFieldType.OPEN_LOOPS, "social_dynamics") # Not exactly social, but close enough for this summary prompt
            
            # Recalculate overall metrics based on LLM scores
            self._calculate_overall_metrics(report)
            return report

        except Exception as e:
            print(f"LLM Judge failed: {e}")
            # Fallback to heuristic validation
            return self.validate_chunk(chunk)
