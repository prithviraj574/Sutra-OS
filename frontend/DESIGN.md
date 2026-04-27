# Talaria Design System

## Intent

Talaria should feel calm, light, and precise. The visual system uses Ethereal Minimalism: hierarchy is created through spacing, luminance, and soft elevation rather than borders or decorative noise.

Talaria should use `shadcn/ui` as much as possible. Start from `shadcn` primitives and variants first, and only introduce custom components when the requirement cannot reasonably be met through composition or extension.

## Current Implementation Reality

- This frontend already has a `shadcn`-compatible token layer in [globals.css](./src/globals.css).
- It already has a reusable foundation class layer in [index.css](./src/index.css).
- It already has app-specific composition styles in [App.css](./src/App.css).
- It already has Tailwind shadow extensions in [tailwind.config.js](./tailwind.config.js).
- It does not yet have the full `shadcn/ui` component library installed.

Because of that, current UI work should follow this rule:

- Use `shadcn/ui` components whenever they exist in the repo.
- Until they exist, build from shared Talaria tokens and shared Talaria classes only.
- Do not hardcode visual values inside feature-level UI code.

## Source Of Truth

- Tokens: [globals.css](./src/globals.css)
- Reusable foundation classes: [index.css](./src/index.css)
- Screen composition classes: [App.css](./src/App.css)
- Tailwind theme extension: [tailwind.config.js](./tailwind.config.js)

If implementation and documentation diverge, update the implementation back toward the system instead of inventing a local exception.

## Non-Negotiable Rule

Do not hardcode visual values in component-level UI code when the value can live in a token or shared class.

This applies to:

- colors
- shadows
- radii
- spacing
- focus rings
- transitions
- gradients
- semantic status states
- font stacks
- width constraints used repeatedly
- responsive page spacing
- touch target sizing

If the same visual value appears more than once, it should usually be promoted into the design system.

## Mobile-First Rule

Every Talaria screen should be mobile friendly by default.

That means:

- start with the narrow-screen layout first, then enhance upward for tablet and desktop
- avoid horizontal scrolling in core app views
- stack controls vertically on small screens before introducing inline layouts
- preserve comfortable tap targets, with interactive controls respecting the shared minimum touch target
- keep readable line lengths and avoid oversized fixed paddings on phones
- treat responsive behavior as part of the design system, not as a per-screen fix

## Token Layer

### Color Tokens

- `--background`
- `--foreground`
- `--card`
- `--card-foreground`
- `--popover`
- `--popover-foreground`
- `--primary`
- `--primary-foreground`
- `--secondary`
- `--secondary-foreground`
- `--muted`
- `--muted-foreground`
- `--accent`
- `--accent-foreground`
- `--border`
- `--input`
- `--ring`

### Shape Tokens

- `--radius`
- `--radius-pill`
- `--radius-surface`

### Elevation Tokens

- `--shadow-sm`
- `--shadow-md`
- `--shadow-lg`
- `--shadow-focus-ring`

### Layout And Motion Tokens

- `--space-1`
- `--space-2`
- `--space-3`
- `--space-4`
- `--space-5`
- `--space-page-x-mobile`
- `--space-page-x-desktop`
- `--space-page-y-mobile`
- `--space-page-y-desktop`
- `--content-max`
- `--copy-max`
- `--touch-target-min`
- `--transition-standard`

### Semantic Tokens

- `--gradient-page`
- `--status-positive`
- `--status-negative`
- `--status-neutral`
- `--font-sans`

## Reusable Class Layer

Shared UI styling should be expressed through reusable classes before feature-specific classes are introduced.

Current reusable classes include:

- `.ui-surface`
- `.ui-surface--raised`
- `.ui-surface--hero`
- `.ui-text-eyebrow`
- `.ui-text-display`
- `.ui-text-body`
- `.ui-text-body--lead`
- `.ui-text-muted`
- `.ui-card-label`
- `.ui-metric`
- `.ui-button-primary`
- `.ui-status-dot`
- `.ui-status-dot--online`
- `.ui-status-dot--offline`
- `.ui-grid-cards`

When adding a new visual pattern, prefer extending this layer instead of introducing one-off styles into a single component.

## Layout Rules

- The application canvas sits on `background`.
- Distinct modules, panels, sidebars, drawers, and dialogs sit on `card`.
- Do not use borders to separate macro layout sections.
- Use spacing and elevation to create separation.
- White surfaces should appear to float above the cooler slate background.
- Build layouts mobile-first and only expand to multi-column arrangements when screen width earns it.
- Default horizontal action rows to vertical stacks on small screens.

## Typography Rules

- Build hierarchy with size, weight, rhythm, and spacing.
- Use `foreground` for headings and primary readable text.
- Use `muted-foreground` for metadata, helper text, timestamps, and placeholders.
- Do not use the primary teal for normal body copy.

## Interaction Rules

- The teal primary treatment is reserved for the main action in a view.
- Secondary actions should stay neutral.
- Inputs may use `border-input`, but focus should resolve through the shared ring token.
- Hover and pressed states should remain subtle.
- Interactive elements should respect the shared minimum touch target.

## Messaging Rules

- User bubbles should use the primary surface treatment.
- AI or contact bubbles should use the secondary surface treatment.
- Chat bubbles should not cast shadows.
- Bubble geometry should stay soft, with one tighter tail corner to indicate direction.

## `shadcn/ui` Guidance

- Use `shadcn/ui` as much as possible once components are installed.
- Configure `shadcn` components from Talaria tokens instead of view-specific overrides.
- Prefer extending `shadcn` variants over replacing them.
- If a custom component is unavoidable, it must still consume Talaria tokens and shared Talaria classes rather than hardcoded values.
- Responsive behavior should also be expressed through shared Talaria tokens, shared classes, or `shadcn` composition patterns whenever possible.

## Tailwind Reference

### Base token example

```css
@layer base {
  :root {
    --background: 210 40% 98%;
    --foreground: 215 25% 15%;
    --primary: 173 80% 32%;
    --radius: 0.75rem;
    --shadow-md:
      0 8px 24px -4px rgba(26, 38, 52, 0.04),
      0 4px 10px -2px rgba(26, 38, 52, 0.02);
  }
}
```

### Tailwind shadow extension example

```js
export default {
  theme: {
    extend: {
      boxShadow: {
        sm: "0 2px 8px -1px rgba(26, 38, 52, 0.04), 0 1px 2px -1px rgba(26, 38, 52, 0.02)",
        md: "0 8px 24px -4px rgba(26, 38, 52, 0.04), 0 4px 10px -2px rgba(26, 38, 52, 0.02)",
        lg: "0 12px 32px -4px rgba(26, 38, 52, 0.05), 0 6px 14px -2px rgba(26, 38, 52, 0.03)",
      },
    },
  },
};
```
