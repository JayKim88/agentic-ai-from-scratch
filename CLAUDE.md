# CLAUDE.md

Project-specific instructions. Global rules in `~/.claude/CLAUDE.md` still apply;
this file only records what differs or what cannot be inferred from the code.

## What this project is

Local workspace for the ungraded code examples of the DeepLearning.AI course
[**Agentic AI**](https://www.deeplearning.ai/courses/agentic-ai) (Andrew Ng, intermediate, ~10h).

It is a **learning workspace, not a product.** Lab notebooks are downloaded from the
course platform and run locally. There is no application to ship and no test suite.

Course modules: (1) agentic workflows (2) reflection (3) tool use + MCP
(4) evaluation & error analysis (5) planning & multi-agent → final research agent.

## Environment

| | |
|---|---|
| Interpreter | `./venv/bin/python` — Python 3.12.11 |
| Activate | `source venv/bin/activate` |
| Jupyter kernel | `venv` / display name `Python (agentic-ai)` |

- **Always use `./venv/bin/python` or `./venv/bin/pip`.** Never the system `python3`
  (3.13.1) — it does not have the course dependencies.
- Adding a package means editing `requirements.txt` **and** installing it. Do not
  install into the venv without recording it.

## Hard constraints

1. **Do not lift the `nltk<3.10` pin.** nltk 3.10 added an import guard that blocks any
   nltk-initiated import resolving under the cwd — which includes `./venv/.../site-packages`.
   Lifting the pin breaks `import textstat`. Rationale is in `requirements.txt` and README.
   `PYTHONSAFEPATH=1` does not work around it.

2. **Never introduce agent frameworks.** No LangChain, LlamaIndex, CrewAI, AutoGen, or
   similar. The course's whole point is implementing agentic patterns from first
   principles. Suggesting a framework defeats the exercise even when it would be shorter.
   `aisuite` is the only abstraction in use, and only for swapping model providers.

3. **Never hardcode API keys.** Keys live in `.env`, loaded via `python-dotenv`.
   Do not print keys or full env dicts in notebook cells.

4. **Do not modify downloaded lab notebooks beyond what is asked.** They are course
   material — reference points for what the lesson taught. Prefer a new cell or a new
   file over rewriting the original.

## Working on labs

- Lab notebooks depend on helper scripts, config, and data files downloaded alongside
  them. If an import or file read fails, the missing sibling file is the first suspect —
  ask before reconstructing it from scratch.
- When explaining a lab, connect it back to the design pattern the module teaches
  (reflection / tool use / planning / multi-agent), not just the mechanics of the code.
- When a lab hits a library-version error, check the version first. Two known risks:
  **pandas 3.0.5** (labs may assume 2.x) and **nltk** (see above).

## Code style in this project

The global coding rules apply to any `.py` module extracted from a lab. They apply
**loosely inside notebook cells** — exploratory cells are allowed to be linear and
literal-heavy, since matching the lesson's code is more valuable than refactoring it.
Do not silently restructure lab code into "clean" code; if a cleanup is worth doing,
say so and let the user decide.

Tool-use labs generate LLM tool schemas from function docstrings via `docstring-parser`.
In those files, **the docstring is the interface** — keep parameter descriptions accurate
and complete, since they are what the model actually reads.

## Anthropic models

When a lab calls Claude, use current model IDs (`claude-opus-5`, `claude-sonnet-5`).
Load the `claude-api` skill before writing or debugging Anthropic SDK code rather than
answering from memory.

## Communication

- Explanations and generated documents in Korean; code, comments, config, and this file
  in English.
- The user is learning this material. Prefer explaining *why* a pattern is structured a
  certain way over just producing working code.
