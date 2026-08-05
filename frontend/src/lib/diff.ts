// Reconstruct original/modified text from a unified diff so Monaco DiffEditor can
// render it side-by-side. Approximate but faithful for review (context + -/+ lines).
export function parseUnifiedDiff(diff: string): { original: string; modified: string } {
  const original: string[] = [];
  const modified: string[] = [];
  for (const raw of diff.split("\n")) {
    if (raw.startsWith("+++") || raw.startsWith("---") || raw.startsWith("@@") || raw.startsWith("diff ") || raw.startsWith("index ")) {
      continue;
    }
    if (raw.startsWith("+")) {
      modified.push(raw.slice(1));
    } else if (raw.startsWith("-")) {
      original.push(raw.slice(1));
    } else {
      const line = raw.startsWith(" ") ? raw.slice(1) : raw;
      original.push(line);
      modified.push(line);
    }
  }
  return { original: original.join("\n"), modified: modified.join("\n") };
}
