"""Selector-to-SQL compiler tests.

Organized from atoms to molecules:
  Level 1: Type selectors (file, tool, mode)
  Level 2: ID selectors (file#README.md, tool#Bash)
  Level 3: Attribute selectors ([path="..."], [path^="..."])
  Level 4: Class selectors (mode.implement, mode.implement.tdd)
  Levels 5-8: see Task 5
"""
from __future__ import annotations

from tests.test_compilers_sql.conftest import parse_selector, parse_view, query_ids
from umwelt.compilers.sql.compiler import compile_selector, compile_view
from umwelt.compilers.sql.dialects import SQLiteDialect


DIALECT = SQLiteDialect()


# ============================================================================
# Level 1: Bare type selectors
# ============================================================================

class TestTypeSelectors:
    def test_bare_file_matches_all_files(self, populated_db):
        sql = compile_selector(parse_selector("file"), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 3, 4, 5}

    def test_bare_tool_matches_all_tools(self, populated_db):
        sql = compile_selector(parse_selector("tool"), DIALECT)
        assert query_ids(populated_db, sql) == {40, 41, 42, 43, 44, 45, 46}

    def test_bare_mode_matches_all_modes(self, populated_db):
        sql = compile_selector(parse_selector("mode"), DIALECT)
        assert query_ids(populated_db, sql) == {50, 51, 52, 53, 54}

    def test_bare_resource_matches_all_resources(self, populated_db):
        sql = compile_selector(parse_selector("resource"), DIALECT)
        assert query_ids(populated_db, sql) == {20, 21}

    def test_type_selector_excludes_other_types(self, populated_db):
        sql = compile_selector(parse_selector("tool"), DIALECT)
        ids = query_ids(populated_db, sql)
        assert all(40 <= i <= 46 for i in ids)


# ============================================================================
# Level 2: ID selectors
# ============================================================================

