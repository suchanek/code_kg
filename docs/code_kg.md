# CodeKG v0
## A Deterministic Knowledge Graph for Python Codebases
### With Semantic Indexing and Source-Grounded Snippet Packing

**Author:** Eric G. Suchanek, PhD

---

## Abstract

CodeKG constructs a **deterministic, explainable knowledge graph** from a Python codebase using static analysis. The graph captures structural relationships—definitions, calls, imports, inheritance—directly from the Python AST, stores them in SQLite, and augments retrieval with vector embeddings via LanceDB.

Structure is treated as **ground truth**; semantic search is an acceleration layer. The result is a searchable, auditable representation of a codebase that supports precise navigation, contextual snippet extraction, and downstream reasoning without hallucination.

---

## 1. Motivation

As Python systems grow, basic architectural questions become difficult:

- Where is database configuration actually defined?
- Which functions participate in connection setup and verification?
- How does configuration propagate through runtime logic?
- Where are specific services or APIs invoked, and in what context?

Text search and IDE symbol lookup are brittle. LLMs provide semantic intuition but are not source-grounded. CodeKG bridges this gap by constructing a first-principles representation of code structure and layering semantic retrieval on top—without surrendering determinism or provenance.

---

## 2. Design Principles

1. **Structure is authoritative**
   The AST-derived graph is the source of truth.

2. **Semantics accelerate, never decide**
   Vector embeddings seed and rank retrieval but never invent structure.

3. **Everything is traceable**
   Nodes and edges map to concrete files and line numbers.

4. **Determinism over heuristics**
   Identical input yields identical output.

5. **Composable artifacts**
   SQLite for structure, LanceDB for vectors, Markdown/JSON for consumption.

---

## 3. Core Data Model

### 3.1 Nodes

Nodes represent concrete program elements:

| Kind     | Description                          |
|----------|--------------------------------------|
| module   | Python source file                   |
| class    | Class definition                     |
| function | Top-level function                   |
| method   | Class method                         |
| symbol   | Names, attributes, call expressions  |

Each node stores:

- `id` (stable, deterministic)
- `kind`
- `name`
- `qualname`
- `module_path`
- `lineno`
- `end_lineno`
- `docstring`

Nodes live in **SQLite**, which is canonical.

---

### 3.2 Edges

Edges encode semantic relationships:

| Relation  | Meaning                             |
|-----------|-------------------------------------|
| CONTAINS  | Module → class/function             |
| CALLS     | Function/method → function/method   |
| IMPORTS   | Module → module/symbol              |
| INHERITS  | Class → base class                  |

Edges may include **evidence**, typically JSON:

~~~json
{
  "lineno": 586,
  "expr": "psql_path = _get_psql_path()"
}
~~~

Evidence enables call-site extraction and auditability.

---

## 4. Build Pipeline

### 4.1 Static Analysis Phase (AST → SQLite)

The repository is parsed using Python’s `ast` module:

- Walk all `.py` files
- Extract definitions, calls, imports, inheritance
- Generate normalized node IDs
- Emit explicit edges with evidence

**Output:** a single SQLite database (`.codekg/graph.sqlite`) with:

- `nodes` table
- `edges` table

This phase uses **no embeddings and no LLMs**.

---

### 4.2 Semantic Indexing Phase (SQLite → LanceDB)

To support semantic retrieval:

1. Select semantic nodes: `module`, `class`, `function`, `method`
2. Build embedding text from:
   - name / qualname
   - docstring
   - (optional) signature hints
3. Embed with `sentence-transformers/all-MiniLM-L6-v2`
4. Store vectors in **LanceDB**

The vector index is **derived and disposable**; SQLite remains authoritative.

---

## 5. Hybrid Query Model

Queries execute in two explicit phases.

### 5.1 Semantic Seeding

~~~text
query → embedding → top-K node IDs
~~~

This identifies conceptually relevant entry points.

---

### 5.2 Structural Expansion

From semantic seeds, the graph is expanded using selected edge types:

- `CONTAINS`
- `CALLS`
- `IMPORTS`
- `INHERITS`

Expansion is bounded by hop count and records provenance (minimum hop distance and originating seed).

---

## 6. Ranking and Deduplication

### 6.1 Ranking

Nodes are ranked deterministically by:

1. Hop distance from seed
2. Seed embedding distance
3. Kind priority:

~~~text
function / method > class > module > symbol
~~~

Optional downweighting penalizes topic drift (e.g., “hindsight”, “ollama”) when terms appear in docstrings/snippets.

---

### 6.2 Dedupe by File and Span

To avoid redundant context:

- Each node produces a source span `(start_line, end_line)`
- Nodes in the same file with overlapping spans are deduplicated
- A per-file cap prevents large modules from dominating

---

## 7. Snippet Packing (Definitions)

For retained nodes, CodeKG extracts **source-grounded definition snippets**:

- uses `module_path`, `lineno`, `end_lineno`
- applies bounded context windows
- emits line-numbered code blocks

These context packs are suitable for:
- human review
- LLM ingestion (grounded)
- agent pipelines

---

## 8. Call-Site Snippets (Usage)

Beyond definitions, CodeKG extracts **call-site snippets**:

- For each `CALLS` edge:
  - use `evidence.lineno`
  - extract a small window around the call site
- Deduplicate overlapping call sites per file
- Rank call sites by caller/callee importance

This answers “where is this used?” with concrete source evidence.

---

## 9. Output Artifacts

- **SQLite** — canonical knowledge graph
- **LanceDB** — derived semantic vector index
- **Markdown** — human-readable context packs
- **JSON** — agent/LLM ingestion payload

---

## 10. End-to-End Workflow

~~~text
Repository
  ↓
AST parsing
  ↓
SQLite graph (nodes + edges)
  ↓
Vector indexing (LanceDB)
  ↓
Hybrid query (semantic + graph)
  ↓
Ranking + dedupe
  ↓
Snippet pack (Markdown / JSON)
~~~

---

## Conclusion

CodeKG shows that **explainable, scalable code understanding** emerges from combining static analysis with semantic indexing—without sacrificing determinism or trust. Structure remains authoritative, semantics improve recall, and every answer is grounded in the source tree.
