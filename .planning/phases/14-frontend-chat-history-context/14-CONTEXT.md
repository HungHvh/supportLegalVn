# Phase 14: Frontend Chat History Retention and RAG Context Loop - Context

## Scope Boundary
This phase focuses strictly on implementing chat history retention and contextual query rewriting to improve the accuracy of follow-up questions in the RAG pipeline.

## Locked Decisions

<decisions>
- **Context State Ownership**: **Stateless Backend**. The frontend will maintain the chat history state. It will send the `chat_history` (previous message pairs) along with the new `query` in every `/api/v1/ask` request. The backend will not store session state.
- **Query Resolution Strategy**: **Contextual Query Rewriting**. The backend will use a fast, low-latency LLM (like Groq) to rewrite the user's raw follow-up query using the provided chat history *before* performing the vector search. This ensures search accuracy for ambiguous follow-up questions (e.g., "how do I complain?").
- **History Pruning Strategy**: **Sliding Window**. Only the last 3 to 5 message pairs will be retained/sent to the backend. This acts as a rolling context window to keep token usage low and ensure only the most relevant recent context is used for query rewriting.
</decisions>

## Specifics & Edge Cases
- The query rewriting step must be extremely fast to avoid adding significant latency to the user experience.
- The `chat_history` format should be compatible with standard LLM message formats (e.g., array of objects with `role` and `content`).

## Canonical References
- `frontend/src/app/page.tsx` (Where state is managed and API is called)
- `frontend/src/components/ChatSidebar.tsx` (UI for chat history)
- `api/v1/endpoints.py` (Backend endpoint to be updated to accept `chat_history`)
