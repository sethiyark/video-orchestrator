import { readFile, rm } from "node:fs/promises";
import path from "node:path";
import net from "node:net";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

// Remotion binds its ephemeral asset server to all interfaces by default.
// This process serves private job media; constrain every local server to loopback.
const listen = net.Server.prototype.listen;
net.Server.prototype.listen = function (options, ...args) {
  if (options && typeof options === "object" && "port" in options) {
    return listen.call(this, { ...options, host: "127.0.0.1" }, ...args);
  }
  throw new Error("Renderer servers must use explicit loopback TCP options");
};

const [manifest, publicDir, outputLocation] = process.argv.slice(2);
const inputProps = JSON.parse(await readFile(manifest, "utf8"));
const serveUrl = await bundle({
  entryPoint: fileURLToPath(new URL("./src/index.jsx", import.meta.url)),
  publicDir,
  outDir: path.join(path.dirname(manifest), "bundle"),
});
try {
  const options = {
    serveUrl,
    inputProps,
    onBrowserDownload: () => {
      throw new Error("Run make setup-renderer first");
    },
  };
  const composition = await selectComposition({ ...options, id: "Explainer" });
  await renderMedia({
    ...options,
    composition,
    outputLocation,
    codec: "h264",
    audioCodec: "aac",
    pixelFormat: "yuv420p",
    concurrency: 2,
  });
} finally {
  await rm(serveUrl, { recursive: true, force: true });
}
