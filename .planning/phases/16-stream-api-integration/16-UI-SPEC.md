# UI Design Contract: Phase 16 - Stream API Integration

## 1. Interaction Flow: Chat Streaming

### Sequence of Events
1. **Submit**: User sends query. Add User message to list.
2. **Init Agent Message**: Add a placeholder Agent message with `content: ""` and `streaming: true`.
3. **Citations Received**: Event `type: citations` arrives. Update global `citations` state immediately. **MainPane** should react and show results even before text starts.
4. **Token Stream**: Event `type: token` arrives. Append content to the last Agent message.
5. **Classification Arrival**: Event `type: classification` arrives. Update the `domains` metadata for the current message.
6. **Completion**: Event `type: done` arrives. Set `streaming: false`.

## 2. Visual Specifications

### Message Bubble (Agent)
- **Token Rendering**: Use standard `whitespace-pre-wrap` for smooth multi-line rendering.
- **Typing Indicator**: When `streaming: true` and content is empty, show a subtle pulsing dot or cursor. Remove "Đang phân tích..." static text once tokens begin.

### Classification Badges (New Component)
- **Location**: Top of the Agent message bubble, below the Bot avatar but above the text content.
- **Style**: Small, rounded tags.
- **Colors (Brand Alignment)**:
  - `Hình sự`: Background `bg-red-50`, Text `text-red-600`, Border `border-red-100`.
  - `Dân sự`: Background `bg-blue-50`, Text `text-blue-600`, Border `border-blue-100`.
  - `Hành chính`: Background `bg-amber-50`, Text `text-amber-600`, Border `border-amber-100`.
  - `Default`: Background `bg-zinc-100`, Text `text-zinc-600`.
- **Animation**: Fade-in transition when the `classification` event triggers.

### Citations (MainPane)
- **Update Behavior**: Instant update. As soon as the first SSE frame (`citations`) is parsed, the left pane must populate with article highlights.

## 3. Error States
- **Stream Interruption**: If the stream fails or an `error` event is received:
  - Display an `AlertTriangle` icon inside the message bubble.
  - Text color: `text-red-500`.
  - Background: `bg-red-50`.
  - Message: "Lỗi kết nối trong quá trình tạo câu trả lời. Vui lòng thử lại."

## 4. Technical Constraints (Frontend)
- **API Client**: Must use standard `EventSource` (GET) for the primary stream to ensure native browser handling of SSE and prevent intermediate buffering.
- **Data Transfer**: Use Base64 encoding for the `chat_history` query parameter to stay within URL length limits and handle special characters.
- **State Management**: Use functional updates `setMessages(prev => ...)` to ensure the streaming text doesn't cause race conditions or unnecessary full-list re-renders.

## 5. Copywriting
- **Placeholder**: "Đang kết nối thư viện pháp luật..." (while waiting for first frame).
- **Done signal**: No explicit text, just removal of active cursor.
