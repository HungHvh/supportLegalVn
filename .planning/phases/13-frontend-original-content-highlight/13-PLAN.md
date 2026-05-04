---
wave: 1
depends_on: []
files_modified:
  - frontend/src/components/MainPane.tsx
  - frontend/src/hooks/useSearchHighlight.ts
autonomous: false
---

# Phase 13: Frontend Original Content Display with Highlights

## Goal
Integrate the Phase 12 Legal Search API into the existing Phase 7 split-screen layout (MainPane) to display full original articles with highlighted keywords, including smooth scrolling, highlighting navigation, and empty/error states.

## Tasks

<task id="13.1" name="Implement useSearchHighlight hook for API integration and state">
  <read_first>
    - frontend/src/components/MainPane.tsx
    - .planning/phases/13-frontend-original-content-highlight/13-CONTEXT.md
  </read_first>
  <action>
    Create a new React hook `frontend/src/hooks/useSearchHighlight.ts` to manage the state for document highlighting.
    1. Define the state variables:
       - `activeHighlightIndex` (number)
       - `highlightCount` (number)
       - `loading` (boolean)
       - `error` (string | null)
       - `articleData` (object containing `content` and `highlights` array)
    2. Add navigation functions: `nextHighlight` and `prevHighlight` to safely increment/decrement `activeHighlightIndex`.
    3. Implement a data fetching effect (`useEffect`) that calls the Phase 12 Legal Search API endpoint when a new `articleId` and `query` are provided.
    4. Handle loading and error states during the fetch, setting `articleData` on success.
  </action>
  <acceptance_criteria>
    - `frontend/src/hooks/useSearchHighlight.ts` exists and exports the `useSearchHighlight` function.
    - Hook returns `activeHighlightIndex`, `highlightCount`, `loading`, `error`, `articleData`, `nextHighlight`, and `prevHighlight`.
    - Fetching logic correctly sets loading true/false and populates `error` on failure.
  </acceptance_criteria>
</task>

<task id="13.2" name="Update MainPane component to render highlights and navigation">
  <read_first>
    - frontend/src/components/MainPane.tsx
    - frontend/src/hooks/useSearchHighlight.ts
    - .planning/phases/13-frontend-original-content-highlight/13-CONTEXT.md
  </read_first>
  <action>
    Update the `MainPane.tsx` document viewer component to display the original content with highlights and navigation controls.
    1. Import and use the `useSearchHighlight` hook.
    2. Render States:
       - **Loading:** Display a skeleton or spinner.
       - **Error:** Retain previous article if available, display a short error toast/message with a "Retry" button.
       - **Empty/No Highlights:** Render plain article text and show message: "Không tìm thấy đoạn khớp từ khóa trong nội dung gốc."
    3. Render the `articleData.content` string, replacing highlight positions with `<mark>` tags.
       - **Default `<mark>`:** Light background (e.g., pale yellow/blue), slight border radius, original text color.
       - **Active `<mark>`:** Slightly darker background for the highlight matching `activeHighlightIndex`.
    4. Navigation Controls: Add a fixed or sticky control bar containing "Previous" and "Next" buttons and a counter (e.g., `activeHighlightIndex + 1 / highlightCount`). Hook buttons to `prevHighlight` and `nextHighlight`.
    5. Add a `useEffect` that triggers `scrollIntoView` for the active `<mark>` element. Ensure it triggers only on initial load or when the user navigates via buttons, not arbitrarily on re-renders.
  </action>
  <acceptance_criteria>
    - `frontend/src/components/MainPane.tsx` imports and calls `useSearchHighlight`.
    - Component renders `<mark>` tags mapping to the text matches.
    - The active highlight element receives a specific CSS class or inline style for darker background.
    - Previous/Next buttons and a counter (e.g., "1 / 5") are rendered in the UI.
    - Loading spinner/skeleton and error states are properly rendered.
  </acceptance_criteria>
</task>

## Verification
- [ ] Ensure selecting an article triggers the Phase 12 Search API.
- [ ] Verify that highlight navigation buttons cycle through matches correctly.
- [ ] Confirm smooth scrolling only happens on initial load or navigation click, preventing jitter.
- [ ] Verify error and empty states render gracefully in the `MainPane`.
