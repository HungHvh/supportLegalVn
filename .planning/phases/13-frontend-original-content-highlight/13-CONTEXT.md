# Phase 13 Context: Frontend Original Content Display with Highlights

## Domain
Displaying original legal articles with highlighted keywords in the Next.js Frontend. This involves integrating the Phase 12 Search API into the existing Phase 7 split-screen layout.

## Decisions

### 1. UI / Layout
- **Decision:** Display directly within the existing document viewer pane of the split-screen layout.
- **Details:** No modals or new tabs. The viewer will render the original full content returned by the API, with highlights directly mapped to `<mark>` or custom `<span>` tags within the text. Long articles will maintain scrolling within the current pane to preserve the IRAC context alongside the original text.

### 2. Highlight Styling & Auto-scroll
- **Decision:** Use "eye-friendly" highlights with visual hierarchy and conservative auto-scrolling.
- **Details:**
  - **Default Highlight:** Light background (e.g., pale yellow or blue), original text color, slight border-radius to prevent layout shifts.
  - **Active Highlight:** Slightly darker background to indicate the current position.
  - **Hover State:** Add a border or increase contrast for interactivity.
  - **Auto-scroll:** Strictly trigger *only* upon initial article load or a new search to avoid jarring jumps during React re-renders.

### 3. Highlight Navigation
- **Decision:** Implement navigation controls for articles with multiple matches.
- **Details:** Include "Previous" and "Next" buttons along with a counter (e.g., "2 / 7"). Navigation should utilize smooth scrolling to the active highlight, and the active state must remain synchronized with the user's viewport.

### 4. Error / Empty States
- **Decision:** Handle loading, no-match, and error states gracefully without clearing the viewer entirely.
- **Details:**
  - **Loading:** Display a skeleton or spinner inside the viewer pane.
  - **No Highlights Found:** Render the plain original article text, accompanied by a gentle message ("Không tìm thấy đoạn khớp từ khóa trong nội dung gốc.").
  - **API Error:** Retain the previously loaded article (if any) and display a short error toast/message with a "Retry" button.

## Technical Proposal & State Needs
- **Integration:** Consume the Phase 12 API (`full content` + `highlight positions`).
- **State required:** `activeHighlightIndex`, `highlightCount`, `loading`, `error`.
- **Mapping:** Frontend will map highlight positions to DOM nodes cleanly.

## Canonical Refs
- Phase 7 (Frontend Split-screen layout structure)
- Phase 12 (Legal Search API response format)

## Deferred Ideas
*(None)*
