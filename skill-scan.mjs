#!/usr/bin/env node
/**
 * skill-scan — static scanner for a skill under test.
 *
 * Pure Node. No npm packages, no build step, nothing to install. Uses only
 * node:fs, node:path and node:zlib, all of which ship with Node itself.
 *
 * Deterministic pass over a skill folder, a single SKILL.md, or a .skill
 * bundle. Seeds the evaluation with: context cost, frontmatter validity,
 * broken references, external hosts, env vars, runtime requirements,
 * credential-shaped strings, destructive commands, connector mentions and
 * placeholder markers.
 *
 * Nothing here executes the skill. It only reads text.
 *
 * Usage:
 *   node skill-scan.mjs <path>                 folder, SKILL.md, or .skill file
 *   node skill-scan.mjs <path> --json out.json also write raw results
 *   node skill-scan.mjs <path> --quiet         suppress the readable summary
 *   node skill-scan.mjs <bundle.skill> --unpack <dir>   extract, then scan
 */

import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const TEXT_SUFFIXES = new Set([
  ".md", ".txt", ".py", ".sh", ".bash", ".yml", ".yaml", ".json",
  ".toml", ".ini", ".cfg", ".html", ".js", ".mjs", ".cjs", ".jsx",
  ".ts", ".tsx", ".sql",
]);

// ~4 chars/token for prose, ~3 for denser code and config.
const PROSE_CHARS_PER_TOKEN = 4.0;
const CODE_CHARS_PER_TOKEN = 3.0;
const CODE_SUFFIXES = new Set([
  ".py", ".sh", ".bash", ".yml", ".yaml", ".json", ".js", ".mjs",
  ".cjs", ".jsx", ".ts", ".tsx", ".sql",
]);

