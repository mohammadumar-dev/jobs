# Design tokens

Style reference: eventbeep.com (home and job hub), inspected in the browser on
2026-11-16. We borrow the *rhythm and tone* only: warm paper background, heavy
black headline, two CTAs, stat tiles, category-tabbed job section, flat bordered
cards. The name, logo mark, copy and all imagery here are our own; nothing was
copied from the reference site (no logo, wordmark, photos, press logos or text).

No screenshots are stored in this folder: the plan asked for 4-6 reference
screenshots placed here by a person. The values below were read from the live
page's computed styles instead. Drop screenshots here later if you want the
tokens re-checked against them.

## Colour

| Token                | Value     | Use                                         |
| -------------------- | --------- | ------------------------------------------- |
| `--background`       | `#FFFDF3` | page background (warm paper)                |
| `--card`             | `#FFFFFF` | cards, inputs, nav bar                      |
| `--foreground`       | `#0A0A0A` | text, primary button fill                   |
| `--muted-foreground` | `#555B66` | secondary text (7.0:1 on background)        |
| `--border`           | `#E4E4E0` | card and input borders (1px)                |
| `--muted`            | `#F3F3F0` | chips, hover fills                          |
| `--brand`            | `#3F56D6` | links, job titles, stat numbers (5.9:1)     |
| `--brand-soft`       | `#EEF0FD` | selected tab / chip background              |
| `--accent-yellow`    | `#FFD84D` | logo mark, small highlights (never text)    |
| `--destructive`      | `#B42318` | form errors (6.6:1)                         |
| `--success`          | `#12714A` | "saved" / "applied" states                  |

All text pairs meet WCAG AA (4.5:1). Yellow is decoration only.

## Type

- Body and UI: **Albert Sans** (400, 500, 600, 700), 16px / 24px.
- Display (hero and section headings): **Unbounded** 700, tight leading
  (1.05), `letter-spacing: -0.02em`. Hero is `clamp(2.25rem, 6vw, 4rem)`.
- Job title in cards: 16px / 700 in `--brand`.
- Chips: 14px / 500.

## Shape, spacing, elevation

- Radius: buttons and nav `10px`, cards and inputs `8px`, chips `8px`,
  stat tiles `16px`.
- Borders instead of shadows: cards are flat with a 1px `--border`. The only
  shadow is on hover: `0 4px 16px rgb(10 10 10 / 0.06)`.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 72. Card padding 16px. Section
  gap 72px desktop, 48px mobile. Content width `max-w-6xl` (1152px).
- Buttons: height 44px (40px small), padding 0 24px, weight 600.
  - Primary: black fill, white text, hover `#262626`.
  - Secondary: white fill, 1px border, black text, hover `--muted`.
- Focus: 2px `--brand` outline with 2px offset on every interactive element.

## Layout rhythm

1. Floating bordered nav bar: logo, links, one black CTA.
2. Hero: centred display headline, one supporting line, two CTAs.
3. Stat tiles (active jobs, companies, last refresh).
4. Category chips, then a grid of featured job cards.
5. Closing CTA band, then a plain footer.

Mobile-first: single column under 768px, filters stack above the list, tap
targets at least 44px.

## Where tokens live

Tailwind v4 has no `tailwind.config`; tokens are CSS variables mapped with
`@theme inline` in `client/app/globals.css`.
