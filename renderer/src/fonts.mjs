import { useEffect, useState } from "react";
import { continueRender, delayRender, staticFile } from "remotion";

import { FONT_FILES } from "./theme.mjs";

// Fonts come from the job's media directory (rendering.py copies them from the
// renderer's installed @fontsource packages); nothing leaves the host. A
// missing or slow file falls back to the CSS stack instead of stalling.
const FONT_WAIT_MS = 8000;

export const installFonts = () => {
  if (typeof document === "undefined" || document.getElementById("vo-fonts")) return;
  const style = document.createElement("style");
  style.id = "vo-fonts";
  style.textContent = FONT_FILES.map(
    ([family, weight, file]) =>
      `@font-face{font-family:"${family}";font-weight:${weight};font-style:normal;` +
      `font-display:block;src:url("${staticFile(`fonts/${file}`)}") format("woff2");}`,
  ).join("\n");
  document.head.appendChild(style);
};

export const useFonts = () => {
  const [handle] = useState(() =>
    delayRender("Loading vendored fonts", { timeoutInMilliseconds: FONT_WAIT_MS * 3 }),
  );
  useEffect(() => {
    installFonts();
    const done = () => continueRender(handle);
    const loads = FONT_FILES.map(([family, weight]) =>
      document.fonts.load(`${weight} 20px "${family}"`),
    );
    Promise.race([
      Promise.all(loads),
      new Promise((resolve) => setTimeout(resolve, FONT_WAIT_MS)),
    ]).then(done, done);
  }, [handle]);
};