class TestIDSelectors:
    def test_file_with_id(self, populated_db):
        sql = compile_selector(parse_selector("file#README.md"), DIALECT)
        assert query_ids(populated_db, sql) == {4}

    def test_tool_with_id(self, populated_db):
        sql = compile_selector(parse_selector("tool#Bash"), DIALECT)
        assert query_ids(populated_db, sql) == {42}

    def test_principal_with_id(self, populated_db):
        sql = compile_selector(parse_selector("principal#Teague"), DIALECT)
        assert query_ids(populated_db, sql) == {60}

    def test_nonexistent_id_matches_nothing(self, populated_db):
        sql = compile_selector(parse_selector("tool#NonExistent"), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 3: Attribute selectors
# ============================================================================

class TestAttributeSelectors:
    def test_exact_match(self, populated_db):
        sql = compile_selector(parse_selector('file[path="src/auth.py"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1}

    def test_prefix_match(self, populated_db):
        sql = compile_selector(parse_selector('file[path^="src/"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 5}

    def test_suffix_match(self, populated_db):
        sql = compile_selector(parse_selector('file[path$=".py"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 3}

    def test_contains_match(self, populated_db):
        sql = compile_selector(parse_selector('file[path*="auth"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 3}

    def test_multiple_attributes_conjoin(self, populated_db):
        sql = compile_selector(parse_selector('file[path^="src/"][language="python"]'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2}

    def test_attribute_on_tool(self, populated_db):
        sql = compile_selector(parse_selector('tool[altitude="os"]'), DIALECT)
        assert query_ids(populated_db, sql) == {40, 41, 42, 43, 45, 46}

    def test_resource_kind_attribute(self, populated_db):
        sql = compile_selector(parse_selector('resource[kind="memory"]'), DIALECT)
        assert query_ids(populated_db, sql) == {20}


# ============================================================================
# Level 4: Class selectors
# ============================================================================

class TestClassSelectors:
    def test_single_class(self, populated_db):
        sql = compile_selector(parse_selector("mode.implement"), DIALECT)
        assert query_ids(populated_db, sql) == {50, 53}

    def test_class_excludes_non_matching(self, populated_db):
        sql = compile_selector(parse_selector("mode.explore"), DIALECT)
        assert query_ids(populated_db, sql) == {52}

    def test_multiple_classes_must_all_match(self, populated_db):
        sql = compile_selector(parse_selector("mode.implement.tdd"), DIALECT)
        assert query_ids(populated_db, sql) == {53}

    def test_class_not_present_matches_nothing(self, populated_db):
        sql = compile_selector(parse_selector("mode.deploy"), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 5: Compound selectors — cross-axis
# ============================================================================

class TestCompoundSelectors:
    def test_two_axis_mode_tool(self, populated_db):
        sql = compile_selector(parse_selector("mode.implement tool"), DIALECT)
        assert query_ids(populated_db, sql) == {40, 41, 42, 43, 44, 45, 46}

    def test_two_axis_mode_tool_with_attr(self, populated_db):
        sql = compile_selector(parse_selector('mode.implement tool[name="Bash"]'), DIALECT)
        assert query_ids(populated_db, sql) == {42}

    def test_context_qualifier_nonexistent_mode_produces_nothing(self, populated_db):
        sql = compile_selector(parse_selector("mode.deploy tool"), DIALECT)
        assert query_ids(populated_db, sql) == set()

    def test_two_axis_principal_tool(self, populated_db):
        sql = compile_selector(parse_selector("principal#Teague tool"), DIALECT)
        assert query_ids(populated_db, sql) == {40, 41, 42, 43, 44, 45, 46}

    def test_two_axis_principal_nonexistent(self, populated_db):
        sql = compile_selector(parse_selector("principal#Nobody tool"), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 6: Three-axis compounds
# ============================================================================

class TestThreeAxisCompounds:
    def test_principal_mode_tool(self, populated_db):
        sql = compile_selector(parse_selector('principal#Teague mode.implement tool[name="Bash"]'), DIALECT)
        assert query_ids(populated_db, sql) == {42}

    def test_three_axis_one_qualifier_fails(self, populated_db):
        sql = compile_selector(parse_selector('principal#Nobody mode.implement tool[name="Bash"]'), DIALECT)
        assert query_ids(populated_db, sql) == set()

    def test_three_axis_different_qualifier_fails(self, populated_db):
        sql = compile_selector(parse_selector('principal#Teague mode.deploy tool[name="Bash"]'), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 7: Structural descendants
# ============================================================================

class TestStructuralDescendants:
    def test_dir_file_descendant(self, populated_db):
        sql = compile_selector(parse_selector('dir[name="src"] file'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 5}

    def test_dir_file_other_dir(self, populated_db):
        sql = compile_selector(parse_selector('dir[name="tests"] file'), DIALECT)
        assert query_ids(populated_db, sql) == {3}

    def test_dir_file_nonexistent_dir(self, populated_db):
        sql = compile_selector(parse_selector('dir[name="lib"] file'), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# Level 8: Pseudo-classes
# ============================================================================

class TestPseudoClasses:
    def test_glob_pseudo(self, populated_db):
        sql = compile_selector(parse_selector('file:glob("src/*.py")'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2}

    def test_glob_recursive(self, populated_db):
        sql = compile_selector(parse_selector('file:glob("**/*.py")'), DIALECT)
        assert query_ids(populated_db, sql) == {1, 2, 3}

    def test_glob_no_match(self, populated_db):
        sql = compile_selector(parse_selector('file:glob("*.rs")'), DIALECT)
        assert query_ids(populated_db, sql) == set()


# ============================================================================
# compile_view — full View AST to cascade candidates
# ============================================================================

class TestCompileView:
    def test_compile_view_populates_candidates(self, populated_db):
        view = parse_view('file[path^="src/"] { editable: true; }')
        compile_view(populated_db, view, DIALECT, source_file="test.umw")
        count = populated_db.execute("SELECT COUNT(*) FROM cascade_candidates").fetchone()[0]
        assert count > 0

    def test_compile_view_creates_resolution_views(self, populated_db):
        view = parse_view('file { editable: false; }')
        compile_view(populated_db, view, DIALECT, source_file="test.umw")
        row = populated_db.execute("SELECT COUNT(*) FROM resolved_properties").fetchone()
        assert row[0] > 0

    def test_compile_view_comparison_inference(self, populated_db):
        view = parse_view('tool { max-level: 5; }')
        compile_view(populated_db, view, DIALECT, source_file="test.umw")
        row = populated_db.execute(
            "SELECT comparison FROM cascade_candidates WHERE property_name = 'max-level'"
        ).fetchone()
        assert row[0] == "<="

    def test_compile_view_pattern_comparison(self, populated_db):
        view = parse_view('tool[name="Bash"] { allow-pattern: "git *"; }')
        compile_view(populated_db, view, DIALECT, source_file="test.umw")
        row = populated_db.execute(
            "SELECT comparison FROM cascade_candidates WHERE property_name = 'allow-pattern'"
        ).fetchone()
        assert row[0] == "pattern-in"
