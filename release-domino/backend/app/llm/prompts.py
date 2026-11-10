"""Centralized prompts for all local LLM tasks.
All prompts enforce strict JSON output and style/syntax preservation.
"""

SYSTEM_JSON_ONLY = (
    "You are a precise code analysis assistant for Release Domino. "
    "You MUST respond with valid JSON only. Do not wrap the JSON in markdown "
    "code blocks, and do not include any text before or after the JSON object."
)

SUMMARIZE_NODE_PROMPT = """Analyze the following source code file and return a JSON object with:
- "summary": a list of exactly 3 short plain-English bullet strings explaining how the file works
- "purpose": a 1-sentence string describing the main purpose of this file
- "exports": a list of strings naming the key exported functions, classes, or routes
- "risks": a list of strings describing potential bugs, failure modes, or security risks in this file

File Path: {path}
Language: {lang}
Dependencies: {deps}

Code:
{code}
"""

GENERATE_TESTS_PROMPT = """Write a complete, runnable unit test file for the following code focusing on the changed lines and edge cases.
Return a JSON object with:
- "test_code": a string containing the full runnable {framework} test file code
- "framework": "{framework}"

File Path: {path}
Language: {lang}
Changed Lines (Diff):
{diff}

Code:
{code}
"""

PROPOSE_CONNECTION_PROMPT = """Propose how to wire the source file into the destination file.
STRICT STYLE, COMPONENT MOUNTING & ARCHITECTURE PRESERVATION RULES:
1. NEVER remove, comment out, or alter existing CSS, SCSS, Tailwind, or stylesheet imports (e.g. `import './App.css'`, `import styles from './styles.module.css'`).
2. PRESERVE ALL EXISTING STYLING: NEVER replace existing CSS className hierarchies or inject page-breaking wrappers.
3. FOR REACT / UI COMPONENTS:
   - When importing a UI component into a React caller (e.g. `import ComponentName from '...'`), YOU MUST ALSO MOUNT AND RENDER IT inside the parent's JSX return block (e.g. `<ComponentName />` or an interactive trigger button). Do NOT just leave an unused import!
   - Ensure the component is actually visible to the user and can be clicked or interacted with.
4. JAVASCRIPT VS TYPESCRIPT SAFETY:
   - If destination file is `.js` or `.jsx`, use PURE JavaScript/JSX ONLY. Do NOT use TypeScript type annotations (no `: React.FC`, no `: NodeJS.Timeout`, no `interface`).
   - If destination file is `.ts` or `.tsx`, use valid TypeScript.
5. NO DUPLICATE EXPORTS & BALANCED SYNTAX:
   - Exactly ONE `export default` per file. Never concatenate two components with multiple `export default`.
   - Ensure all brackets `()`, `{{}}`, `[]` and JSX tags (`<div>...</div>`, `<section>...</section>`) are 100% balanced and syntactically valid.

Return a JSON object with:
- "patch": a valid unified-diff string that can be applied with `git apply`
- "endpoint": a string describing the function call, route, or import added
- "rationale": a plain-English explanation of how this connection works while preserving existing styling

Language: {lang}
Source File ({src_path}):
{src_code}

Destination File ({dst_path}):
{dst_code}
"""

AUTO_HEAL_CODE_PROMPT = """The following {lang} code failed pre-output syntax or JSX validation with error:
{error_msg}

Fix ONLY the syntax, indentation, bracket balance, or unclosed JSX tag error while preserving all existing CSS imports, classNames, and logic.
Return a JSON object with:
- "healed_code": the complete, syntactically valid {lang} source code
- "fix_summary": a 1-sentence explanation of what syntax error was repaired

Broken Code:
{code}
"""

ARCHITECTURE_SUMMARY_PROMPT = """Given the detected tech stack, styling system, execution configuration, and infrastructure connections below, write a concise 3-sentence plain-English summary of the project's architecture.
Return a JSON object with:
- "summary": a single string containing the 3 sentences.

Detected Stack: {stack}
Detected Infrastructure: {infra}
Node-to-Infra Links: {links}
"""