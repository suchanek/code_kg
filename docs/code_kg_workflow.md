CodeKG v0 — Command Workflow
	•	python build_codekg_sqlite.py --repo ~/repos/personal_agent/src --db ~/repos/personal_agent/codekg.sqlite --wipe
Build the authoritative SQLite knowledge graph from the Python source tree using AST analysis.
	•	python build_codekg_lancedb_v0.py --sqlite ~/repos/personal_agent/codekg.sqlite --lancedb ~/repos/personal_agent/codekg_lancedb --table codekg_nodes --wipe
Create a semantic vector index (LanceDB) over graph nodes for natural-language retrieval.
	•	python codekg_query_v0.py --sqlite ~/repos/personal_agent/codekg.sqlite --lancedb ~/repos/personal_agent/codekg_lancedb --table codekg_nodes --q "database connection url configuration" --k 8 --hop 1
Run a hybrid semantic + graph query to retrieve structurally related code elements.
	•	python codekg_query_v0.py --sqlite ~/repos/personal_agent/codekg.sqlite --lancedb ~/repos/personal_agent/codekg_lancedb --table codekg_nodes --q "database connection url configuration" --k 8 --hop 1 --pack-md /tmp/codekg_pack.md
Execute the query and emit a ranked, deduplicated, source-grounded snippet pack in Markdown.
	•	open /tmp/codekg_pack.md
Review the extracted definitions and call-site snippets with full source provenance.
