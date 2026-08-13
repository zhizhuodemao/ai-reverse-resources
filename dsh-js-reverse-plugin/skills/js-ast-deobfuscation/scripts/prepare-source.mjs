#!/usr/bin/env node

import {
  closeSync,
  constants,
  existsSync,
  fstatSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  realpathSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT_PATH = fileURLToPath(import.meta.url);
const SKILL_ROOT = path.dirname(path.dirname(SCRIPT_PATH));
const NO_FOLLOW = constants.O_NOFOLLOW ?? 0;

class PreparationError extends Error {
  constructor(code, message, details = undefined) {
    super(message);
    this.name = "PreparationError";
    this.code = code;
    this.details = details;
  }
}

function usage() {
  return `Usage:
  node scripts/prepare-source.mjs \\
    --source <source.js> \\
    --workspace <directory> \\
    [--prettier-bin <local-prettier-cli>] \\
    [--parser <prettier-parser>] \\
    [--run-id <unique-id>]

The script only prepares evidence:
  - copies the source without modifying it;
  - formats a derived copy with an already-installed local Prettier;
  - validates parsing and formatting idempotence;
  - records hashes and provenance as JSON.

It never downloads dependencies and never performs an AST deobfuscation transform.
`;
}

function parseArgs(argv) {
  const result = {};
  const supported = new Set([
    "source",
    "workspace",
    "prettier-bin",
    "parser",
    "run-id",
  ]);

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];

    if (argument === "--help" || argument === "-h") {
      result.help = true;
      continue;
    }

    if (!argument.startsWith("--")) {
      throw new PreparationError(
        "INVALID_ARGUMENT",
        `Unexpected positional argument: ${argument}`,
      );
    }

    const equalsIndex = argument.indexOf("=");
    const key =
      equalsIndex === -1
        ? argument.slice(2)
        : argument.slice(2, equalsIndex);

    if (!supported.has(key)) {
      throw new PreparationError(
        "UNKNOWN_OPTION",
        `Unknown option: --${key}`,
      );
    }

    const value =
      equalsIndex === -1 ? argv[(index += 1)] : argument.slice(equalsIndex + 1);

    if (value === undefined || value === "" || value.startsWith("--")) {
      throw new PreparationError(
        "MISSING_OPTION_VALUE",
        `Option --${key} requires a value`,
      );
    }

    if (result[key] !== undefined) {
      throw new PreparationError(
        "DUPLICATE_OPTION",
        `Option --${key} was provided more than once`,
      );
    }

    result[key] = value;
  }

  if (!result.help) {
    for (const key of ["source", "workspace"]) {
      if (!result[key]) {
        throw new PreparationError(
          "MISSING_REQUIRED_OPTION",
          `Option --${key} is required`,
        );
      }
    }
  }

  return result;
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function truncate(value, limit = 8_000) {
  const text = String(value ?? "");
  return text.length <= limit ? text : `${text.slice(0, limit)}\n<truncated>`;
}

function generateRunId() {
  const timestamp = new Date()
    .toISOString()
    .replaceAll("-", "")
    .replaceAll(":", "")
    .replace(/\.\d{3}Z$/, "Z");
  return `${timestamp}-${randomUUID().slice(0, 8)}`;
}

function validateRunId(value) {
  if (
    value === "." ||
    value === ".." ||
    !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(value)
  ) {
    throw new PreparationError(
      "INVALID_RUN_ID",
      "run-id must be 1-128 characters using letters, digits, dot, underscore, or hyphen; it cannot be . or ..",
      { runId: value },
    );
  }
  return value;
}

