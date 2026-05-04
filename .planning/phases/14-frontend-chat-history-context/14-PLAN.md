---
wave: 1
depends_on: []
files_modified:
  - api/models.py
  - core/rag_pipeline.py
  - api/v1/endpoints.py
  - frontend/src/app/page.tsx
autonomous: false
---

# Phase 14: Frontend Chat History Retention and RAG Context Loop

## Goal
Implement frontend chat history context retention to improve RAG query quality for follow-up questions using contextual query rewriting and a sliding window.

## Verification
- [ ] Send a follow-up question referencing previous context (e.g., "what about for a 5 year old company?").
- [ ] Inspect network request to verify `chat_history` is sent with exactly the last N messages.
- [ ] Inspect backend logs to confirm the query was rewritten before vector search.
- [ ] Verify the RAG response correctly incorporates the previous context.

---

## Tasks

```xml
<task id="1">
  <title>Update AskRequest Model to Accept Chat History</title>
  <description>Modify the API models to support receiving chat history from the frontend.</description>
  <read_first>
    - api/models.py
  </read_first>
  <action>
    Modify `api/models.py`.
    Add a new `ChatMessage` model:
    ```python
    class ChatMessage(BaseModel):
        role: str
        content: str
    ```
    Update the `AskRequest` model to include an optional `chat_history` field:
    ```python
    class AskRequest(BaseModel):
        query: str = Field(..., example="Thủ tục thành lập công ty TNHH")
        chat_history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Recent conversation history")
    ```
  </action>
  <acceptance_criteria>
    - `api/models.py` contains `ChatMessage` model definition.
    - `api/models.py` `AskRequest` contains `chat_history` field of type `Optional[List[ChatMessage]]`.
  </acceptance_criteria>
</task>

<task id="2">
  <title>Implement Contextual Query Rewriting in RAG Pipeline</title>
  <description>Add query rewriting logic to the RAG pipeline to resolve coreferences and context from chat history before retrieval.</description>
  <read_first>
    - core/rag_pipeline.py
    - .planning/phases/14-frontend-chat-history-context/14-CONTEXT.md
  </read_first>
  <action>
    Modify `core/rag_pipeline.py`.
    1. Add an async method `arewrite_query(self, query: str, chat_history: List[dict]) -> str` to `LegalRAGPipeline`.
    2. The rewrite prompt should be:
       "Dựa vào lịch sử trò chuyện dưới đây, hãy viết lại câu hỏi tiếp theo của người dùng thành một câu hỏi duy nhất, độc lập và rõ ràng, chứa đầy đủ ngữ cảnh để có thể tìm kiếm tài liệu pháp luật. Nếu câu hỏi đã rõ ràng, hãy giữ nguyên. Không trả lời câu hỏi, chỉ viết lại câu hỏi.\n\nLịch sử:\n{history}\n\nCâu hỏi tiếp theo: {query}\n\nCâu hỏi được viết lại:"
    3. Update `acustom_query(self, query_str: str, chat_history: Optional[List[Any]] = None)`:
       - If `chat_history` is provided and not empty, call `self.arewrite_query` to get `search_query`.
       - Use `search_query` for `self.retriever.aretrieve(search_query)`.
       - Format `chat_history` into a string and append it to the `qa_prompt_template` (or inject it) so the LLM has context for generation. Modify `qa_prompt_template` to accept a `{chat_history_str}` placeholder.
    4. Apply the same logic to `astream_query`.
  </action>
  <acceptance_criteria>
    - `core/rag_pipeline.py` contains `arewrite_query` method.
    - `acustom_query` accepts `chat_history` argument.
    - `astream_query` accepts `chat_history` argument.
    - The LLM is used to rewrite the query before `self.retriever.aretrieve`.
  </acceptance_criteria>
</task>

<task id="3">
  <title>Update API Endpoints to Pass Chat History</title>
  <description>Update the FastAPI endpoints to pass the new chat_history field to the RAG pipeline.</description>
  <read_first>
    - api/v1/endpoints.py
  </read_first>
  <action>
    Modify `api/v1/endpoints.py`.
    1. In `@router.post("/ask")`, update the call: 
       `result = await pipeline.acustom_query(request.query, request.chat_history)`
    2. In `@router.post("/stream")`, update the call:
       `async for token in pipeline.astream_query(request.query, request.chat_history):`
  </action>
  <acceptance_criteria>
    - `api/v1/endpoints.py` passes `request.chat_history` to `pipeline.acustom_query`.
    - `api/v1/endpoints.py` passes `request.chat_history` to `pipeline.astream_query`.
  </acceptance_criteria>
</task>

<task id="4">
  <title>Update Frontend State to Send Chat History</title>
  <description>Update the frontend to implement a sliding window of chat history and send it to the backend.</description>
  <read_first>
    - frontend/src/app/page.tsx
  </read_first>
  <action>
    Modify `frontend/src/app/page.tsx`.
    1. In `handleSendMessage`, extract the last 4 messages (2 pairs of user/agent) from the `messages` array:
       `const chatHistoryWindow = messages.slice(-4);`
    2. Update the `fetch` body to include `chat_history`:
       `body: JSON.stringify({ query: content, chat_history: chatHistoryWindow }),`
  </action>
  <acceptance_criteria>
    - `frontend/src/app/page.tsx` slices the `messages` array before sending.
    - `fetch` payload includes `chat_history: chatHistoryWindow`.
  </acceptance_criteria>
</task>
```
