import { createRootRoute, Outlet } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/router-devtools'
import { Sidebar } from '@/components/layout/sidebar'

export const Route = createRootRoute({
  component: () => (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground font-sans antialiased">
        <Sidebar />
        <main className="flex-1 flex flex-col overflow-hidden">
          <Outlet />
        </main>
      <TanStackRouterDevtools />
    </div>
  ),
})