function ensureSafeDirectory(directoryPath) {
  const absolute = path.resolve(directoryPath);

  if (existsSync(absolute)) {
    const metadata = lstatSync(absolute);
    if (metadata.isSymbolicLink()) {
      throw new PreparationError(
        "SYMLINK_DIRECTORY_REJECTED",
        `Refusing symbolic-link directory: ${absolute}`,
      );
    }
    if (!metadata.isDirectory()) {
      throw new PreparationError(
        "NON_DIRECTORY_REJECTED",
        `Expected a directory: ${absolute}`,
      );
    }
    return absolute;
  }

  const parent = path.dirname(absolute);
  if (parent === absolute) {
    throw new PreparationError(
      "DIRECTORY_CREATE_FAILED",
      `Cannot create directory: ${absolute}`,
    );
  }

  ensureSafeDirectory(parent);
  mkdirSync(absolute, { mode: 0o755 });
  return absolute;
}

function readRegularSource(sourcePath) {
  const absolute = path.resolve(sourcePath);
  let metadata;

  try {
    metadata = lstatSync(absolute);
  } catch (error) {
    throw new PreparationError(
      "SOURCE_NOT_FOUND",
      `Source does not exist: ${absolute}`,
      { cause: error.message },
    );
  }

  if (metadata.isSymbolicLink()) {
    throw new PreparationError(
      "SOURCE_SYMLINK_REJECTED",
      `Refusing symbolic-link source: ${absolute}`,
    );
  }
  if (!metadata.isFile()) {
    throw new PreparationError(
      "SOURCE_NOT_REGULAR_FILE",
      `Source is not a regular file: ${absolute}`,
    );
  }

  let descriptor;
  try {
    descriptor = openSync(absolute, constants.O_RDONLY | NO_FOLLOW);
    const openedMetadata = fstatSync(descriptor);
    if (!openedMetadata.isFile()) {
      throw new PreparationError(
        "SOURCE_NOT_REGULAR_FILE",
        `Opened source is not a regular file: ${absolute}`,
      );
    }
    const bytes = readFileSync(descriptor);
    return {
      requestedPath: sourcePath,
      path: absolute,
      realPath: realpathSync(absolute),
      bytes,
      size: bytes.length,
      sha256: sha256(bytes),
      device: openedMetadata.dev,
      inode: openedMetadata.ino,
    };
  } finally {
    if (descriptor !== undefined) {
      closeSync(descriptor);
    }
  }
}

function ancestors(startPath) {
  const result = [];
  let current = path.resolve(startPath);

  while (true) {
    result.push(current);
    const parent = path.dirname(current);
    if (parent === current) {
      return result;
    }
    current = parent;
  }
}

function prettierCandidates(basePath) {
  return [
    path.join(basePath, "node_modules/prettier/bin/prettier.cjs"),
    path.join(basePath, "node_modules/prettier/bin/prettier.js"),
    path.join(basePath, "node_modules/prettier/bin-prettier.js"),
    path.join(basePath, "node_modules/prettier/cli.js"),
    path.join(basePath, "node_modules/.bin/prettier"),
  ];
}

function resolveToolFile(candidatePath) {
  if (!existsSync(candidatePath)) {
    return null;
  }

  const requestedPath = path.resolve(candidatePath);
  const requestedMetadata = lstatSync(requestedPath);
  const resolvedPath = realpathSync(requestedPath);
  const resolvedMetadata = statSync(resolvedPath);

  if (!resolvedMetadata.isFile()) {
    return null;
  }

  return {
    requestedPath,
    resolvedPath,
    followedToolSymlink:
      requestedMetadata.isSymbolicLink() || resolvedPath !== requestedPath,
  };
}

function buildLauncher(tool) {
  const extension = path.extname(tool.resolvedPath).toLowerCase();
  let firstLine = "";

  try {
    firstLine = readFileSync(tool.resolvedPath, {
      encoding: "utf8",
      flag: "r",
    }).slice(0, 160);
  } catch {
    // spawn will return a precise error if this non-JavaScript tool cannot run.
  }

  if (
    new Set([".js", ".cjs", ".mjs"]).has(extension) ||
    /^#!.*\bnode\b/m.test(firstLine)
  ) {
    return {
      command: process.execPath,
      prefixArgs: [tool.resolvedPath],
    };
  }

  return {
    command: tool.resolvedPath,
    prefixArgs: [],
  };
}

