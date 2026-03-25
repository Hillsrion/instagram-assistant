# Sira - Frontend

Modern web interface for the Sira RAG system, built with React, Vite, and TanStack.

## Tech Stack
- **Framework**: [React 19](https://react.dev) + [Vite](https://vitejs.dev)
- **Routing**: [TanStack Router](https://tanstack.com/router) (File-based routing)
- **State Management**: [TanStack Query](https://tanstack.com/query)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com) + [Shadcn UI](https://ui.shadcn.com)
- **Streaming**: `@microsoft/fetch-event-source`

## Getting Started

### Prerequisites
- Node.js 18+
- pnpm

### Installation

```bash
cd frontend
pnpm install
```

### Development

Start the development server. API requests will be proxied to the Python backend at `http://localhost:8000`.

```bash
pnpm dev
```

### Build

Build the application for production.

```bash
pnpm build
```

The output will be in `dist/`.

## Directory Structure
- `src/routes`: File-based routes (TanStack Router).
- `src/components/ui`: Shadcn UI components.
- `src/components/layout`: Application shell (Sidebar, etc.).
- `src/lib`: API client and types.
- `src/hooks`: Custom hooks (e.g., streaming logic).
