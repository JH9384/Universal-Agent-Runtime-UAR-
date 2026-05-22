import { Q as ensure_array_like, J as attr_class, V as escape_html, K as bind_props, X as fallback, G as attr } from "../../chunks/renderer.js";
function SkillSelector($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let selected = fallback($$props["selected"], () => [], true);
    const skills = [
      "section_sum",
      "doc_ingest",
      "dependency_map",
      "ollama_generate",
      "graphrag_skills"
    ];
    $$renderer2.push(`<div class="mb-4"><label class="mb-1 block text-sm font-medium">Skills</label> <div class="flex flex-wrap gap-2"><!--[-->`);
    const each_array = ensure_array_like(skills);
    for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
      let skill = each_array[$$index];
      $$renderer2.push(`<button${attr_class("rounded-full border px-3 py-1 text-sm transition-colors", void 0, {
        "bg-blue-600": selected.includes(skill),
        "border-gray-700": !selected.includes(skill)
      })}>${escape_html(skill)}</button>`);
    }
    $$renderer2.push(`<!--]--></div></div>`);
    bind_props($$props, { selected });
  });
}
function EventStream($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let reversed;
    let events = fallback($$props["events"], () => [], true);
    reversed = [...events].reverse();
    if (events.length > 0) {
      $$renderer2.push("<!--[0-->");
      $$renderer2.push(`<div class="mt-6 rounded-lg border border-gray-700 bg-gray-900 p-4"><h2 class="mb-2 text-lg font-semibold">Events (${escape_html(events.length)})</h2> <div class="max-h-96 space-y-2 overflow-y-auto"><!--[-->`);
      const each_array = ensure_array_like(reversed);
      for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
        let event = each_array[$$index];
        $$renderer2.push(`<div class="rounded bg-gray-800 p-2 text-sm"><span class="font-mono text-blue-400">${escape_html(event.type)}</span> `);
        if (event.skill) {
          $$renderer2.push("<!--[0-->");
          $$renderer2.push(`<span class="ml-2 text-gray-400">${escape_html(event.skill)}</span>`);
        } else {
          $$renderer2.push("<!--[-1-->");
        }
        $$renderer2.push(`<!--]--> `);
        if (event.error) {
          $$renderer2.push("<!--[0-->");
          $$renderer2.push(`<p class="mt-1 text-red-400">${escape_html(event.error)}</p>`);
        } else {
          $$renderer2.push("<!--[-1-->");
        }
        $$renderer2.push(`<!--]--></div>`);
      }
      $$renderer2.push(`<!--]--></div></div>`);
    } else {
      $$renderer2.push("<!--[-1-->");
    }
    $$renderer2.push(`<!--]-->`);
    bind_props($$props, { events });
  });
}
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let goal = "";
    let selectedSkills = [];
    let events = [];
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      $$renderer3.push(`<main class="mx-auto max-w-4xl p-6"><h1 class="mb-6 text-3xl font-bold">Universal Agent Runtime</h1> <div class="mb-4"><label class="mb-1 block text-sm font-medium">Goal</label> <textarea class="w-full rounded-lg border border-gray-700 bg-gray-900 p-3" rows="3" placeholder="Describe what you want the agent to do...">`);
      const $$body = escape_html(goal);
      if ($$body) {
        $$renderer3.push(`${$$body}`);
      }
      $$renderer3.push(`</textarea></div> `);
      SkillSelector($$renderer3, {
        get selected() {
          return selectedSkills;
        },
        set selected($$value) {
          selectedSkills = $$value;
          $$settled = false;
        }
      });
      $$renderer3.push(`<!----> <button${attr("disabled", !goal.trim(), true)} class="mt-4 rounded-lg bg-blue-600 px-6 py-2 font-semibold disabled:opacity-50">${escape_html("Run")}</button> `);
      EventStream($$renderer3, { events });
      $$renderer3.push(`<!----></main>`);
    }
    do {
      $$settled = true;
      $$inner_renderer = $$renderer2.copy();
      $$render_inner($$inner_renderer);
    } while (!$$settled);
    $$renderer2.subsume($$inner_renderer);
  });
}
export {
  _page as default
};
