export const SERVER_KEY = "kalavigyan";
export const SERVER_NAME = "KalaVigyan";
export const CONNECT_PATH = "/connect";
export const CONNECT_TITLE = "Connect your AI";
export const CLAUDE_IDENTITY = "Use Claude's published identity";

export type GuideStep = { text: string; code?: string };
export type ClientGuide = { key: string; name: string; steps: GuideStep[]; note: string | null; docs: string };

export function claudeCodeCommand(address: string): string {
  return `claude mcp add --transport http ${SERVER_KEY} ${address}`;
}

export function cursorConfig(address: string): string {
  return JSON.stringify({ mcpServers: { [SERVER_KEY]: { url: address } } }, null, 2);
}

export function vsCodeConfig(address: string): string {
  return JSON.stringify({ servers: { [SERVER_KEY]: { type: "http", url: address } } }, null, 2);
}

function claude(address: string): ClientGuide {
  return {
    key: "claude",
    name: "Claude and Claude Desktop",
    steps: [
      { text: "Open Customize, then Connectors, press + Add and choose Add custom connector." },
      { text: `Name it ${SERVER_NAME}, paste the address as the server URL and press Continue.`, code: address },
      { text: `Review the sign-in Claude detects: under Authentication choose Sign in now, under OAuth client choose ${CLAUDE_IDENTITY} (Recommended), then press Add.` },
      { text: "In a chat, press + at the lower left, open Connectors and switch KalaVigyan on." }
    ],
    note: `On Team and Enterprise plans an owner adds it in Organization settings, Connectors (Add, Custom, Web) with the same choices; members then press Connect beside it in Customize, Connectors. Register automatically also signs in, where ${CLAUDE_IDENTITY} cannot be chosen.`,
    docs: "https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp"
  };
}

function claudeCode(address: string): ClientGuide {
  return {
    key: "claude-code",
    name: "Claude Code",
    steps: [
      { text: "In a terminal, add the server.", code: claudeCodeCommand(address) },
      { text: "In Claude Code, run /mcp, choose kalavigyan and follow the sign-in in your browser.", code: "/mcp" }
    ],
    note: "The server is added to the current project; put --scope user before the address to use it in every project, or sign in from the shell with claude mcp login kalavigyan.",
    docs: "https://code.claude.com/docs/en/mcp"
  };
}

function chatGpt(address: string): ClientGuide {
  return {
    key: "chatgpt",
    name: "ChatGPT",
    steps: [
      { text: "Open chatgpt.com/plugins, press the plus button and choose Add custom MCP server." },
      { text: `Name it ${SERVER_NAME} and, under Connection, paste the address as the Server URL.`, code: address },
      { text: "Choose OAuth as its authentication, tick I understand and want to continue, and choose Create as a plugin." },
      { text: "Install the plugin, then in a chat type @ and choose KalaVigyan." }
    ],
    note: "On the web only. In Business, Enterprise and Edu workspaces admins and owners create it; Pro connects custom servers for reading and fetching only.",
    docs: "https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt"
  };
}

function cursor(address: string): ClientGuide {
  return {
    key: "cursor",
    name: "Cursor",
    steps: [
      { text: "Add KalaVigyan to ~/.cursor/mcp.json for every project, or to .cursor/mcp.json in one project.", code: cursorConfig(address) },
      { text: "Switch it on from Customize in the sidebar; Cursor signs in with OAuth, registering itself as a public client." }
    ],
    note: null,
    docs: "https://cursor.com/docs/context/mcp"
  };
}

function vsCode(address: string): ClientGuide {
  return {
    key: "vscode",
    name: "VS Code",
    steps: [
      { text: "From the Command Palette run MCP: Open User Configuration, or MCP: Open Workspace Folder MCP Configuration for .vscode/mcp.json, and add the server.", code: vsCodeConfig(address) },
      { text: "Or run MCP: Add Server, choose HTTP (HTTP or Server-Sent Events) and paste the address." },
      { text: "Start KalaVigyan and review the sign-in request when it appears; a browser window opens to sign you in." }
    ],
    note: null,
    docs: "https://code.visualstudio.com/docs/copilot/reference/mcp-configuration"
  };
}

function anyClient(address: string): ClientGuide {
  return {
    key: "any",
    name: "Any other client",
    steps: [
      { text: "Add the address as a remote MCP server over Streamable HTTP.", code: address },
      { text: "Let the client sign you in with OAuth: it reads the sign-in from the server, names itself by its published client ID document or registers itself, and opens KalaVigyan's sign-in page." }
    ],
    note: "Reading works without signing in; asking, contributing and reviewing need it.",
    docs: "https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization"
  };
}

export function clientGuides(address: string): ClientGuide[] {
  return [claude(address), claudeCode(address), chatGpt(address), cursor(address), vsCode(address), anyClient(address)];
}
