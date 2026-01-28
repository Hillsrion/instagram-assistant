"use client"

import { useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { ChevronDown, AlertCircle, MessageCircle, BarChart3 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import { getChunkContent } from "@/lib/api"
import type { Source, SummarySource } from "@/lib/types"

interface SourcesModalProps {
  sources: Source[]
  summaryources: SummarySource[]
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SourcesModal({
  sources,
  summaryources,
  open,
  onOpenChange,
}: SourcesModalProps) {
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set())
  console.log(sources);
  
  // Fetch all chunk content in parallel
  const chunkQueries = useQueries({
    queries: sources.map((source) => ({
      queryKey: ["chunk", source.chunk_id],
      queryFn: () => getChunkContent(source.chunk_id),
      enabled: open && sources.length > 0,
    })),
  })

  const toggleExpanded = (chunkId: string) => {
    const newExpanded = new Set(expandedChunks)
    if (newExpanded.has(chunkId)) {
      newExpanded.delete(chunkId)
    } else {
      newExpanded.add(chunkId)
    }
    setExpandedChunks(newExpanded)
  }

  const handleOpenChange = (newOpen: boolean) => {
    onOpenChange(newOpen)
    if (!newOpen) {
      setExpandedChunks(new Set())
    }
  }

  const hasConversationSources = sources.length > 0
  const hasSummarySources = summaryources.length > 0

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl w-full h-[80vh] flex flex-col gap-4 p-0">
        <div className="px-6 py-4 border-b">
          <DialogTitle>Sources</DialogTitle>
        </div>

        <ScrollArea className="flex-1">
          <div className="space-y-6 px-6">
            {/* Conversation Excerpts Section */}
            {hasConversationSources && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <MessageCircle className="h-5 w-5 text-blue-600" />
                  <h3 className="text-sm font-semibold text-foreground">
                    Extraits de conversations
                  </h3>
                  <span className="text-xs text-muted-foreground ml-auto">
                    {sources.length}
                  </span>
                </div>

                <div className="space-y-2">
                  {sources.map((source, idx) => {
                    const chunkData = chunkQueries[idx]?.data
                    const isExpanded = expandedChunks.has(source.chunk_id)
                    const isLoading = chunkQueries[idx]?.isLoading
                    const isError = chunkQueries[idx]?.isError

                    return (
                      <div
                        key={source.chunk_id}
                        className="border border-slate-200 rounded-lg overflow-hidden hover:border-slate-300 transition-colors"
                      >
                        <button
                          onClick={() => toggleExpanded(source.chunk_id)}
                          className="w-full p-3 text-left hover:bg-slate-50 transition-colors"
                        >
                          <div className="flex items-start gap-3">
                            <ChevronDown
                              className={cn(
                                "h-4 w-4 mt-0.5 flex-shrink-0 transition-transform",
                                isExpanded && "rotate-180"
                              )}
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-medium px-2 py-1 rounded bg-blue-100 text-blue-700">
                                  conversation
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  Score: {source.score.toFixed(2)}
                                </span>
                              </div>
                              <div className="text-xs text-muted-foreground mb-2">
                                {source.participants.join(", ")} •{" "}
                                {source.date_start}
                              </div>
                              <p className="text-sm text-foreground line-clamp-2">
                                {source.preview}
                              </p>
                            </div>
                          </div>
                        </button>

                        {isExpanded && (
                          <div className="border-t bg-slate-50 p-3">
                            {isLoading && (
                              <div className="text-sm text-muted-foreground">
                                Loading full content...
                              </div>
                            )}
                            {isError && (
                              <div className="flex items-center gap-2 text-sm text-red-600">
                                <AlertCircle className="h-4 w-4" />
                                Failed to load content
                              </div>
                            )}
                            {chunkData && (
                              <div className="space-y-3 text-sm">
                                <div>
                                  <p className="text-xs font-semibold text-muted-foreground mb-1">
                                    CONTENT
                                  </p>
                                  <p className="text-foreground whitespace-pre-wrap">
                                    {chunkData.content}
                                  </p>
                                </div>
                                {chunkData.hypothetical_questions?.length >
                                  0 && (
                                  <div>
                                    <p className="text-xs font-semibold text-muted-foreground mb-1">
                                      QUESTIONS
                                    </p>
                                    <ul className="space-y-1">
                                      {chunkData.hypothetical_questions.map(
                                        (q, i) => (
                                          <li
                                            key={i}
                                            className="text-foreground flex gap-2"
                                          >
                                            <span className="flex-shrink-0">
                                              •
                                            </span>
                                            <span>{q}</span>
                                          </li>
                                        )
                                      )}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Summary Sources Section */}
            {hasSummarySources && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-amber-600" />
                  <h3 className="text-sm font-semibold text-foreground">
                    Résumés
                  </h3>
                  <span className="text-xs text-muted-foreground ml-auto">
                    {summaryources.length}
                  </span>
                </div>

                <div className="space-y-2">
                  {summaryources.map((summary) => (
                    <div
                      key={summary.summary_id}
                      className="border border-amber-200 bg-amber-50 rounded-lg p-3 hover:border-amber-300 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium px-2 py-1 rounded bg-amber-100 text-amber-700">
                              résumé
                            </span>
                            <span className="text-xs text-amber-700">
                              Score: {summary.score.toFixed(2)}
                            </span>
                          </div>
                          <div className="text-xs text-amber-700 mb-2">
                            {summary.participants.join(", ")} • {summary.period}
                          </div>
                          <p className="text-sm text-amber-900">
                            {summary.preview}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!hasConversationSources && !hasSummarySources && (
              <div className="text-center py-8 text-muted-foreground">
                No sources available
              </div>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
