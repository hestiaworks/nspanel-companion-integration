# Bundled typefaces

The admin panel is drawn in the same typefaces as the design and the panel
itself. They are served from this directory rather than fetched from Google
Fonts: a Home Assistant install is often on a network that cannot reach the
internet, and an admin page should not tell a third party who is looking at
it.

| File | Family | Weights | Source |
| --- | --- | --- | --- |
| `barlow-400/500/600/700.woff2` | Barlow | 400, 500, 600, 700 | the panel app's `res/font/barlow_*.ttf`, converted to woff2 |
| `roboto-mono-latin.woff2` | Roboto Mono | 400–500 (variable) | Google Fonts, Latin subset |

Both are licensed under the SIL Open Font License 1.1, which permits
redistribution as part of this integration; see `OFL.txt`.

Roboto Mono carries only the Latin subset. It is used for identifiers —
entity IDs, page IDs, tokens — which are ASCII by definition. Anything else
falls back through `ui-monospace`.
