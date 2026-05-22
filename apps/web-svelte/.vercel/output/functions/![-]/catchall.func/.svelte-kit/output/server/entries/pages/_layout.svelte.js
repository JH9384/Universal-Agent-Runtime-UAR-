import { a9 as slot } from "../../chunks/renderer.js";
function _layout($$renderer, $$props) {
  $$renderer.push(`<div class="min-h-screen bg-gray-950 text-gray-100"><!--[-->`);
  slot($$renderer, $$props, "default", {});
  $$renderer.push(`<!--]--></div>`);
}
export {
  _layout as default
};