function runTool(launcher, args, options = {}) {
  const result = spawnSync(
    launcher.command,
    [...launcher.prefixArgs, ...args],
    {
      cwd: options.cwd,
      input: options.input,
      encoding: options.encoding ?? null,
      maxBuffer: options.maxBuffer ?? 16 * 1024 * 1024,
      windowsHide: true,
    },
  );

  if (result.error) {
    throw new PreparationError(
      "TOOL_EXECUTION_FAILED",
      `Failed to execute local Prettier: ${result.error.message}`,
      {
        command: launcher.command,
        cause: result.error.message,
      },
    );
  }

  return result;
}

function verifyPrettier(tool) {
  const launcher = buildLauncher(tool);
  const result = runTool(launcher, ["--version"], { encoding: "utf8" });
  const version = String(result.stdout ?? "").trim();

  if (result.status !== 0 || version === "") {
    throw new PreparationError(
      "INVALID_PRETTIER_BINARY",
      `Local Prettier version check failed: ${tool.requestedPath}`,
      {
        exitStatus: result.status,
        stderr: truncate(result.stderr),
      },
    );
  }

  return {
    ...tool,
    launcher,
    version,
  };
}

function discoverPrettier({ explicitPath, sourcePath, workspacePath }) {
  if (explicitPath) {
    const tool = resolveToolFile(path.resolve(explicitPath));
    if (!tool) {
      throw new PreparationError(
        "PRETTIER_BIN_INVALID",
        `--prettier-bin is not a regular local file: ${path.resolve(explicitPath)}`,
      );
    }
    return {
      ...verifyPrettier(tool),
      discovery: "explicit",
      discoveryBase: null,
      searched: [path.resolve(explicitPath)],
    };
  }

  const groups = [
    {
      discovery: "source-project",
      bases: ancestors(path.dirname(sourcePath)),
    },
    {
      discovery: "workspace",
      bases: ancestors(workspacePath),
    },
    {
      discovery: "skill",
      bases: [SKILL_ROOT],
    },
  ];
  const searched = [];
  const seen = new Set();

  for (const group of groups) {
    for (const base of group.bases) {
      for (const candidate of prettierCandidates(base)) {
        const absolute = path.resolve(candidate);
        if (seen.has(absolute)) {
          continue;
        }
        seen.add(absolute);
        searched.push(absolute);

        const tool = resolveToolFile(absolute);
        if (tool) {
          return {
            ...verifyPrettier(tool),
            discovery: group.discovery,
            discoveryBase: base,
            searched,
          };
        }
      }
    }
  }

  throw new PreparationError(
    "PRETTIER_NOT_FOUND",
    "No local Prettier was found. Install it in an isolated project/tooling directory or provide --prettier-bin. This script does not use npx and does not download packages.",
    { searched },
  );
}

function inferParser(sourcePath, requestedParser) {
  if (requestedParser) {
    if (
      requestedParser.length > 100 ||
      /[\u0000-\u001f\u007f]/.test(requestedParser)
    ) {
      throw new PreparationError(
        "INVALID_PARSER",
        "Parser contains invalid control characters or is too long",
      );
    }
    return {
      parser: requestedParser,
      source: "explicit",
    };
  }

  const extension = path.extname(sourcePath).toLowerCase();
  if (new Set([".ts", ".tsx", ".mts", ".cts"]).has(extension)) {
    return {
      parser: "typescript",
      source: `inferred-from-${extension}`,
    };
  }

  return {
    parser: "babel",
    source: extension ? `inferred-from-${extension}` : "default",
  };
}

function describeConfigCandidate(candidatePath, kind) {
  const absolute = path.resolve(candidatePath);
  const metadata = lstatSync(absolute);

  if (metadata.isSymbolicLink()) {
    return {
      path: absolute,
      kind,
      regularFile: false,
      symbolicLink: true,
      sha256: null,
      note: "Symlink candidate recorded but not followed or loaded",
    };
  }

  if (!metadata.isFile()) {
    return {
      path: absolute,
      kind,
      regularFile: false,
      symbolicLink: false,
      sha256: null,
      note: "Non-regular candidate recorded but not loaded",
    };
  }

  return {
    path: absolute,
    kind,
    regularFile: true,
    symbolicLink: false,
    sha256: sha256(readFileSync(absolute)),
    note: "Detected and hashed as bytes; not applied",
  };
}

