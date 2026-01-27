import { createFileRoute } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/')({
  component: Index,
})

function Index() {
  return (
    <div className="p-8 flex flex-col items-center justify-center min-h-[50vh] gap-4">
      <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl">
        Instagram Assistant
      </h1>
      <p className="text-xl text-muted-foreground">
        Your AI-powered conversation analyzer.
      </p>
      <div className="flex gap-2">
        <Button>New Conversation</Button>
        <Button variant="outline">History</Button>
      </div>
    </div>
  )
}
