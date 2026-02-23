import ast

from code_kg.codekg import node_id

# Relation types (add to your constants or use strings directly)
REL_CALLS = "CALLS"
REL_CONTAINS = "CONTAINS"
REL_READS = "READS"
REL_WRITES = "WRITES"
REL_ATTR_ACCESS = "ATTR_ACCESS"
REL_DEPENDS_ON = "DEPENDS_ON"  # placeholder for future control-flow


class CodeKGVisitor(ast.NodeVisitor):
    def __init__(self, module_id: str, file_path: str):
        self.module_id = module_id
        self.file_path = file_path
        self.current_scope: list[str] = []  # qualnames stack
        self.current_func: str | None = None
        self.vars_in_scope: dict[str, set[str]] = {}  # scope → local vars set
        self._scope_kinds: dict[str, str] = {}  # qualname → kind
        self.edges: list[tuple[str, str, str, dict | None]] = []  # (src_id, tgt_id, rel, evidence)
        self.nodes: dict[str, dict] = {}  # id → node props (your existing)

    def _qualname(self, name: str) -> str:
        """Build qualified name, e.g. module.class.method"""
        if self.current_scope:
            return f"{self.current_scope[-1]}.{name}"
        return name

    def _get_node_id(self, qualname: str) -> str:
        """Build a stable node id using the project's ``kind:module:qualname`` convention."""
        kind = self._scope_kinds.get(qualname, "symbol")
        prefix = self.module_id + "."
        if kind == "module" or qualname == self.module_id:
            nid = node_id("module", self.module_id, None)
        else:
            rel_qn = qualname[len(prefix) :] if qualname.startswith(prefix) else qualname
            nid = node_id(kind, self.module_id, rel_qn)
        if nid not in self.nodes:
            self.nodes[nid] = {"qualname": qualname, "kind": kind, "file": self.file_path}
        return nid

    def _add_edge(self, src_id: str, tgt_id: str, rel: str, evidence: ast.AST | None = None):
        ev = {"lineno": getattr(evidence, "lineno", None), "file": self.file_path}
        self.edges.append((src_id, tgt_id, rel, ev))

    def _extract_reads(self, expr: ast.AST) -> set[str]:
        """Collect variable names that are loaded (READS)"""
        reads = set()
        for sub in ast.walk(expr):
            if isinstance(sub, ast.Name) and isinstance(
                sub.ctx, ast.Load | ast.Del
            ):  # Del can be read-like
                reads.add(sub.id)
        return reads

    def _add_var_edge(
        self, var_name: str, rel: str, target: str | None = None, evidence: ast.AST | None = None
    ):
        scope = self.current_scope[-1] if self.current_scope else None
        if not scope:
            return
        src_id = self._get_node_id(f"{scope}.{var_name}")  # per-scope var node
        if target:
            tgt_id = self._get_node_id(f"{scope}.{target}")
            self._add_edge(src_id, tgt_id, rel, evidence)
        # Optionally annotate var node itself

    # ────────────────────────────────────────────────
    # Enhanced visitors
    # ────────────────────────────────────────────────

    def visit_Module(self, node: ast.Module):
        self.current_scope = [self.module_id]
        self._scope_kinds[self.module_id] = "module"
        self.vars_in_scope[self.module_id] = set()
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        qualname = self._qualname(node.name)
        self._scope_kinds[qualname] = "class"
        self.current_scope.append(qualname)
        parent_id = self._get_node_id(self.current_scope[-2])
        class_id = self._get_node_id(qualname)
        self._add_edge(parent_id, class_id, REL_CONTAINS)
        self.generic_visit(node)
        self.current_scope.pop()

    def _seed_params(self, qualname: str, args: ast.arguments) -> None:
        """Seed all parameter names into the function's local variable scope.

        :param qualname: Qualified name of the function being entered.
        :param args: The ``ast.arguments`` node from the function definition.
        """
        all_params = (
            args.posonlyargs
            + args.args
            + args.kwonlyargs
            + ([args.vararg] if args.vararg else [])
            + ([args.kwarg] if args.kwarg else [])
        )
        for param in all_params:
            self.vars_in_scope[qualname].add(param.arg)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        qualname = self._qualname(node.name)
        parent_kind = self._scope_kinds.get(
            self.current_scope[-1] if self.current_scope else "", "module"
        )
        func_kind = "method" if parent_kind == "class" else "function"
        self._scope_kinds[qualname] = func_kind

        # Default expressions are evaluated in the enclosing scope, not the
        # function scope — process them before pushing the new scope.
        # kw_defaults may contain None for keyword-only args without a default.
        defaults = node.args.defaults + [d for d in node.args.kw_defaults if d is not None]
        for expr in defaults:
            for r in self._extract_reads(expr):
                self._add_var_edge(r, REL_READS, evidence=expr)

        self.current_scope.append(qualname)
        self.current_func = qualname
        self.vars_in_scope[qualname] = set()
        self._seed_params(qualname, node.args)

        parent_id = self._get_node_id(self.current_scope[-2])
        func_id = self._get_node_id(qualname)
        self._add_edge(parent_id, func_id, REL_CONTAINS)

        for stmt in node.body:
            self.visit(stmt)

        self.current_scope.pop()
        self.current_func = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        qualname = self._qualname(node.name)
        parent_kind = self._scope_kinds.get(
            self.current_scope[-1] if self.current_scope else "", "module"
        )
        func_kind = "method" if parent_kind == "class" else "function"
        self._scope_kinds[qualname] = func_kind

        # Default expressions are evaluated in the enclosing scope, not the
        # function scope — process them before pushing the new scope.
        # kw_defaults may contain None for keyword-only args without a default.
        defaults = node.args.defaults + [d for d in node.args.kw_defaults if d is not None]
        for expr in defaults:
            for r in self._extract_reads(expr):
                self._add_var_edge(r, REL_READS, evidence=expr)

        self.current_scope.append(qualname)
        self.current_func = qualname
        self.vars_in_scope[qualname] = set()
        self._seed_params(qualname, node.args)

        parent_id = self._get_node_id(self.current_scope[-2])
        func_id = self._get_node_id(qualname)
        self._add_edge(parent_id, func_id, REL_CONTAINS)

        for stmt in node.body:
            self.visit(stmt)

        self.current_scope.pop()
        self.current_func = None

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                var = target.id
                scope = self.current_scope[-1] if self.current_scope else None
                if scope:
                    self.vars_in_scope.setdefault(scope, set()).add(var)

                # READS from value
                reads = self._extract_reads(node.value)
                for r in reads:
                    self._add_var_edge(r, REL_READS, evidence=node)

                # WRITES to target
                self._add_var_edge(var, REL_WRITES, evidence=node)

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if isinstance(node.value, ast.Name):
            obj = node.value.id
            attr = node.attr
            self._add_var_edge(obj, REL_ATTR_ACCESS, target=attr, evidence=node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Assume you already have CALLS logic; add READS from args/kwargs
        for arg in node.args:
            reads = self._extract_reads(arg)
            for r in reads:
                self._add_var_edge(r, REL_READS, evidence=node)

        for kw in node.keywords:
            if kw.value:
                reads = self._extract_reads(kw.value)
                for r in reads:
                    self._add_var_edge(r, REL_READS, evidence=node)

        self.generic_visit(node)

    # Add more visitors as needed (e.g. visit_If for DEPENDS_ON stubs)

    def finalize(self):
        """Return collected nodes & edges for DB insertion"""
        return self.nodes, self.edges
