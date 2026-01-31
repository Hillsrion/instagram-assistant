import { useState, useEffect, useRef } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Progress } from '@/components/ui/progress'
import { Dropzone, DropzoneContent, DropzoneEmptyState } from '@/components/ui/dropzone'
import { startImport, listImportedConversations, startRag, uploadFile, browseFolder } from '@/lib/api'
import { Loader2, FolderInput, Play, CheckCircle, ListFilter, Terminal, FolderOpen } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

export const Route = createFileRoute('/onboarding')({
  component: Onboarding,
})

type Step = 1 | 2 | 3
type JobStatus = 'pending' | 'running' | 'completed' | 'failed'

function Onboarding() {
  const [step, setStep] = useState<Step>(1)
  
  // Step 1: Import
  const [importPath, setImportPath] = useState('')
  const [importing, setImporting] = useState(false)
  const [importJobId, setImportJobId] = useState<string | null>(null)
  const [files, setFiles] = useState<File[] | undefined>(undefined)
  const [uploading, setUploading] = useState(false)
  const [browsing, setBrowsing] = useState(false)
  
  // Step 2: Filter
  const [conversations, setConversations] = useState<any[]>([])
  const [minMessages, setMinMessages] = useState(10)
  const [loadingConvs, setLoadingConvs] = useState(false)
  
  // Step 3: RAG
  const [ragJobId, setRagJobId] = useState<string | null>(null)
  const [ragStatus, setRagStatus] = useState<JobStatus>('pending')
  const [ragLogs, setRagLogs] = useState<string[]>([])
  
  const navigate = useNavigate()

  // --- Step 1 Handlers ---
  
  const handleDrop = async (acceptedFiles: File[]) => {
    setFiles(acceptedFiles)
    if (acceptedFiles.length > 0) {
      // Auto upload the first file
      try {
        setUploading(true)
        const file = acceptedFiles[0]
        toast.info(`Uploading ${file.name}...`)
        const { path } = await uploadFile(file)
        setImportPath(path)
        toast.success('File uploaded successfully!')
      } catch (e) {
        toast.error('Upload failed')
        console.error(e)
      } finally {
        setUploading(false)
      }
    }
  }

  const handleBrowse = async () => {
    try {
      setBrowsing(true)
      const { path } = await browseFolder()
      if (path) {
        setImportPath(path)
        toast.success('Folder selected!')
      }
    } catch (e) {
      toast.error('Failed to open folder dialog')
    } finally {
      setBrowsing(false)
    }
  }

  const handleImport = async () => {
    if (!importPath) {
      toast.error('Please select a path')
      return
    }
    
    try {
      setImporting(true)
      const { job_id } = await startImport(importPath)
      setImportJobId(job_id)
      
      // Start streaming logs immediately for import
      streamJob(job_id, (log) => {
        // We could show import logs, but for now just wait for completion
        console.log("Import log:", log)
      }, () => {
        setImporting(false)
        setStep(2)
        loadConversations()
        toast.success('Import completed!')
      })
      
    } catch (e) {
      toast.error('Failed to start import')
      setImporting(false)
    }
  }
  
  // --- Step 2 Handlers ---
  
  const loadConversations = async () => {
    setLoadingConvs(true)
    try {
      const data = await listImportedConversations()
      setConversations(data)
    } catch (e) {
      toast.error('Failed to load conversations')
    } finally {
      setLoadingConvs(false)
    }
  }
  
  const filteredCount = conversations.filter(c => c.msg_count >= minMessages).length

  const handleStartRag = async () => {
    try {
      setStep(3)
      setRagStatus('running')
      const { job_id } = await startRag(minMessages, true) // Force reset for clean start
      setRagJobId(job_id)
      
      streamJob(job_id, (log) => {
        setRagLogs(prev => [...prev, log])
      }, () => {
        setRagStatus('completed')
        toast.success('RAG Pipeline completed!')
      })
      
    } catch (e) {
      toast.error('Failed to start RAG pipeline')
      setRagStatus('failed')
    }
  }
  
  // --- Job Streamer ---
  
  const streamJob = (jobId: string, onLog: (l: string) => void, onComplete: () => void) => {
    const es = new EventSource(`/api/jobs/${jobId}/stream`)
    
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'log') {
          onLog(data.content)
        } else if (data.type === 'status') {
          if (data.status === 'completed' || data.status === 'failed') {
            es.close()
            onComplete()
          }
        }
      } catch (e) {
        // keep alive
      }
    }
    
    es.onerror = () => {
      es.close()
      // Optional: retry or handle error
    }
  }
  
  // Auto-scroll logs
  const logsEndRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [ragLogs])

  return (
    <div className="container max-w-4xl py-8 space-y-8">
      
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Setup Assistant</h1>
        <p className="text-muted-foreground">Import your Instagram data and prepare the AI knowledge base.</p>
      </div>
      
      {/* Stepper */}
      <div className="flex items-center space-x-4 mb-8">
        <StepIndicator step={1} current={step} title="Import" />
        <div className="h-[2px] w-12 bg-muted" />
        <StepIndicator step={2} current={step} title="Filter" />
        <div className="h-[2px] w-12 bg-muted" />
        <StepIndicator step={3} current={step} title="Index" />
      </div>

      {/* Step 1: Import */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FolderInput className="h-5 w-5" />
              Source Directory
            </CardTitle>
            <CardDescription>
               Select your <strong>original_import_folder</strong> or the extracted Instagram export folder.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            
            <div className="flex flex-col gap-4 items-center justify-center border-2 border-dashed rounded-lg p-8 bg-muted/20">
               <div className="text-center space-y-2">
                 <h3 className="font-semibold text-lg">Locate your Data</h3>
                 <p className="text-muted-foreground text-sm max-w-md">
                    Since your files are large (>2GB), avoid uploading them. Instead, simply select the folder on your computer.
                 </p>
               </div>
               
               <Button size="lg" onClick={handleBrowse} disabled={browsing}>
                 {browsing ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <FolderOpen className="mr-2 h-5 w-5" />}
                 Browse Folders...
               </Button>
            </div>

            <div className="relative">
                <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">Or upload zip (smaller files)</span>
                </div>
            </div>
            
            <Dropzone
                onDrop={handleDrop}
                src={files}
                maxFiles={1}
                accept={{ 'application/zip': ['.zip'] }}
                className="w-full h-24 border-dashed"
                disabled={uploading || importing}
            >
                <DropzoneContent />
                <DropzoneEmptyState />
            </Dropzone>

            <div className="flex gap-2 pt-4">
              <Input 
                placeholder="/Users/name/Downloads/instagram_export" 
                value={importPath}
                onChange={(e) => setImportPath(e.target.value)}
                disabled={importing || uploading}
              />
              <Button onClick={handleImport} disabled={importing || uploading || !importPath}>
                {importing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {importing ? 'Importing...' : 'Start Import'}
              </Button>
            </div>
            
            {importing && (
               <div className="p-4 bg-muted rounded-md text-sm text-muted-foreground">
                 <p>Converting JSON to Text... This may take a while depending on the size.</p>
               </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Step 2: Filter */}
      {step === 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ListFilter className="h-5 w-5" />
              Filter Conversations
            </CardTitle>
            <CardDescription>
              Select which conversations to index. Filtering out short conversations saves time and space.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-end gap-4">
              <div className="space-y-2 flex-1">
                <label className="text-sm font-medium">Minimum Messages</label>
                <Input 
                  type="number" 
                  value={minMessages}
                  onChange={(e) => setMinMessages(parseInt(e.target.value) || 0)}
                />
              </div>
              <div className="pb-2 text-sm text-muted-foreground">
                Keeps {filteredCount} / {conversations.length} conversations
              </div>
            </div>
            
            <ScrollArea className="h-[300px] border rounded-md p-4">
              {loadingConvs ? (
                <div className="flex justify-center p-4"><Loader2 className="animate-spin" /></div>
              ) : (
                <div className="space-y-2">
                  {conversations.map(c => {
                     const isKept = c.msg_count >= minMessages
                     return (
                       <div key={c.id} className={cn("flex justify-between items-center p-2 rounded", isKept ? "bg-accent/50" : "opacity-50")}>
                         <div className="flex flex-col">
                           <span className="font-medium">{c.title}</span>
                           <span className="text-xs text-muted-foreground">{c.date_range}</span>
                         </div>
                         <div className="text-sm font-mono bg-background px-2 py-1 rounded border">
                           {c.msg_count} msgs
                         </div>
                       </div>
                     )
                  })}
                </div>
              )}
            </ScrollArea>
            
            <div className="flex justify-end">
              <Button onClick={handleStartRag} size="lg">
                <Play className="mr-2 h-4 w-4" />
                Start Indexing
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: RAG */}
      {step === 3 && (
        <Card className="flex flex-col h-[600px]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="h-5 w-5" />
              Indexing Pipeline
            </CardTitle>
            <CardDescription>
              Building the knowledge base. This involves chunking, enrichment (LLM), embedding, and indexing.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col space-y-4 overflow-hidden">
            {ragStatus === 'running' && <Progress value={33} className="animate-pulse" />} 
            {/* Note: Real progress value requires parsing logs or backend updates. Using generic for now or we could parse "Step X/8" */}
            
            <div className="flex-1 bg-black text-green-400 font-mono text-xs p-4 rounded-md overflow-hidden relative">
              <ScrollArea className="h-full w-full">
                <div className="space-y-1">
                  {ragLogs.map((log, i) => (
                    <div key={i} className="break-words">{log}</div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              </ScrollArea>
            </div>
            
            {ragStatus === 'completed' && (
              <div className="flex justify-center pt-4">
                <Button onClick={() => navigate({ to: '/' })} size="lg" className="w-full sm:w-auto">
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Go to Chat
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

    </div>
  )
}

function StepIndicator({ step, current, title }: { step: number, current: number, title: string }) {
  const isActive = current === step
  const isCompleted = current > step
  
  return (
    <div className="flex items-center gap-2">
      <div className={cn(
        "flex items-center justify-center w-8 h-8 rounded-full border-2 text-sm font-bold transition-colors",
        isActive ? "border-primary bg-primary text-primary-foreground" :
        isCompleted ? "border-primary bg-primary text-primary-foreground" :
        "border-muted-foreground text-muted-foreground"
      )}>
        {isCompleted ? <CheckCircle className="h-4 w-4" /> : step}
      </div>
      <span className={cn(
        "font-medium",
        isActive || isCompleted ? "text-foreground" : "text-muted-foreground"
      )}>{title}</span>
    </div>
  )
}
