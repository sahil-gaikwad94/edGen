// Minimal, safe markdown: escape first, then re-inject a small tag set.
// Supports: **bold**, `code`, paragraphs, line breaks, unordered/ordered lists, tables.

function esc(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inline(s) {
  return s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*(?!\s)(.+?)(?<!\s)\*/g, "<em>$1</em>");
}

function isTableLine(l) {
  return /^\s*\|.*\|\s*$/.test(l);
}

export function mdToHtml(md) {
  const lines = esc(md || "").split("\n");
  const out = [];
  let i = 0;
  let para = [];
  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${para.map(inline).join("<br/>")}</p>`);
      para = [];
    }
  };
  while (i < lines.length) {
    const line = lines[i];
    if (isTableLine(line) && i + 1 < lines.length && /^\s*\|[-\s|]+\|\s*$/.test(lines[i + 1])) {
      flushPara();
      const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const header = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && isTableLine(lines[i])) {
        rows.push(cells(lines[i]));
        i++;
      }
      out.push(
        `<table><thead><tr>${header.map((h) => `<th>${inline(h)}</th>`).join("")}</tr></thead>` +
        `<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`
      );
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      flushPara();
      const items = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      out.push(`<ul>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</ul>`);
      continue;
    }
    if (line.trim() === "") {
      flushPara();
      i++;
      continue;
    }
    para.push(line);
    i++;
  }
  flushPara();
  return out.join("\n");
}
