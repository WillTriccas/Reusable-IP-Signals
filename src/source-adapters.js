import { readFile } from "node:fs/promises";
import path from "node:path";

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') {
        value += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        value += character;
      }
    } else if (character === '"' && value.length === 0) {
      quoted = true;
    } else if (character === ",") {
      row.push(value);
      value = "";
    } else if (character === "\n") {
      row.push(value.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      value = "";
    } else {
      value += character;
    }
  }

  if (quoted) {
    throw new Error("CSV source contains an unterminated quoted field");
  }
  if (row.length > 0 || value.length > 0) {
    row.push(value.replace(/\r$/, ""));
    rows.push(row);
  }

  const headers = rows.shift()?.map((header, index) =>
    index === 0 ? header.replace(/^\uFEFF/, "").trim() : header.trim(),
  );
  if (!headers?.length || headers.some((header) => !header)) {
    throw new Error("CSV source must include non-empty column headers");
  }

  return rows
    .filter((cells) => cells.some((cell) => cell.trim().length > 0))
    .map((cells) =>
      Object.fromEntries(headers.map((header, index) => [header, cells[index] ?? ""])),
    );
}

export async function readSource(source, configDirectory) {
  const sourcePath = path.resolve(configDirectory, source.path);
  const contents = await readFile(sourcePath, "utf8");

  if (source.adapter === "csv") {
    return parseCsv(contents);
  }
  if (source.adapter === "json") {
    const parsed = JSON.parse(contents);
    const records = Array.isArray(parsed) ? parsed : parsed.records;
    if (!Array.isArray(records)) {
      throw new Error(`JSON source "${source.name}" must contain an array of records`);
    }
    return records;
  }
  throw new Error(`Unsupported source adapter: ${source.adapter}`);
}
