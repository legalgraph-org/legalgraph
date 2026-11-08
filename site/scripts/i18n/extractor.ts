/**
 * Finds the translatable messages in .astro and .ts sources: calls `t("…")` and
 * `t.ctx("context", "…")`. `.astro` files are converted to TSX with
 * @astrojs/compiler, which keeps frontmatter and template expressions verbatim and in order;
 * oxc-parser then parses the result.
 *
 * Rules enforced here (errors fail extraction):
 *   1. arguments are string literals (or backtick literals without ${});
 *   2. no multi-line literals, and no leading or trailing whitespace (normalizing drops it, so the
 *      untranslated text would lose it: put spacing outside the message);
 *   3. `t` is never renamed: `const tr = t`, `{ t: tr }`, `x = t` are errors. Passing it on under
 *      the name `t` (`<Page t={t} />`, `cards(t)`) is fine, every call stays findable as `t(…)`;
 *   4. messages over MAX_MESSAGE_LENGTH characters are a warning: move them to a content collection.
 */
import { convertToTSX } from "@astrojs/compiler";
import { parseSync } from "oxc-parser";

import { MAX_MESSAGE_LENGTH, normalizeMsgid } from "../../src/i18n/message";
import { directLines, sourceMappedLines, type LineResolver } from "./source-lines";

export interface ExtractedMessage {
  msgid: string;
  context?: string;
  /** "path:line" */
  reference: string;
}

export interface ExtractionProblem {
  severity: "error" | "warning";
  reference: string;
  message: string;
}

export interface ExtractionResult {
  messages: ExtractedMessage[];
  problems: ExtractionProblem[];
}

const T = "t";

/** A minimal ESTree view: oxc-parser returns plain JSON-like nodes with a `type` and offsets. */
interface AstNode {
  type: string;
  start: number;
  end: number;
  [key: string]: AstValue;
}
type AstValue = AstNode | AstNode[] | string | number | boolean | null | undefined | AstValue[];

function isNode(value: unknown): value is AstNode {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    "type" in value &&
    typeof value.type === "string" &&
    "start" in value &&
    typeof value.start === "number"
  );
}

function children(node: AstNode): AstNode[] {
  const result: AstNode[] = [];
  for (const [key, value] of Object.entries(node)) {
    if (key === "type" || key === "start" || key === "end") {
      continue;
    }
    if (isNode(value)) {
      result.push(value);
    } else if (Array.isArray(value)) {
      for (const item of value) {
        if (isNode(item)) {
          result.push(item);
        }
      }
    }
  }
  return result;
}

/** The nodes in an array-valued field (e.g. CallExpression.arguments). */
function nodesOf(value: AstValue): AstNode[] {
  const nodes: AstNode[] = [];
  if (Array.isArray(value)) {
    for (const item of value) {
      if (isNode(item)) {
        nodes.push(item);
      }
    }
  }
  return nodes;
}

function isIdentifier(node: AstValue, name: string): boolean {
  return isNode(node) && node.type === "Identifier" && node.name === name;
}

/** The literal's text, or undefined when it is not a static string. */
function staticString(node: AstValue): string | undefined {
  if (!isNode(node)) {
    return undefined;
  }
  if (node.type === "Literal" && typeof node.value === "string") {
    return node.value;
  }
  if (
    node.type === "TemplateLiteral" &&
    Array.isArray(node.expressions) &&
    node.expressions.length === 0
  ) {
    const quasis = node.quasis;
    if (Array.isArray(quasis) && quasis.length === 1) {
      const quasi = quasis[0];
      // TemplateElement.value is { raw, cooked }, not a node.
      const value = isNode(quasi) ? quasi.value : undefined;
      if (
        typeof value === "object" &&
        value !== null &&
        "cooked" in value &&
        typeof value.cooked === "string"
      ) {
        return value.cooked;
      }
    }
  }
  return undefined;
}

interface ParsedSource {
  code: string;
  lineOf: LineResolver;
}

