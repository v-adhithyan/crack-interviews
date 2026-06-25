# HackerLeap Code Design Notes

Use the question-solving page as the source of truth for the coding platform UI.

## App Shell

- Use the compact `AppHeader` toolbar at the top of coding-platform pages.
- Header layout is always: brand on the left, primary actions in the center, secondary/status actions on the right.
- Keep the header full width with `min-h-16`, `border-b border-line`, `bg-white/75`, and `px-4`.
- Use the shared `BrandMark` logo only. Do not introduce alternate icons for HackerLeap.
- Page-specific titles, back links, subtitles, and metadata belong in the content area below the toolbar, not inside the toolbar.

## Page Body

- Use `bg-paper text-ink` for page backgrounds.
- Keep content inside `mx-auto` containers with `px-6 py-8`.
- Use `max-w-6xl` for list/detail pages and `max-w-7xl` when code/results need two columns.
- Prefer dense, scannable operational layouts over large document-style headers.
- Cards should be simple white panels with `rounded-lg`, subtle border, and `shadow-product`.

## Controls

- Primary actions use gold styling, matching the Submit button.
- Secondary actions use white buttons with `border-line`.
- Status values use compact badges via `StatusBadge`; badges should not stretch to fill table columns.
- Language selectors use segmented controls with the active segment on `bg-soft`.

## Tables And Lists

- Keep table headers in `bg-[#fffaf0]` with uppercase muted labels.
- Rows should be roomy enough to scan but not oversized.
- Avoid layouts where long labels or badges push into the next column.

## Code Surfaces

- Monaco/editor surfaces stay dark and visually dominant on code pages.
- Code panels should have stable width constraints and `min-w-0` so they never collapse into a narrow strip.
- Results/output text should wrap or scroll inside its own container, never force the page grid wider.

## Footer / Account Controls

- There is no large footer on the coding platform.
- The admin/account chip stays fixed at bottom-left and should not cover code or result panels.
