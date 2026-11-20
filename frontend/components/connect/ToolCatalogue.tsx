import { groupTools, type McpCatalogue, type McpPrompt, type ToolGroup } from "@/lib/connectCatalogue";
import { countNoun, listText } from "@/lib/format";

export function catalogueLine(catalogue: McpCatalogue): string {
  const groups = groupTools(catalogue.tools).length;
  return `${countNoun(catalogue.tools.length, "tool")} in ${countNoun(groups, "group")}, and ${countNoun(catalogue.prompts.length, "guided prompt")}, as the server lists them now.`;
}

export function promptTakes(prompt: McpPrompt): string | null {
  if (!prompt.arguments.length) return null;
  const names = prompt.arguments.map((argument) => (argument.required ? argument.name : `${argument.name} (optional)`));
  return `Takes ${listText(names)}.`;
}

const ENTRY = "grid min-w-0 gap-1 border-b border-rule py-3";
const ENTRY_HEAD = "m-0 flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5";

function ToolGroupView({ group }: { group: ToolGroup }) {
  const heading = `tools-${group.key}`;
  return (
    <section aria-labelledby={heading} className="grid min-w-0 content-start gap-2" data-testid={`tool-group-${group.key}`}>
      <div className="flex items-baseline justify-between gap-4 border-b border-ink-1 pb-2">
        <h3 id={heading} className="font-reading text-h3 text-ink-1">
          {group.title}
        </h3>
        <p className="m-0 shrink-0 font-ui text-label text-ink-3 tabular-nums lining-nums">{countNoun(group.tools.length, "tool")}</p>
      </div>
      <p className="m-0 font-ui text-label text-ink-2">{group.about}</p>
      <ul className="m-0 grid list-none p-0">
        {group.tools.map((tool) => (
          <li key={tool.name} className={ENTRY}>
            <p className={ENTRY_HEAD}>
              <span className="font-ui text-h4 text-ink-1">{tool.title}</span>
              <code className="font-code text-label text-ink-3 [overflow-wrap:anywhere]">{tool.name}</code>
            </p>
            <p className="m-0 font-ui text-ui font-normal text-ink-2">{tool.summary}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function PromptList({ prompts }: { prompts: readonly McpPrompt[] }) {
  if (!prompts.length) return null;
  return (
    <section aria-labelledby="tools-prompts" className="grid min-w-0 content-start gap-2" data-testid="prompt-list">
      <div className="flex items-baseline justify-between gap-4 border-b border-ink-1 pb-2">
        <h3 id="tools-prompts" className="font-reading text-h3 text-ink-1">
          Guided prompts
        </h3>
        <p className="m-0 shrink-0 font-ui text-label text-ink-3 tabular-nums lining-nums">{countNoun(prompts.length, "prompt")}</p>
      </div>
      <p className="m-0 font-ui text-label text-ink-2">Each walks your AI through one piece of work, step by step, with the method every contributor follows.</p>
      <ul className="m-0 grid list-none p-0 md:grid-cols-2 md:gap-x-10">
        {prompts.map((prompt) => (
          <li key={prompt.name} className={ENTRY}>
            <p className={ENTRY_HEAD}>
              <span className="font-ui text-h4 text-ink-1">{prompt.title}</span>
              <code className="font-code text-label text-ink-3 [overflow-wrap:anywhere]">{prompt.name}</code>
            </p>
            <p className="m-0 font-ui text-ui font-normal text-ink-2">{prompt.description}</p>
            {promptTakes(prompt) ? <p className="m-0 font-ui text-label text-ink-3">{promptTakes(prompt)}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ToolCatalogue({ catalogue }: { catalogue: McpCatalogue }) {
  return (
    <div className="grid min-w-0 gap-6">
      <p className="m-0 font-ui text-ui font-normal text-ink-2" data-testid="catalogue-line">
        {catalogueLine(catalogue)}
      </p>
      <div className="gap-x-10 lg:columns-2 [&>section]:mb-10 [&>section]:break-inside-avoid">
        {groupTools(catalogue.tools).map((group) => (
          <ToolGroupView key={group.key} group={group} />
        ))}
      </div>
      <PromptList prompts={catalogue.prompts} />
    </div>
  );
}
