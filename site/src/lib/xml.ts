// Minimal XML syntax highlighting for display: tags, attributes, and our lga: annotations in their
// own colour so a reviewer sees at once what we added to the official text.
const escape = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function highlightXml(xml: string): string {
  return escape(xml).replace(/&lt;(\/?)([\w:.-]+)((?:\s+[\w:.-]+="[^"]*")*)\s*(\/?)&gt;/g, (_match, close, name, attrs, selfClose) => {
    const attributes = (attrs as string).replace(/\s+([\w:.-]+)="([^"]*)"/g, (_m, key: string, value: string) => {
      const annotated = key.startsWith("lga:") || key === "xmlns:lga";
      return ` <span class="${annotated ? "xml-mla" : "xml-attr"}">${key}</span>=<span class="${annotated ? "xml-mla-value" : "xml-value"}">"${value}"</span>`;
    });
    return `<span class="xml-tag">&lt;${close}${name}</span>${attributes}<span class="xml-tag">${selfClose}&gt;</span>`;
  });
}
