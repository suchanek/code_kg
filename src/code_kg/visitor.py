import ast
from typing import Dict, List, Optional, Set, Tuple

# Relation types (add to your constants or use strings directly)
REL_CALLS      = "CALLS"
REL_CONTAINS   = "CONTAINS"
REL_READS      = "READS"
REL_WRITES     = "WRITES"
REL_ATTR_ACCESS= "ATTR_ACCESS"
REL_DEPENDS_ON = "DEPENDS_ON"  # placeholder for future control-flow

class CodeKGVisitor(ast.NodeVisitor):
    def __init__(self, module_id: str, file_path: str):
        self.module_id = module_id
        self.file_path = file_path
        self.current_scope: List[str] = []           # qualnames stack
        self.current_func: Optional[str] = None
        self.vars_in_scope: Dict[str, Set[str]] = {}  # scope → local vars set
        self.edges: List[Tuple[str, str, str, Optional[Dict]]] = []  # (src_id, tgt_id, rel, evidence)
        self.nodes: Dict[str, Dict] = {}  # id → node props (your existing)

    def _qualname(self, name: str) -> str:
        """Build qualified name, e.g. module.class.method"""
        if self.current_scope:
            return ".".join(self.current_scope + [name])
        return name

    def _get_node_id(self, qualname: str) -> str:
        """Your logic to get/create node id from qualname"""
        # Placeholder: implement or use your existing method
        node_id = qualname  # simplify for example; replace with hash or db insert
        if qualname not in self.nodes:
            self.nodes[node_id] = {"qualname": qualname, "kind": "unknown", "file": self.file_path}
        return node_id

    def _add_edge(self, src_id: str, tgt_id: str, rel: str, evidence: Optional[ast.AST] = None):
        ev = {"lineno": evidence.lineno if evidence else None,
              "file": self.file_path}
        self.edges.append((src_id, tgt_id, rel, ev))

    def _extract_reads(self, expr: ast.AST) -> Set[str]:
        """Collect variable names that are loaded (READS)"""
        reads = set()
        for sub in ast.walk(expr):
            if (isinstance(sub, ast.Name) and
                isinstance(sub.ctx, (ast.Load, ast.Del))):  # Del can be read-like
                reads.add(sub.id)
        return reads

    def _add_var_edge(self, var_name: str, rel: str, target: Optional[str] = None, evidence: Optional[ast.AST] = None):
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
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_ClassDef(self, node: ast.ClassDef):
        qualname = self._qualname(node.name)
        self.current_scope.append(qualname)
        parent_id = self._get_node_id(self.current_scope[-2])
        class_id = self._get_node_id(qualname)
        self._add_edge(parent_id, class_id, REL_CONTAINS)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        qualname = self._qualname(node.name)
        self.current_scope.append(qualname)
        self.current_func = qualname
        self.vars_in_scope[qualname] = set()

        parent_id = self._get_node_id(self.current_scope[-2])
        func_id = self._get_node_id(qualname)
        self._add_edge(parent_id, func_id, REL_CONTAINS)

        self.generic_visit(node)
        self.current_scope.pop()
        self.current_func = None

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                var = target.id
                scope = self.current_scope[-1] if self.current_scope else None
                if scope:
                    self.vars_in_scope[scope].add(var)

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
            scope = self.current_scope[-1]
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
        