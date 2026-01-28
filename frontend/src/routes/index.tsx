import { createFileRoute, Link } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createConversation } from '@/lib/api'

export const Route = createFileRoute('/')({
  component: Index,
})

function Index() {
  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: () => createConversation(),
    onSuccess: (newConv) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      window.location.href = `/chat/${newConv.id}`
    }
  })

  return (
    <div className="p-8 flex flex-col items-center justify-center min-h-[50vh] gap-6">
      <div className="text-center">
        <h1 className="text-5xl font-extrabold tracking-tight mb-2">
          Instagram Assistant
        </h1>
        <p className="text-xl text-muted-foreground mb-8">
          Your AI-powered conversation analyzer
        </p>
      </div>

      <div className="flex gap-3 flex-wrap justify-center">
        <Button
          size="lg"
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
        >
          New Conversation
        </Button>
        <Link to="/analytics">
          <Button size="lg" variant="outline">
            View Analytics
          </Button>
        </Link>
      </div>

      <div className="mt-12 max-w-2xl bg-slate-50 rounded-lg p-6 border border-slate-200">
        <h2 className="text-lg font-semibold mb-3">Features</h2>
        <ul className="space-y-2 text-sm text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">✓</span>
            <span>Chat with your Instagram conversations using AI</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">✓</span>
            <span>View detailed analytics and statistics</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">✓</span>
            <span>Track conversations with participants over time</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-blue-500 font-bold">✓</span>
            <span>100% private - all data stays local</span>
          </li>
        </ul>
      </div>
    </div>
  )
}