async function toParsedSource(path: string, source: string): Promise<ParsedSource> {
  if (!path.endsWith(".astro")) {
    return { code: source, lineOf: directLines(source) };
  }
  const result = await convertToTSX(source, { filename: path });
  // The compiler wraps each <script> in `{() => { … }}`. In the browser that script is a module,
  // where top-level `await` is allowed, so make the wrapper async for the parser. The wrapper
  // sits on a line of its own, so no message's line moves.
  const code = result.code.replace(/(<script\b[^>]*>\s*\{)\(\) => \{/g, "$1async () => {");
  return { code, lineOf: sourceMappedLines(code, result.map.mappings) };
}

export async function extractMessages(path: string, source: string): Promise<ExtractionResult> {
  const { code, lineOf } = await toParsedSource(path, source);
  const parsed = parseSync(path.endsWith(".astro") ? `${path}.tsx` : path, code);
  const messages: ExtractedMessage[] = [];
  const problems: ExtractionProblem[] = [];
  const at = (node: AstNode) => `${path}:${lineOf(node.start)}`;

  for (const error of parsed.errors) {
    problems.push({ severity: "error", reference: path, message: `parse error: ${error.message}` });
  }

  const addMessage = (call: AstNode, args: AstNode[], hasContext: boolean) => {
    const [contextArg, msgidArg] = hasContext ? [args[0], args[1]] : [undefined, args[0]];
    const reference = isNode(msgidArg) ? at(msgidArg) : at(call);
    const msgid = staticString(msgidArg);
    const context = contextArg === undefined ? undefined : staticString(contextArg);
    if (msgid === undefined || (hasContext && context === undefined)) {
      problems.push({
        severity: "error",
        reference,
        message: "t() arguments must be string literals (no variables, ${} or concatenation)",
      });
      return;
    }
    if (msgid.includes("\n") || (context ?? "").includes("\n")) {
      problems.push({
        severity: "error",
        reference,
        message: "multi-line message literals are not allowed",
      });
      return;
    }
    if (msgid !== msgid.trim() || (context ?? "") !== (context ?? "").trim()) {
      problems.push({
        severity: "error",
        reference,
        message: "leading or trailing whitespace is dropped from messages: put it outside t()",
      });
      return;
    }
    const normalized = normalizeMsgid(msgid);
    if (normalized.length > MAX_MESSAGE_LENGTH) {
      problems.push({
        severity: "warning",
        reference,
        message: `message is ${normalized.length} characters (> ${MAX_MESSAGE_LENGTH}): move it to a content collection`,
      });
    }
    messages.push({ msgid: normalized, ...(context ? { context } : {}), reference });
  };

  const visit = (node: AstNode, ancestors: readonly AstNode[]) => {
    if (node.type === "CallExpression") {
      const args = nodesOf(node.arguments);
      const callee = node.callee;
      if (isIdentifier(callee, T)) {
        addMessage(node, args, false);
      } else if (
        isNode(callee) &&
        callee.type === "MemberExpression" &&
        isIdentifier(callee.object, T) &&
        isIdentifier(callee.property, "ctx")
      ) {
        addMessage(node, args, true);
      }
    }
    if (isIdentifier(node, T) && renamesT(node, ancestors)) {
      problems.push({
        severity: "error",
        reference: at(node),
        message: "`t` must not be renamed (rule 3)",
      });
    }
    for (const child of children(node)) {
      visit(child, [...ancestors, node]);
    }
  };
  if (!isNode(parsed.program)) {
    throw new Error(`${path}: oxc-parser returned no program`);
  }
  visit(parsed.program, []);
  return { messages, problems };
}

/** Whether this `t` identifier hands the translator to a binding with another name. */
function renamesT(node: AstNode, ancestors: readonly AstNode[]): boolean {
  const parent = ancestors.at(-1);
  if (!parent) {
    return false;
  }
  switch (parent.type) {
    case "VariableDeclarator":
      return parent.init === node; // const tr = t
    case "AssignmentExpression":
      return parent.right === node; // tr = t
    case "Property": {
      if (parent.shorthand === true) {
        return false; // { t } keeps the name
      }
      const container = ancestors.at(-2);
      if (container?.type === "ObjectPattern") {
        return parent.key === node; // const { t: tr } = …
      }
      return parent.value === node; // { tr: t }
    }
    default:
      return false;
  }
}