function detectProjectPrettierConfigs(sourcePath) {
  const configNames = [
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.json5",
    ".prettierrc.yaml",
    ".prettierrc.yml",
    ".prettierrc.toml",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.mjs",
    ".prettierrc.ts",
    ".prettierrc.cts",
    ".prettierrc.mts",
    "prettier.config.js",
    "prettier.config.cjs",
    "prettier.config.mjs",
    "prettier.config.ts",
    "prettier.config.cts",
    "prettier.config.mts",
  ];
  const detected = [];
  const warnings = [];

  for (const directory of ancestors(path.dirname(sourcePath))) {
    const packagePath = path.join(directory, "package.json");
    if (existsSync(packagePath)) {
      const candidate = describeConfigCandidate(
        packagePath,
        "package.json",
      );
      if (candidate.regularFile) {
        try {
          const parsed = JSON.parse(readFileSync(packagePath, "utf8"));
          if (
            parsed &&
            typeof parsed === "object" &&
            Object.hasOwn(parsed, "prettier")
          ) {
            detected.push(candidate);
          }
        } catch (error) {
          warnings.push({
            path: packagePath,
            message: `package.json was not parsed while detecting a Prettier field: ${error.message}`,
          });
        }
      } else {
        warnings.push({
          path: packagePath,
          message: candidate.note,
        });
      }
    }

    for (const configName of configNames) {
      const candidatePath = path.join(directory, configName);
      if (existsSync(candidatePath)) {
        detected.push(
          describeConfigCandidate(candidatePath, configName),
        );
      }
    }
  }

  return {
    detected,
    warnings,
    applied: false,
  };
}

function formatAndValidate(
  prettier,
  source,
  parser,
  isolatedConfigPath,
  runRoot,
) {
  const args = [
    "--parser",
    parser,
    "--config",
    isolatedConfigPath,
    "--no-editorconfig",
    "--stdin-filepath",
    source.realPath,
  ];
  const maxBuffer = Math.max(
    32 * 1024 * 1024,
    source.bytes.length * 8 + 1024 * 1024,
  );
  const first = runTool(prettier.launcher, args, {
    cwd: runRoot,
    input: source.bytes,
    maxBuffer,
  });

  if (first.status !== 0) {
    throw new PreparationError(
      "PRETTIER_FORMAT_FAILED",
      "Prettier could not parse and format the source",
      {
        parser,
        exitStatus: first.status,
        stderr: truncate(first.stderr),
      },
    );
  }

  const formatted = Buffer.from(first.stdout ?? []);
  const second = runTool(prettier.launcher, args, {
    cwd: runRoot,
    input: formatted,
    maxBuffer: Math.max(
      32 * 1024 * 1024,
      formatted.length * 8 + 1024 * 1024,
    ),
  });

  if (second.status !== 0) {
    throw new PreparationError(
      "PRETTIER_REPARSE_FAILED",
      "Prettier formatted the source but could not parse the formatted result",
      {
        parser,
        exitStatus: second.status,
        stderr: truncate(second.stderr),
      },
    );
  }

  const reformatted = Buffer.from(second.stdout ?? []);
  if (!formatted.equals(reformatted)) {
    throw new PreparationError(
      "PRETTIER_NOT_IDEMPOTENT",
      "The formatted result changed on a second pass with the same parser and configuration",
      {
        parser,
        firstSha256: sha256(formatted),
        secondSha256: sha256(reformatted),
      },
    );
  }

  return {
    args,
    formatted,
    firstStderr: truncate(first.stderr),
    secondStderr: truncate(second.stderr),
    syntaxValidation: {
      method: "prettier-reparse-and-idempotence",
      parser,
      passed: true,
    },
  };
}

