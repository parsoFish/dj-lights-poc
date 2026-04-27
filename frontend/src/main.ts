import { bootstrap } from "./app.js";
import "./styles.css";

const root = document.getElementById("app");
if (!root) throw new Error("missing #app");
bootstrap(root).catch((err) => {
  // eslint-disable-next-line no-console
  console.error("bootstrap failed:", err);
  root.innerHTML = `<pre style="padding: 24px; color: #f88;">${String(err)}</pre>`;
});