const JS_SUFFIXES = new Set([".html", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"]);

const DESTRUCTIVE_PATTERNS = [
  [/\brm\s+-[a-zA-Z]*[rf]/g, "recursive/forced delete"],
  [/\bdd\s+if=/g, "raw disk write"],
  [/\bmkfs\b/g, "filesystem format"],
  [/:\s*>\s*\//g, "truncate absolute path"],
  [/\bchmod\s+777\b/g, "world-writable permissions"],
  [/\bkubectl\s+delete\b/g, "kubernetes delete"],
  [/\boc\s+delete\b/g, "openshift delete"],
  [/\bterraform\s+(destroy|apply\s+-auto-approve)/g, "terraform destroy/auto-approve"],
  [/\baws\s+\w+\s+delete-/g, "aws delete call"],
  [/\bDROP\s+(TABLE|DATABASE)\b/g, "sql drop"],
  [/\bTRUNCATE\s+TABLE\b/g, "sql truncate"],
  [/\bgit\s+push\s+--force/g, "force push"],
  [/\bsystemctl\s+stop\b/g, "service stop"],
  [/\bshutdown\b|\breboot\b/g, "host shutdown/reboot"],
  [/\bcurl\b[^\n]*\|\s*(ba)?sh/g, "pipe remote script to shell"],
  [/\bwget\b[^\n]*\|\s*(ba)?sh/g, "pipe remote script to shell"],
  [/\beval\s*\(/g, "dynamic eval"],
];

const CREDENTIAL_PATTERNS = [
  [/\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|bearer)\b\s*[:=]\s*['"][^'"]{8,}/gi, "inline credential assignment"],
  [/\bAKIA[0-9A-Z]{16}\b/g, "aws access key id"],
  [/\bpassword\b\s*[:=]\s*['"][^'"]{3,}/gi, "inline password"],
  [/-----BEGIN [A-Z ]*PRIVATE KEY-----/g, "embedded private key"],
  [/\bghp_[A-Za-z0-9]{20,}/g, "github token"],
  [/\bxox[baprs]-[A-Za-z0-9-]{10,}/g, "slack token"],
];

const INJECTION_PATTERNS = [
  [/ignore (all )?(the )?(previous|prior|above) instructions/gi, "instruction override"],
  [/disregard (the )?(system|previous|safety)/gi, "instruction override"],
  [/you are now (a|an|in) /gi, "role reassignment"],
  [/do not (tell|inform|mention to) the user/gi, "concealment from user"],
  [/without (asking|informing|notifying) the (user|human)/gi, "bypass of confirmation"],
  [/(bypass|skip|disable) (the )?(safety|guardrail|check|approval|confirmation)/gi, "guardrail bypass"],
  [/(exfiltrat|send .{0,20}to an external)/gi, "data exfiltration language"],
];

const CONNECTOR_HINTS = {
  confluence: "knowledge", sharepoint: "knowledge", notion: "knowledge",
  "google drive": "knowledge", gdrive: "knowledge", wiki: "knowledge",
  jira: "tracker", servicenow: "tracker", "snow ticket": "tracker",
  pagerduty: "tracker", gitlab: "tracker", "github issue": "tracker",
  slack: "connector", gmail: "connector", outlook: "connector",
  calendar: "connector", mcp: "connector",
  dynatrace: "observability", grafana: "observability", splunk: "observability",
  cloudwatch: "observability", prometheus: "observability", datadog: "observability",
  openshift: "platform", kubernetes: "platform", kubectl: "platform",
  terraform: "platform", ansible: "platform", aap: "platform",
  aws: "platform", azure: "platform", kafka: "platform", jboss: "platform",
  vault: "credential", delinea: "credential", "secrets manager": "credential",
  cyberark: "credential",
};

const PLACEHOLDER_PATTERNS = [
  [/\{\{[^}]{1,60}\}\}/g, "handlebars placeholder"],
  [/<[A-Z_]{3,30}>/g, "angle placeholder"],
  [/\bTODO\b|\bTBD\b|\bFIXME\b|\bXXX\b/g, "unfinished marker"],
  [/\[(?:INSERT|YOUR|TEAM|ENTER)[^\]]{0,40}\]/g, "bracket placeholder"],
];

const URL_RE = /https?:\/\/([A-Za-z0-9._-]+)(?:\/[^\s)"'`]*)?/g;
const ENV_PY_RE = /os\.environ(?:\.get)?[[(]\s*['"]([A-Z0-9_]{2,})['"]/g;
// Shell-style $VAR / ${VAR}. Skipped in JS/HTML, where ${...} is a template literal.
const ENV_SH_RE = /\$\{?([A-Z][A-Z0-9_]{2,})\}?(?![A-Za-z0-9_]*[[(.])/g;
const PY_IMPORT_RE = /^[ \t]*(?:import[ \t]+([\w.]+)|from[ \t]+([\w.]+)[ \t]+import)/gm;
const JS_IMPORT_RE = /(?:^|[^\w.])(?:require\(\s*['"]([^'"]+)['"]\s*\)|from\s+['"]([^'"]+)['"]|import\s+['"]([^'"]+)['"])/g;
const MD_LINK_RE = /\]\(([^)#][^)]*)\)/g;
const BACKTICK_PATH_RE = /`((?:\.\/)?(?:scripts|references|assets)\/[A-Za-z0-9_\-./]+)`/g;
const SHEBANG_RE = /^#!.*\b(python[0-9.]*|node|bash|sh|ruby|perl|pwsh)\b/m;

const PY_STDLIB = new Set([
  "os", "sys", "re", "json", "argparse", "pathlib", "typing", "subprocess", "shutil",
  "datetime", "time", "math", "collections", "itertools", "functools", "hashlib",
  "logging", "csv", "io", "textwrap", "tempfile", "glob", "random", "urllib", "zipfile",
  "dataclasses", "enum", "base64", "uuid", "socket", "string", "traceback", "warnings",
  "__future__", "unittest", "abc", "copy", "contextlib", "html", "http", "sqlite3",
]);

const NODE_BUILTINS = new Set([
  "fs", "path", "os", "util", "events", "stream", "crypto", "zlib", "http", "https",
  "url", "child_process", "readline", "assert", "buffer", "process", "worker_threads",
  "timers", "string_decoder", "querystring", "net", "dns", "tls", "cluster", "v8", "vm",
  "perf_hooks", "async_hooks", "module", "console", "tty", "dgram", "repl", "test",
]);

/* ── helpers ─────────────────────────────────────────────────────── */

function estTokens(text, suffix = ".md") {
  const ratio = CODE_SUFFIXES.has(suffix) ? CODE_CHARS_PER_TOKEN : PROSE_CHARS_PER_TOKEN;
  return Math.round(text.length / ratio);
}

function lineOf(text, index) {
  let n = 1;
  for (let i = 0; i < index; i++) if (text.charCodeAt(i) === 10) n++;
  return n;
}

function findAll(patterns, text, file) {
  const hits = [];
  const lines = text.split("\n");
  for (const [re, label] of patterns) {
    for (const m of text.matchAll(re)) {
      const line = lineOf(text, m.index);
      hits.push({ file, line, label, snippet: (lines[line - 1] || "").trim().slice(0, 180) });
    }
  }
  return hits;
}

function parseFrontmatter(text) {
  const problems = [];
  if (!text.startsWith("---")) return [{}, text, ["SKILL.md has no YAML frontmatter block"]];
  const first = text.indexOf("\n---", 3);
  if (first === -1) return [{}, text, ["frontmatter block is not closed with ---"]];
  const raw = text.slice(3, first);
  const body = text.slice(first + 4).replace(/^\n+/, "");
  const fm = {};
  let key = null;
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    const m = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    if (m) { key = m[1]; fm[key] = m[2].trim(); }
    else if (key && /^[ \t]/.test(line)) fm[key] = (fm[key] + " " + line.trim()).trim();
  }
  for (const required of ["name", "description"]) {
    if (!fm[required]) problems.push(`frontmatter is missing required field: ${required}`);
  }
  return [fm, body, problems];
}

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".")) continue;
    if (entry.name === "node_modules" || entry.name === "__pycache__") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.isFile() && TEXT_SUFFIXES.has(path.extname(entry.name).toLowerCase())) out.push(full);
  }
  return out.sort();
}

/* ── minimal zip reader, so .skill bundles open without `unzip` ───── */

function unpackSkill(bundlePath, destDir) {
  const buf = fs.readFileSync(bundlePath);
  // End of central directory: scan backwards for the signature.
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0 && i > buf.length - 66000; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd === -1) throw new Error("not a zip archive (no end-of-central-directory record)");
  const count = buf.readUInt16LE(eocd + 10);
  let ptr = buf.readUInt32LE(eocd + 16);
  const written = [];

  for (let i = 0; i < count; i++) {
    if (buf.readUInt32LE(ptr) !== 0x02014b50) throw new Error("corrupt central directory");
    const method = buf.readUInt16LE(ptr + 10);
    const compSize = buf.readUInt32LE(ptr + 20);
    const nameLen = buf.readUInt16LE(ptr + 28);
    const extraLen = buf.readUInt16LE(ptr + 30);
    const commentLen = buf.readUInt16LE(ptr + 32);
    const localOff = buf.readUInt32LE(ptr + 42);
    const name = buf.toString("utf8", ptr + 46, ptr + 46 + nameLen);
    ptr += 46 + nameLen + extraLen + commentLen;

    if (name.includes("..")) continue;               // never write outside destDir
    const target = path.join(destDir, name);
    if (name.endsWith("/")) { fs.mkdirSync(target, { recursive: true }); continue; }

    const lNameLen = buf.readUInt16LE(localOff + 26);
    const lExtraLen = buf.readUInt16LE(localOff + 28);
    const start = localOff + 30 + lNameLen + lExtraLen;
    const raw = buf.subarray(start, start + compSize);
    let data;
    if (method === 0) data = raw;
    else if (method === 8) data = zlib.inflateRawSync(raw);
    else throw new Error(`unsupported compression method ${method} for ${name}`);

    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, data);
    written.push(name);
  }
  return written;
}

/* ── the scan ────────────────────────────────────────────────────── */

function scan(root) {
  const isFile = fs.statSync(root).isFile();
  const files = isFile ? [root] : walk(root);
  if (!files.length) return { error: `no readable text files found under ${root}` };

  const rel = (f) => (isFile ? path.basename(f) : path.relative(root, f).split(path.sep).join("/"));
  let skillMd = files.find((f) => path.basename(f).toLowerCase() === "skill.md") || (isFile ? root : null);

  const result = {
    root, files: [], frontmatter: {}, frontmatter_problems: [], context_cost: {},
    broken_references: [], external_hosts: [], env_vars: [],
    runtime: { interpreters: [], python_third_party: [], node_third_party: [] },
    destructive: [], credentials: [], injection: [], placeholders: [],
    connectors: [], smells: [],
  };

  const corpus = new Map();
  for (const f of files) {
    let text;
    try { text = fs.readFileSync(f, "utf8"); }
    catch (e) { result.smells.push(`could not read ${rel(f)}: ${e.message}`); continue; }
    corpus.set(rel(f), text);
    result.files.push({
      path: rel(f), bytes: Buffer.byteLength(text, "utf8"),
      lines: text.split("\n").length, est_tokens: estTokens(text, path.extname(f).toLowerCase()),
    });
  }

  // context cost + frontmatter + broken references
  if (skillMd) {
    const smRel = rel(skillMd);
    const smText = corpus.get(smRel) ?? fs.readFileSync(skillMd, "utf8");
    const [fm, body, problems] = parseFrontmatter(smText);
    result.frontmatter = fm;
    result.frontmatter_problems = problems;
    const others = result.files.filter((e) => e.path !== smRel).reduce((a, e) => a + e.est_tokens, 0);
    result.context_cost = {
      standing_est_tokens: estTokens(`${fm.name || ""} ${fm.description || ""}`),
      trigger_est_tokens: estTokens(body),
      bundled_resources_est_tokens: others,
      skill_md_lines: body.split("\n").length,
      description_words: (fm.description || "").split(/\s+/).filter(Boolean).length,
      note: "estimates at ~4 chars/token prose, ~3 for code",
    };
    if (result.context_cost.description_words > 160) {
      result.smells.push(`description is ${result.context_cost.description_words} words — long descriptions are loaded for every user in every context`);
    }
    if (result.context_cost.skill_md_lines > 500) {
      result.smells.push(`SKILL.md body is ${result.context_cost.skill_md_lines} lines — over the ~500 line guideline; consider moving detail into references/`);
    }
    const referenced = new Set();
    for (const m of smText.matchAll(MD_LINK_RE)) referenced.add(m[1]);
    for (const m of smText.matchAll(BACKTICK_PATH_RE)) referenced.add(m[1]);
    for (const ref of [...referenced].sort()) {
      if (/^(https?:|mailto:)/.test(ref)) continue;
      if (!fs.existsSync(path.resolve(path.dirname(skillMd), ref))) result.broken_references.push(ref);
    }
  }

  // per-file sweeps
  const hosts = new Map(), envs = new Set(), connHits = new Map();
  const pyDeps = new Set(), pyStd = new Set(), nodeDeps = new Set(), interpreters = new Set();

  for (const [relPath, text] of corpus) {
    result.destructive.push(...findAll(DESTRUCTIVE_PATTERNS, text, relPath));
    result.credentials.push(...findAll(CREDENTIAL_PATTERNS, text, relPath));
    result.injection.push(...findAll(INJECTION_PATTERNS, text, relPath));
    result.placeholders.push(...findAll(PLACEHOLDER_PATTERNS, text, relPath));

    for (const m of text.matchAll(URL_RE)) {
      if (!hosts.has(m[1])) hosts.set(m[1], new Set());
      hosts.get(m[1]).add(relPath);
    }
    for (const m of text.matchAll(ENV_PY_RE)) envs.add(m[1]);
    const ext = path.extname(relPath).toLowerCase();
    if (!JS_SUFFIXES.has(ext)) for (const m of text.matchAll(ENV_SH_RE)) envs.add(m[1]);

    const shebang = SHEBANG_RE.exec(text);
    if (shebang) interpreters.add(shebang[1].startsWith("python") ? "python" : shebang[1]);
    if (ext === ".py") {
      interpreters.add("python");
      for (const m of text.matchAll(PY_IMPORT_RE)) {
        const mod = (m[1] || m[2] || "").split(".")[0];
        if (mod) (PY_STDLIB.has(mod) ? pyStd : pyDeps).add(mod);
      }
    }
    if ([".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx"].includes(ext)) {
      interpreters.add("node");
      for (const m of text.matchAll(JS_IMPORT_RE)) {
        const spec = m[1] || m[2] || m[3] || "";
        if (!spec || spec.startsWith(".") || spec.startsWith("/")) continue;
        const bare = spec.replace(/^node:/, "").split("/")[0];
        if (!NODE_BUILTINS.has(bare)) nodeDeps.add(bare);
      }
    }
    if (ext === ".sh" || ext === ".bash") interpreters.add("bash");

    const low = text.toLowerCase();
    for (const [hint, klass] of Object.entries(CONNECTOR_HINTS)) {
      if (low.includes(hint)) {
        const key = `${hint}\u0000${klass}`;
        if (!connHits.has(key)) connHits.set(key, new Set());
        connHits.get(key).add(relPath);
      }
    }
  }

  // A hint that appears only in a bundled doc is a mention; one in SKILL.md or a
  // script is a real dependency. Surface the distinction rather than flattening it.
  result.connectors = [...connHits.entries()]
    .map(([key, f]) => {
      const [name, klass] = key.split("\u0000");
      const seen = [...f].sort();
      return { name, class: klass, seen_in: seen,
        in_primary: seen.some((x) => x.toLowerCase() === "skill.md" || x.startsWith("scripts/")) };
    })
    .sort((a, b) => (a.in_primary === b.in_primary ? a.name.localeCompare(b.name) : a.in_primary ? -1 : 1));

  result.external_hosts = [...hosts.entries()].sort((a, b) => a[0].localeCompare(b[0]))
    .map(([host, f]) => ({ host, seen_in: [...f].sort() }));
  result.env_vars = [...envs].sort();
  result.runtime.interpreters = [...interpreters].sort();
  result.runtime.python_third_party = [...pyDeps].sort();
  result.runtime.node_third_party = [...nodeDeps].sort();

  if (result.broken_references.length) {
    result.smells.push(`${result.broken_references.length} referenced file(s) missing from the bundle`);
  }
  if (result.injection.length) {
    result.smells.push("text resembling instruction-override / prompt-injection found — review each hit; documentation quoting such phrases as examples will also match");
  }
  if (result.credentials.length) result.smells.push("credential-shaped strings found in the bundle");
  if (result.runtime.python_third_party.length) {
    result.smells.push(`needs Python packages that are not stdlib: ${result.runtime.python_third_party.join(", ")} — confirm these exist in the target environment before adopting`);
  }
  if (result.runtime.node_third_party.length) {
    result.smells.push(`needs npm packages: ${result.runtime.node_third_party.join(", ")} — confirm these exist in the target environment before adopting`);
  }
  return result;
}

/* ── rendering ───────────────────────────────────────────────────── */

function render(r) {
  if (r.error) return `ERROR: ${r.error}`;
  const out = [];
  const add = (s = "") => out.push(s);
  add(`SKILL SCAN — ${r.frontmatter.name || "(no name)"}`);
  add(`root: ${r.root}`);
  add();
  const cc = r.context_cost;
  if (cc && Object.keys(cc).length) {
    add("CONTEXT COST (estimated)");
    add(`  standing (name+description, always loaded) : ${cc.standing_est_tokens} tok (${cc.description_words} words)`);
    add(`  trigger  (SKILL.md body)                   : ${cc.trigger_est_tokens} tok (${cc.skill_md_lines} lines)`);
    add(`  bundled resources (on demand)              : ${cc.bundled_resources_est_tokens} tok`);
    add();
  }
  const rt = r.runtime;
  if (rt.interpreters.length || rt.python_third_party.length || rt.node_third_party.length) {
    add("RUNTIME REQUIRED");
    if (rt.interpreters.length) add(`  interpreters      : ${rt.interpreters.join(", ")}`);
    if (rt.python_third_party.length) add(`  python packages   : ${rt.python_third_party.join(", ")}`);
    if (rt.node_third_party.length) add(`  npm packages      : ${rt.node_third_party.join(", ")}`);
    add();
  }
  for (const [label, key] of [
    ["FRONTMATTER PROBLEMS", "frontmatter_problems"],
    ["BROKEN REFERENCES", "broken_references"],
    ["SMELLS", "smells"],
    ["ENV VARS", "env_vars"],
  ]) {
    if (r[key] && r[key].length) { add(label); for (const item of r[key]) add(`  - ${item}`); add(); }
  }
  if (r.external_hosts.length) {
    add("EXTERNAL HOSTS");
    for (const h of r.external_hosts) add(`  - ${h.host}  (in: ${h.seen_in.join(", ")})`);
    add();
  }
  if (r.connectors.length) {
    const primary = r.connectors.filter((c) => c.in_primary);
    const mentions = r.connectors.filter((c) => !c.in_primary);
    add("DEPENDENCY HINTS (in SKILL.md or scripts/)");
    if (primary.length) for (const c of primary) add(`  - ${c.name}  [${c.class}]  (in: ${c.seen_in.join(", ")})`);
    else add("  - none");
    if (mentions.length) add(`  mentioned only in bundled docs: ${mentions.map((c) => c.name).join(", ")}`);
    add();
  }
  for (const [label, key] of [
    ["INSTRUCTION-OVERRIDE / INJECTION HITS", "injection"],
    ["CREDENTIAL-SHAPED STRINGS", "credentials"],
    ["DESTRUCTIVE COMMANDS", "destructive"],
    ["PLACEHOLDERS", "placeholders"],
  ]) {
    const hits = r[key] || [];
    if (!hits.length) continue;
    add(`${label} (${hits.length})`);
    for (const h of hits.slice(0, 20)) add(`  - ${h.file}:${h.line} [${h.label}] ${h.snippet}`);
    if (hits.length > 20) add(`  ... ${hits.length - 20} more`);
    add();
  }
  add(`FILES SCANNED: ${r.files.length}`);
  return out.join("\n");
}

/* ── cli ─────────────────────────────────────────────────────────── */

function main() {
  const argv = process.argv.slice(2);
  if (!argv.length || argv.includes("--help") || argv.includes("-h")) {
    console.log("usage: node skill-scan.mjs <folder|SKILL.md|bundle.skill> [--json out.json] [--quiet] [--unpack dir]");
    return 0;
  }
  const flag = (name) => { const i = argv.indexOf(name); return i !== -1 ? argv[i + 1] : null; };
  const positional = argv.filter((a, i) =>
    !a.startsWith("--") && argv[i - 1] !== "--json" && argv[i - 1] !== "--unpack");
  let target = path.resolve(positional[0] || ".");

  if (!fs.existsSync(target)) { console.error(`ERROR: path does not exist: ${target}`); return 2; }

  // A .skill bundle is a zip; open it in place so `unzip` isn't needed.
  if (fs.statSync(target).isFile() && /\.(skill|zip)$/i.test(target)) {
    const dest = path.resolve(flag("--unpack") || path.join(path.dirname(target), path.basename(target).replace(/\.(skill|zip)$/i, "") + "-unpacked"));
    fs.mkdirSync(dest, { recursive: true });
    const written = unpackSkill(target, dest);
    console.log(`unpacked ${written.length} file(s) to ${dest}\n`);
    const inner = fs.readdirSync(dest, { withFileTypes: true }).filter((e) => e.isDirectory());
    target = (inner.length === 1 && !fs.existsSync(path.join(dest, "SKILL.md")))
      ? path.join(dest, inner[0].name) : dest;
  }

  const result = scan(target);
  const jsonOut = flag("--json");
  if (jsonOut) fs.writeFileSync(path.resolve(jsonOut), JSON.stringify(result, null, 2), "utf8");
  if (!argv.includes("--quiet")) console.log(render(result));
  return 0;
}

process.exit(main());