function writeExclusive(filePath, value, mode = 0o644) {
  writeFileSync(filePath, value, {
    flag: "wx",
    mode,
  });
}

const state = {
  runId: null,
  runRoot: null,
  reportPath: null,
  sourcePath: null,
};

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    process.stdout.write(usage());
    return;
  }

  const source = readRegularSource(options.source);
  const workspace = path.resolve(options.workspace);
  const runId = validateRunId(options["run-id"] ?? generateRunId());
  const parser = inferParser(source.realPath, options.parser);
  const prettier = discoverPrettier({
    explicitPath: options["prettier-bin"],
    sourcePath: source.realPath,
    workspacePath: workspace,
  });

  state.runId = runId;
  state.sourcePath = source.realPath;

  ensureSafeDirectory(workspace);
  const runsDirectory = ensureSafeDirectory(path.join(workspace, "runs"));
  const runRoot = path.join(runsDirectory, runId);
  if (existsSync(runRoot)) {
    throw new PreparationError(
      "RUN_ALREADY_EXISTS",
      `Refusing to overwrite existing run evidence: ${runRoot}`,
      { runId, runRoot },
    );
  }

  mkdirSync(runRoot, { mode: 0o755 });
  const inputDirectory = path.join(runRoot, "input");
  const stepsDirectory = path.join(runRoot, "steps");
  const reportsDirectory = path.join(runRoot, "reports");
  mkdirSync(inputDirectory, { mode: 0o755 });
  mkdirSync(stepsDirectory, { mode: 0o755 });
  mkdirSync(reportsDirectory, { mode: 0o755 });

  state.runRoot = runRoot;
  state.reportPath = path.join(reportsDirectory, "preparation.json");

  const originalCopyPath = path.join(inputDirectory, "source.original.js");
  const formattedPath = path.join(stepsDirectory, "00_formatted.js");
  const isolatedConfigPath = path.join(
    reportsDirectory,
    "prettier.config.json",
  );

  if (
    path.resolve(source.realPath) === path.resolve(originalCopyPath) ||
    path.resolve(source.realPath) === path.resolve(formattedPath)
  ) {
    throw new PreparationError(
      "IN_PLACE_WRITE_REJECTED",
      "Refusing to overwrite the source in place",
    );
  }

  const isolatedConfigBytes = Buffer.from("{}\n", "utf8");
  writeExclusive(isolatedConfigPath, isolatedConfigBytes, 0o444);

  writeExclusive(originalCopyPath, source.bytes, 0o444);
  const originalCopy = readFileSync(originalCopyPath);
  if (sha256(originalCopy) !== source.sha256) {
    throw new PreparationError(
      "SOURCE_COPY_HASH_MISMATCH",
      "The frozen source copy does not match the input hash",
    );
  }

  const projectConfigs = detectProjectPrettierConfigs(source.realPath);
  const formatted = formatAndValidate(
    prettier,
    source,
    parser.parser,
    isolatedConfigPath,
    runRoot,
  );
  writeExclusive(formattedPath, formatted.formatted);

  const formattedOnDisk = readFileSync(formattedPath);
  const formattedHash = sha256(formattedOnDisk);
  if (formattedHash !== sha256(formatted.formatted)) {
    throw new PreparationError(
      "FORMATTED_WRITE_HASH_MISMATCH",
      "The formatted file on disk does not match Prettier output",
    );
  }

  const sourceAfter = readRegularSource(source.realPath);
  if (sourceAfter.sha256 !== source.sha256) {
    throw new PreparationError(
      "SOURCE_CHANGED_DURING_PREPARATION",
      "The source hash changed during preparation; derived evidence is not accepted",
      {
        beforeSha256: source.sha256,
        afterSha256: sourceAfter.sha256,
      },
    );
  }

  const report = {
    schemaVersion: 1,
    status: "ok",
    exitStatus: 0,
    createdAt: new Date().toISOString(),
    runId,
    purpose: "source-preparation-only",
    runtime: {
      nodeVersion: process.version,
      platform: process.platform,
      arch: process.arch,
      argv: [...process.argv],
      replayCommand: [
        process.execPath,
        SCRIPT_PATH,
        "--source",
        source.realPath,
        "--workspace",
        workspace,
        "--prettier-bin",
        prettier.resolvedPath,
        "--parser",
        parser.parser,
        "--run-id",
        runId,
      ],
    },
    source: {
      requestedPath: source.requestedPath,
      realPath: source.realPath,
      size: source.size,
      initialSha256: source.sha256,
      finalSha256: sourceAfter.sha256,
      unchanged: true,
      regularFile: true,
      symbolicLink: false,
    },
    workspace: {
      requestedPath: options.workspace,
      workspacePath: workspace,
      runRoot,
      overwritePolicy: "new-run-directory-or-fail",
    },
    prettier: {
      discovery: prettier.discovery,
      discoveryBase: prettier.discoveryBase,
      requestedPath: prettier.requestedPath,
      resolvedPath: prettier.resolvedPath,
      followedToolSymlink: prettier.followedToolSymlink,
      version: prettier.version,
      parser: parser.parser,
      parserSource: parser.source,
      config: {
        appliedPath: isolatedConfigPath,
        appliedSha256: sha256(isolatedConfigBytes),
        appliedContents: "empty JSON object",
        projectConfigApplied: false,
        editorConfigApplied: false,
        detectedProjectConfigs: projectConfigs.detected,
        detectionWarnings: projectConfigs.warnings,
      },
      arguments: formatted.args,
      firstPassStderr: formatted.firstStderr,
      validationPassStderr: formatted.secondStderr,
      syntaxValidation: formatted.syntaxValidation,
      downloadedByScript: false,
    },
    outputs: {
      originalCopy: {
        path: originalCopyPath,
        relativePath: "input/source.original.js",
        size: originalCopy.length,
        sha256: sha256(originalCopy),
      },
      formattedView: {
        path: formattedPath,
        relativePath: "steps/00_formatted.js",
        size: formattedOnDisk.length,
        sha256: formattedHash,
      },
      prettierConfig: {
        path: isolatedConfigPath,
        relativePath: "reports/prettier.config.json",
        size: isolatedConfigBytes.length,
        sha256: sha256(isolatedConfigBytes),
      },
      report: {
        path: state.reportPath,
        relativePath: "reports/preparation.json",
      },
    },
    guarantees: [
      "The input source was opened as a regular non-symlink file.",
      "The input source hash was unchanged after formatting.",
      "All run outputs were created in a new run directory.",
      "Only the run-local empty JSON Prettier config was applied.",
      "Project Prettier and EditorConfig files were not applied.",
      "Prettier parsed both the input and the formatted result.",
      "The formatted result was idempotent under the same parser and configuration.",
      "No dependency was downloaded by this script.",
      "No AST deobfuscation transform was performed.",
    ],
  };

  writeExclusive(
    state.reportPath,
    `${JSON.stringify(report, null, 2)}\n`,
  );
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
}

try {
  main();
} catch (error) {
  const payload = {
    schemaVersion: 1,
    status: "error",
    exitStatus: 1,
    createdAt: new Date().toISOString(),
    code: error.code ?? "UNEXPECTED_ERROR",
    message: error.message,
    details: error.details,
    runId: state.runId,
    runRoot: state.runRoot,
    sourcePath: state.sourcePath,
    preservedPartialEvidence: state.runRoot !== null,
  };

  if (
    state.reportPath &&
    !existsSync(state.reportPath)
  ) {
    try {
      writeExclusive(
        state.reportPath,
        `${JSON.stringify(payload, null, 2)}\n`,
      );
      payload.reportPath = state.reportPath;
    } catch (reportError) {
      payload.reportWriteError = reportError.message;
    }
  }

  process.stderr.write(`${JSON.stringify(payload, null, 2)}\n`);
  process.exitCode = 1;
}
