/**
 * Maps an offset in the code oxc-parser saw back to a 1-based line of the original file.
 * For .ts that code is the file itself; for .astro it is convertToTSX output, mapped back through
 * its source map (VLQ "mappings", one segment list per generated line).
 */
const BASE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

function decodeVlq(segment: string): number[] {
  const values: number[] = [];
  let value = 0;
  let shift = 0;
  for (const char of segment) {
    const digit = BASE64.indexOf(char);
    if (digit === -1) {
      throw new Error(`Invalid source map character ${JSON.stringify(char)}`);
    }
    value += (digit & 31) << shift;
    if (digit & 32) {
      shift += 5;
    } else {
      values.push(value & 1 ? -(value >>> 1) : value >>> 1);
      value = 0;
      shift = 0;
    }
  }
  return values;
}

interface Segment {
  generatedColumn: number;
  originalLine: number;
}

function lineStarts(code: string): number[] {
  const starts = [0];
  for (let index = 0; index < code.length; index += 1) {
    if (code[index] === "\n") {
      starts.push(index + 1);
    }
  }
  return starts;
}

/** 0-based line and column of an offset. */
function position(starts: readonly number[], offset: number): { line: number; column: number } {
  let low = 0;
  let high = starts.length - 1;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if ((starts[middle] ?? 0) <= offset) {
      low = middle;
    } else {
      high = middle - 1;
    }
  }
  return { line: low, column: offset - (starts[low] ?? 0) };
}

export type LineResolver = (offset: number) => number;

export function directLines(code: string): LineResolver {
  const starts = lineStarts(code);
  return (offset) => position(starts, offset).line + 1;
}

export function sourceMappedLines(generated: string, mappings: string): LineResolver {
  const starts = lineStarts(generated);
  const lines: Segment[][] = [];
  let originalLine = 0;
  for (const encodedLine of mappings.split(";")) {
    let generatedColumn = 0;
    const segments: Segment[] = [];
    for (const encoded of encodedLine.split(",").filter(Boolean)) {
      const fields = decodeVlq(encoded);
      generatedColumn += fields[0] ?? 0;
      if (fields.length >= 4) {
        originalLine += fields[2] ?? 0;
        segments.push({ generatedColumn, originalLine });
      }
    }
    lines.push(segments);
  }
  return (offset) => {
    const { line, column } = position(starts, offset);
    for (let current = line; current >= 0; current -= 1) {
      const segments = lines[current] ?? [];
      const onLine =
        current === line ? segments.filter((s) => s.generatedColumn <= column) : segments;
      const segment = onLine.at(-1);
      if (segment) {
        return segment.originalLine + 1;
      }
    }
    return 0;
  };
}
