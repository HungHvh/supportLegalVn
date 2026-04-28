# Phase 7 Research: Frontend UI Integration

## Backend API Endpoints
Based on `app.py` and `api/v1/endpoints.py`, the FastAPI backend exposes:
- `POST /api/v1/ask`: Synchronous endpoint returning `{"answer": "...", "citations": [...]}`.
- `POST /api/v1/stream`: Streaming endpoint using Server-Sent Events (SSE). Streams tokens `{"token": "..."}` and ends with `{"status": "completed"}`.

## Frontend Technology
- **Next.js (TypeScript)**: React framework with App Router. We will bootstrap it using `create-next-app`.
- **Vercel AI SDK**: Highly recommended for the chat interface, specifically `useChat` hook, which handles SSE streaming out of the box.

## UI Design (Split-screen Dashboard)
- Left Pane: Displays citations/legal text. Needs a structured display of the retrieved context.
- Right Pane: Chatbot interface.

## Cross-Origin Resource Sharing (CORS)
- The backend `app.py` reads `ALLOWED_ORIGINS` from the environment. Locally, this needs to be `http://localhost:3000` to allow the Next.js frontend to communicate with the FastAPI backend on port 8000.

## Implementation Steps
1. **Bootstrap Next.js Project**: Initialize in a `frontend/` directory.
2. **Tailwind CSS + shadcn/ui**: For rapid, professional styling.
3. **API Client**: Implement service functions to call `/api/v1/stream`.
4. **Layout**: Split screen using CSS Grid or Flexbox.
5. **Context Syncing**: Modify the streaming backend to return citations either in the first frame or the last frame so the frontend can render them in the left pane. (Currently `stream` only yields tokens, then `done`. It may need modification to return `citations` if we want the split pane to work efficiently, OR we use the synchronous `/ask` endpoint initially).
