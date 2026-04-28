---
name: frontend-design
description: Create distinctive, production-grade frontend interfaces from an end user's perspective. Use when Codex builds or improves web UI, including websites, landing pages, dashboards, applications, React/Vue/Svelte components, HTML/CSS layouts, artifacts, posters, prototypes, or any task involving styling, visual polish, interaction design, responsive UI, or beautifying an existing frontend.
---

# Frontend Design

## Overview

Design the interface as a usable product for real people, not as a decorative screenshot. Commit to a clear point of view, implement working code, and verify that the result is responsive, accessible, coherent, and visually memorable.

## Operating Mode

Before coding, infer or ask only what is necessary to understand:

- **User**: who uses this, what they need to accomplish, and what emotional state or workflow they bring.
- **Domain**: what visual language fits the product, brand, content, or audience.
- **Context**: framework, existing design system, assets, accessibility, performance, and delivery constraints.
- **Memory**: the one visual or interaction detail a user should remember after leaving.

Then choose one strong aesthetic direction and execute it consistently. Good directions can be brutally minimal, editorial, luxury/refined, playful, industrial, organic, art deco, retro-futurist, utilitarian, maximalist, raw/brutalist, cinematic, scientific, or another context-specific style. Boldness means intentionality, not visual noise.

## Design Workflow

1. **Audit the task**
   - Identify the primary user goal and the most important screen state.
   - Inspect existing code, components, tokens, assets, and conventions before inventing new ones.
   - Preserve product ergonomics over decorative novelty.

2. **Pick a concept**
   - Name the design direction in a short phrase before implementation.
   - Define the layout idea, typography mood, color system, motion style, and signature detail.
   - Make choices that belong to the user's domain; avoid generic portfolio or SaaS templates unless the request actually calls for them.

3. **Implement the product surface**
   - Build actual working UI, not a static shell.
   - Include natural states a user expects: empty, loading, active, selected, error, success, disabled, hover/focus, and responsive states when relevant.
   - Use existing framework patterns, component libraries, routing, and styling conventions in the repo.
   - Prefer semantic HTML and accessible controls; preserve keyboard use and visible focus states.

4. **Refine the visual system**
   - Use CSS variables or design tokens for color, spacing, shadow, typography, radius, and motion.
   - Create hierarchy with spacing, contrast, proportion, and rhythm before adding ornament.
   - Use icons, real images, generated bitmap assets, canvas, SVG, or CSS effects when they serve the concept.
   - Ensure text fits containers on mobile and desktop; avoid overlap, clipping, and layout shift.

5. **Verify like a user**
   - Run the app or build command when available.
   - Inspect the UI at mobile and desktop widths. Use browser screenshots for substantial frontend work.
   - Fix broken interactions, cramped text, low contrast, awkward scroll behavior, and visual inconsistencies before handing off.

## Aesthetic Rules

- Choose typography with personality. Avoid defaulting to Arial, Roboto, Inter, system fonts, or the same trendy display face repeatedly unless the existing product already depends on them.
- Pair a distinctive display voice with a legible body face when external fonts are acceptable. If offline constraints apply, use available local or system fonts deliberately.
- Avoid overused AI aesthetics: purple-blue gradients on white, generic glass cards, floating blobs, predictable hero/card grids, uniform pastel dashboards, and decorative effects unrelated to the product.
- Do not make every design maximalist. Minimal interfaces need precise spacing, type scale, contrast, and behavior; maximal ones need orchestration and restraint.
- Avoid one-note palettes. Use a dominant palette with meaningful accent colors, neutrals, and state colors.
- Use motion purposefully: page entrance, state transition, hover/focus feedback, drag/drop, reveal, or progress. Prefer one memorable motion system over scattered animations.
- Favor compositions with intent: asymmetry, editorial grids, compact work surfaces, dense operational tables, layered depth, diagonal flow, or generous negative space as the product demands.

## End-User Perspective Checks

Ask these silently during implementation:

- Can a first-time user tell what to do in five seconds?
- Does the first viewport show the actual product, content, tool, or experience rather than marketing filler?
- Are primary actions obvious without shouting?
- Does the screen support the user's real workflow, including repeated use?
- Are labels, empty states, and feedback written in the product's voice?
- Does the mobile layout feel designed, not merely squeezed?
- Does every visual flourish earn its space?

## Implementation Guidance

- For existing apps, match architecture and component boundaries while upgrading craft.
- For new single-page prototypes, make the first screen the usable experience, not a landing page, unless the user explicitly asks for a landing page.
- For dashboards and tools, prioritize scannability, density, alignment, and efficient controls over giant hero sections.
- For branded or editorial pages, make the subject visually present in the first viewport through image, typography, content, or interaction.
- For games or spatial interfaces, use the appropriate rendering or game library instead of hand-rolling core rules when a reliable library exists.
- Use lucide or the repo's existing icon system for common actions. Use custom visuals only when they are part of the concept.
- Do not add nested cards, decorative card wrappers around whole page sections, or unnecessary explanatory text inside the app.

## Definition of Done

- The interface has a named design direction and coherent visual system.
- The implemented UI is functional, responsive, and accessible for the requested scope.
- The work includes expected interaction states and handles realistic content lengths.
- The result avoids generic AI styling and feels specific to the user's product, audience, and task.
- The implementation has been run or visually checked when the local project supports it.
