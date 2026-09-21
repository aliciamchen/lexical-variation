import {
  defineConfig,
  presetAttributify,
  presetIcons,
  presetTypography,
  presetUno,
  presetWebFonts,
  transformerDirectives,
  transformerVariantGroup,
} from "unocss";

export default defineConfig({
  // Not `theme.extend.colors`: that is a Tailwind convention. UnoCSS merges
  // `theme` into the preset's own theme directly and ignores an `extend` key,
  // so nesting the palette there generated no `*-empirica-*` utility at all.
  // The only ones that worked were those @empirica/core's stylesheet happens
  // to ship, and anything else -- `text-empirica-700`, `border-empirica-500`
  // -- fell back silently to the reset's grey. The values here match the ones
  // that stylesheet was built from, so nothing it already covers changes.
  theme: {
    colors: {
      empirica: {
        50: "#fbfcfe",
        100: "#f2f7fd",
        200: "#bcd8f6",
        300: "#8abbef",
        400: "#549ce8",
        500: "#237fe1",
        600: "#1966b8",
        700: "#124b87",
        800: "#0c325a",
        900: "#06192d",
      },
    },
  },
  presets: [
    presetUno(),
    presetAttributify(),
    presetIcons(),
    presetTypography(),
    presetWebFonts({
      fonts: {
        // ...
      },
    }),
  ],
  transformers: [transformerDirectives(), transformerVariantGroup()],
});
