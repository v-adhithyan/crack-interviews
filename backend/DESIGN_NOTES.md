# Backend Product Design Notes

## Dashboard Hero Pattern

Use the dashboard top section as the product-page hero pattern:

- Left side: direct, outcome-oriented heading with a light emoji accent, followed by one concise supporting sentence.
- Right side: a compact action/status card, visually separate from the hero copy.
- Card styling: white surface, subtle border, 8px radius, soft product shadow, and a full-width gold gradient primary action.
- Layout: two-column grid on desktop with the action card on the right; stack to one column on smaller screens.
- Page structure: the hero owns the vertical gap before the first content card. Keep the first content card flush to that shared spacing token instead of adding page-specific padding or extra margins.
- Consistency: reuse the same right-side card width, compact upload icon size, padding, and primary button treatment across dashboard-like pages.
- Tone: practical and encouraging, focused on the user's next action.

Reference implementation:

- Template: `backend/apps/product/templates/product/dashboard.html`
- CSS: `.dashboard-hero`, `.active-resume-card`, `.resume-row`, `.resume-icon`, `.resume-replace-button`
