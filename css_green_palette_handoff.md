# CSS Color Palette Handoff

This document extracts and explains the color system from the provided CSS theme.

The palette is a **soft botanical / sage green theme** with:

- Light mode: **green-tinted off-white + deep forest green**
- Dark mode: **green-black + mint green accents**
- Overall vibe: **clean, calm, organic, premium, dashboard-friendly**

---

## 1. Original CSS Variables

```css
:root {
  --bg: #f6fbf7;
  --surface: #ffffff;
  --surface-soft: #eaf6ec;
  --text: #123224;
  --text-muted: #3d5f4e;
  --brand-strong: #0f5f36;
  --border: #d6e7db;
  --border-strong: #aecdb9;
}

:root[data-theme='dark'] {
  --bg: #0c1c14;
  --surface: #12271d;
  --surface-soft: #1a3527;
  --text: #edf8f0;
  --text-muted: #b6d4c0;
  --brand-strong: #8ed8ac;
  --border: #294436;
  --border-strong: #3f6650;
}
```

---

## 2. Light Theme Palette

| CSS Variable | Hex | Description | Suggested Usage |
|---|---:|---|---|
| `--bg` | `#f6fbf7` | Very pale greenish white | Main app background |
| `--surface` | `#ffffff` | Pure white | Cards, modals, panels |
| `--surface-soft` | `#eaf6ec` | Soft mint / pale sage | Secondary sections, subtle highlights |
| `--text` | `#123224` | Very dark forest green | Primary text |
| `--text-muted` | `#3d5f4e` | Muted eucalyptus green | Secondary text, descriptions |
| `--brand-strong` | `#0f5f36` | Deep leafy green | Primary buttons, links, active states |
| `--border` | `#d6e7db` | Pale green-gray | Light borders/dividers |
| `--border-strong` | `#aecdb9` | Soft sage border | Stronger borders, focused cards |

### Light Theme Summary

```css
#f6fbf7  /* green-tinted off-white background */
#ffffff  /* pure white surface */
#eaf6ec  /* pale mint/sage surface */
#123224  /* dark forest text */
#3d5f4e  /* muted green text */
#0f5f36  /* primary deep green */
#d6e7db  /* light green-gray border */
#aecdb9  /* sage green border */
```

### Main Light Mode Brand Color

```css
#0f5f36
```

Description:

> Deep leafy green / forest green

Use it for:

- Primary CTA buttons
- Important links
- Active navigation states
- Brand highlights
- Success or positive states, if appropriate

---

## 3. Dark Theme Palette

| CSS Variable | Hex | Description | Suggested Usage |
|---|---:|---|---|
| `--bg` | `#0c1c14` | Very dark green-black | Main dark background |
| `--surface` | `#12271d` | Dark forest green surface | Cards, panels, modals |
| `--surface-soft` | `#1a3527` | Slightly lighter dark green | Secondary sections, hover states |
| `--text` | `#edf8f0` | Almost white with green tint | Primary text |
| `--text-muted` | `#b6d4c0` | Pale sage text | Secondary text, descriptions |
| `--brand-strong` | `#8ed8ac` | Soft mint green accent | Primary accents, links, active states |
| `--border` | `#294436` | Dark muted green border | Normal borders/dividers |
| `--border-strong` | `#3f6650` | Medium dark sage green | Stronger borders, focus states |

### Dark Theme Summary

```css
#0c1c14  /* green-black background */
#12271d  /* dark forest surface */
#1a3527  /* softer dark green surface */
#edf8f0  /* green-tinted near-white text */
#b6d4c0  /* muted pale sage text */
#8ed8ac  /* mint green accent */
#294436  /* dark green border */
#3f6650  /* stronger sage border */
```

### Main Dark Mode Brand Color

```css
#8ed8ac
```

Description:

> Soft mint green / light sage green

Use it for:

- Primary CTA buttons in dark mode
- Links
- Active states
- Small glowing accents
- Positive/success highlights

---

## 4. White and Off-White Colors

### Light Mode Whites

```css
#ffffff  /* pure white */
#f6fbf7  /* very pale green-white */
#eaf6ec  /* pale mint-white */
```

Usage:

- `#ffffff` should be used for clean surfaces like cards and modals.
- `#f6fbf7` should be used as the page background.
- `#eaf6ec` should be used for soft sections, chips, badges, or subtle blocks.

### Dark Mode Near-Whites

```css
#edf8f0  /* near-white with slight green tint */
#b6d4c0  /* muted sage-white */
```

Usage:

- `#edf8f0` should be used for main readable text.
- `#b6d4c0` should be used for secondary text and descriptions.

---

## 5. Design Direction

The palette should feel like:

> Clean off-white + sage green + forest green, with dark mode based on green-black + mint accents.

Suggested visual style:

- Soft, rounded cards
- Light borders instead of heavy shadows
- Minimal gradients
- Botanical, calm, clean aesthetic
- Good for dashboards, sustainability products, health apps, climate tech, finance tools, internal tools, and premium SaaS interfaces

---

## 6. Recommended Component Usage

| Component | Light Theme | Dark Theme |
|---|---|---|
| Page background | `--bg` / `#f6fbf7` | `--bg` / `#0c1c14` |
| Card background | `--surface` / `#ffffff` | `--surface` / `#12271d` |
| Soft card background | `--surface-soft` / `#eaf6ec` | `--surface-soft` / `#1a3527` |
| Primary text | `--text` / `#123224` | `--text` / `#edf8f0` |
| Muted text | `--text-muted` / `#3d5f4e` | `--text-muted` / `#b6d4c0` |
| Primary button | `--brand-strong` / `#0f5f36` | `--brand-strong` / `#8ed8ac` |
| Border | `--border` / `#d6e7db` | `--border` / `#294436` |
| Strong border | `--border-strong` / `#aecdb9` | `--border-strong` / `#3f6650` |

---

## 7. Short Agent Instruction

Use this color palette as the product's core visual identity.

The UI should feel calm, premium, clean, and nature-inspired. Use off-white and soft sage backgrounds in light mode, and green-black backgrounds with mint accents in dark mode. Prefer subtle borders, rounded surfaces, and restrained use of the primary green. Avoid neon greens, harsh contrast, or overly saturated emerald tones.

Primary brand colors:

```css
Light mode primary: #0f5f36
Dark mode primary:  #8ed8ac
```

Primary background colors:

```css
Light mode background: #f6fbf7
Dark mode background:  #0c1c14
```
