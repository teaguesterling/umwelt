"""Pressure tests: CI/CD Pipeline Policy domain.

Novel domain that exercises:
- World-taxon entities (dir, exec, env, network, resource) through PolicyEngine
- These entities are registered in vocabulary but barely tested at policy level
- Network + env restrictions together
- Resource budget constraints
- Fixed constraints on infrastructure safety
- Cross-type queries (tools + dirs + execs in one engine)
- Mode-gated rules for CI pipeline stages
- Cross-axis specificity behavior
"""
from __future__ import annotations

import pytest

from umwelt.errors import PolicyDenied
from umwelt.policy import PolicyEngine


@pytest.fixture
def cicd_engine(tmp_path):
    """CI/CD pipeline engine with dirs, execs, envs, networks, resources."""
    world = tmp_path / "cicd.world.yml"
    world.write_text("""\
entities:
  - type: dir
    id: src
    classes: [source]
    attributes:
      path: src/
  - type: dir
    id: tests
    classes: [source, test]
    attributes:
      path: tests/
  - type: dir
    id: dist
    classes: [output, artifact]
    attributes:
      path: dist/
  - type: dir
    id: node_modules
    classes: [vendor, large]
    attributes:
      path: node_modules/
  - type: dir
    id: secrets
    classes: [sensitive]
    attributes:
      path: .secrets/

  - type: exec
    id: node
    classes: [runtime]
    attributes:
      path: /usr/local/bin/node
  - type: exec
    id: npm
    classes: [package-manager, runtime]
    attributes:
      path: /usr/local/bin/npm
  - type: exec
    id: git
    classes: [vcs]
    attributes:
      path: /usr/bin/git
  - type: exec
    id: bash-exec
    classes: [shell]
    attributes:
      path: /bin/bash
  - type: exec
    id: curl
    classes: [network-tool]
    attributes:
      path: /usr/bin/curl
  - type: exec
    id: docker
    classes: [infrastructure, dangerous]
    attributes:
      path: /usr/bin/docker

  - type: env
    id: NODE_ENV
    classes: [runtime]
  - type: env
    id: CI
    classes: [runtime]
  - type: env
    id: AWS_ACCESS_KEY_ID
    classes: [secret, cloud]
  - type: env
    id: AWS_SECRET_ACCESS_KEY
    classes: [secret, cloud]
  - type: env
    id: DATABASE_URL
    classes: [secret, database]
  - type: env
    id: NPM_TOKEN
    classes: [secret, registry]

  - type: network
    id: npmjs
    classes: [registry]
    attributes:
      host: registry.npmjs.org
  - type: network
    id: github
    classes: [vcs-host]
    attributes:
      host: github.com
  - type: network
    id: docker-hub
    classes: [registry, infrastructure]
    attributes:
      host: hub.docker.com
  - type: network
    id: production-api
    classes: [production, sensitive]
    attributes:
      host: api.example.com

  - type: resource
    id: ci-budget
    attributes:
      name: ci-budget

  - type: mode
    id: build
  - type: mode
    id: test
  - type: mode
    id: deploy
  - type: mode
    id: lint

  - type: tool
    id: Read
    classes: [safe]
  - type: tool
    id: Edit
    classes: [safe, mutating]
  - type: tool
    id: Bash
    classes: [dangerous]
""")
    style = tmp_path / "cicd.umw"
    style.write_text("""\
/* ---- Directory policy ---- */
dir { visible: true; editable: false; }
dir.source { editable: true; }
dir.output { editable: true; }
dir.vendor { visible: true; editable: false; }
dir.sensitive { visible: false; editable: false; }

/* ---- Executable policy ---- */
exec { search-path: /bin:/usr/bin; }
exec.runtime { path: /usr/local/bin/node; }
exec.shell { path: /bin/bash; search-path: /bin:/usr/bin:/usr/local/bin; }
exec.dangerous { path: /usr/bin/false; }
exec#docker { search-path: /usr/bin; }

/* ---- Environment variables ---- */
env { allow: false; }
env.runtime { allow: true; }
env.secret { allow: false; }

/* ---- Network policy ---- */
network { allow: false; }
network.registry { allow: true; }
network.vcs-host { allow: true; }
network.production { allow: false; }

/* ---- Resource budgets ---- */
resource { memory: 1GB; wall-time: 10m; cpu-time: 5m; }
resource#ci-budget { memory: 2GB; wall-time: 30m; }

/* ---- Tool policy ---- */
tool { allow: true; visible: true; }
tool.dangerous { max-level: 3; }

/* ---- Mode-gated rules ---- */

mode#build dir.source { editable: true; }
mode#build dir.output { editable: true; }
mode#build env.runtime { allow: true; }
mode#build network.registry { allow: true; }

mode#test dir { editable: false; }
mode#test dir.test { editable: true; }
mode#test env.runtime { allow: true; }
mode#test network { allow: false; }

mode#deploy dir { visible: true; editable: false; }
mode#deploy exec.dangerous { path: /usr/bin/docker; }
mode#deploy env.cloud { allow: true; }
mode#deploy network.infrastructure { allow: true; }

mode#lint dir { editable: false; }
mode#lint tool.dangerous { allow: false; }
mode#lint resource { memory: 512MB; wall-time: 5m; }
""")
    return PolicyEngine.from_files(world=world, stylesheet=style)


@pytest.fixture
def base_cicd_engine(tmp_path):
    """CI/CD engine with no mode rules — pure single-axis cascade."""
    world = tmp_path / "cicd.world.yml"
    world.write_text("""\
entities:
  - type: dir
    id: src
    classes: [source]
  - type: dir
    id: secrets
    classes: [sensitive]
  - type: dir
    id: node_modules
    classes: [vendor]
  - type: exec
    id: docker
    classes: [infrastructure, dangerous]
  - type: exec
    id: node
    classes: [runtime]
  - type: exec
    id: bash-exec
    classes: [shell]
  - type: env
    id: NODE_ENV
    classes: [runtime]
  - type: env
    id: AWS_ACCESS_KEY_ID
    classes: [secret, cloud]
  - type: network
    id: npmjs
    classes: [registry]
  - type: network
    id: github
    classes: [vcs-host]
  - type: network
    id: production-api
    classes: [production]
  - type: resource
    id: ci-budget
""")
    style = tmp_path / "cicd.umw"
    style.write_text("""\
dir { visible: true; editable: false; }
dir.source { editable: true; }
dir.sensitive { visible: false; editable: false; }

exec { search-path: /bin:/usr/bin; }
exec.runtime { path: /usr/local/bin/node; }
exec.shell { path: /bin/bash; search-path: /bin:/usr/bin:/usr/local/bin; }
exec.dangerous { path: /usr/bin/false; }
exec#docker { search-path: /usr/bin; }

env { allow: false; }
env.runtime { allow: true; }

network { allow: false; }
network.registry { allow: true; }
network.vcs-host { allow: true; }
network.production { allow: false; }

resource { memory: 1GB; wall-time: 10m; }
resource#ci-budget { memory: 2GB; wall-time: 30m; }
""")
    return PolicyEngine.from_files(world=world, stylesheet=style)


@pytest.fixture
def cicd_engine_with_fixed(tmp_path):
    """CI/CD engine with fixed constraints on sensitive dirs and secrets."""
    world = tmp_path / "cicd.world.yml"
    world.write_text("""\
entities:
  - type: dir
    id: src
    classes: [source]
  - type: dir
    id: secrets
    classes: [sensitive]
  - type: env
    id: AWS_ACCESS_KEY_ID
    classes: [secret]
  - type: env
    id: NODE_ENV
    classes: [runtime]
  - type: network
    id: production-api
    classes: [production]
fixed:
  "dir#secrets":
    editable: "false"
    visible: "false"
  "env#AWS_ACCESS_KEY_ID":
    allow: "false"
  "network#production-api":
    allow: "false"
""")
    style = tmp_path / "cicd.umw"
    style.write_text("""\
dir { visible: true; editable: true; }
env { allow: true; }
network { allow: true; }
""")
    return PolicyEngine.from_files(world=world, stylesheet=style)


class TestDirectoryPolicy:
    """Test directory entity resolution through PolicyEngine — no mode interference."""

    def test_source_dirs_editable(self, base_cicd_engine):
        assert base_cicd_engine.check(type="dir", id="src", editable="true")

    def test_vendor_dirs_readonly(self, base_cicd_engine):
        # No .vendor rule, but dir base is editable: false
        assert base_cicd_engine.check(type="dir", id="node_modules", editable="false")

    def test_sensitive_dirs_invisible(self, base_cicd_engine):
        assert base_cicd_engine.check(type="dir", id="secrets", visible="false")

    def test_sensitive_dirs_not_editable(self, base_cicd_engine):
        assert base_cicd_engine.check(type="dir", id="secrets", editable="false")


class TestExecPolicy:
    """Test executable entity resolution — registered but barely tested before."""

    def test_runtime_exec_path(self, base_cicd_engine):
        val = base_cicd_engine.resolve(type="exec", id="node", property="path")
        assert val == "/usr/local/bin/node"

    def test_shell_search_path(self, base_cicd_engine):
        val = base_cicd_engine.resolve(type="exec", id="bash-exec", property="search-path")
        assert val == "/bin:/usr/bin:/usr/local/bin"

    def test_dangerous_exec_blocked(self, base_cicd_engine):
        val = base_cicd_engine.resolve(type="exec", id="docker", property="path")
        assert val == "/usr/bin/false"

    def test_docker_search_path(self, base_cicd_engine):
        val = base_cicd_engine.resolve(type="exec", id="docker", property="search-path")
        assert val == "/usr/bin"

    def test_all_execs_resolved(self, base_cicd_engine):
        execs = base_cicd_engine.resolve_all(type="exec")
        assert len(execs) == 3


class TestEnvPolicy:
    """Test environment variable restrictions."""

    def test_runtime_env_allowed(self, base_cicd_engine):
        assert base_cicd_engine.check(type="env", id="NODE_ENV", allow="true")

    def test_secret_env_denied(self, base_cicd_engine):
        assert base_cicd_engine.check(type="env", id="AWS_ACCESS_KEY_ID", allow="false")

    def test_require_blocks_secret_env(self, base_cicd_engine):
        with pytest.raises(PolicyDenied):
            base_cicd_engine.require(type="env", id="AWS_ACCESS_KEY_ID", allow="true")


class TestNetworkPolicy:
    """Test network endpoint restrictions."""

    def test_registry_allowed(self, base_cicd_engine):
        assert base_cicd_engine.check(type="network", id="npmjs", allow="true")

    def test_vcs_allowed(self, base_cicd_engine):
        assert base_cicd_engine.check(type="network", id="github", allow="true")

    def test_production_denied(self, base_cicd_engine):
        assert base_cicd_engine.check(type="network", id="production-api", allow="false")


class TestResourceBudgets:
    """Test resource entity resolution (no mode rules → ID selector wins)."""

    def test_ci_budget_memory(self, base_cicd_engine):
        val = base_cicd_engine.resolve(type="resource", id="ci-budget", property="memory")
        assert val == "2GB"

    def test_ci_budget_wall_time(self, base_cicd_engine):
        val = base_cicd_engine.resolve(type="resource", id="ci-budget", property="wall-time")
        assert val == "30m"


class TestCrossTypeQueries:
    """Test that tools, dirs, execs, etc. coexist in the same compiled database."""

    def test_all_entity_types_present(self, cicd_engine):
        for type_name, expected_count in [
            ("dir", 5), ("exec", 6), ("env", 6),
            ("network", 4), ("resource", 1), ("tool", 3), ("mode", 4),
        ]:
            entities = cicd_engine.resolve_all(type=type_name)
            assert len(entities) == expected_count, \
                f"Expected {expected_count} {type_name} entities, got {len(entities)}"

    def test_types_dont_interfere(self, cicd_engine):
        tools = cicd_engine.resolve_all(type="tool")
        dirs = cicd_engine.resolve_all(type="dir")
        execs = cicd_engine.resolve_all(type="exec")
        tool_ids = {t["entity_id"] for t in tools}
        dir_ids = {d["entity_id"] for d in dirs}
        exec_ids = {e["entity_id"] for e in execs}
        assert tool_ids & dir_ids == set()
        assert tool_ids & exec_ids == set()


class TestCrossAxisInModes:
    """Test that cross-axis (mode-gated) rules dominate in unfiltered cascade.

    Without context filtering, mode-gated rules have higher cross-axis specificity
    and can dominate single-axis rules. These tests verify this behavior and show
    how context filtering restores predictable per-stage behavior.
    """

    def test_mode_lint_dominates_resource_without_context(self, cicd_engine):
        # mode#lint resource { memory: 512MB } has cross-axis specificity
        # → beats resource#ci-budget { memory: 2GB } (single-axis ID)
        val = cicd_engine.resolve(type="resource", id="ci-budget", property="memory")
        assert val == "512MB"

    def test_context_restores_id_selector_for_resource(self, cicd_engine):
        # With mode=build context, lint rules are excluded
        # → resource#ci-budget { memory: 2GB } wins
        val = cicd_engine.resolve(
            type="resource", id="ci-budget", property="memory",
            context={"mode": "build"},
        )
        assert val == "2GB"


class TestPipelineStagesModes:
    """Test mode-gated rules for CI/CD pipeline stages with explicit context."""

    def test_build_stage_source_editable(self, cicd_engine):
        val = cicd_engine.resolve(
            type="dir", id="src", property="editable",
            context={"mode": "build"},
        )
        assert val == "true"

    def test_build_stage_registry_allowed(self, cicd_engine):
        val = cicd_engine.resolve(
            type="network", id="npmjs", property="allow",
            context={"mode": "build"},
        )
        assert val == "true"

    def test_test_stage_source_readonly(self, cicd_engine):
        val = cicd_engine.resolve(
            type="dir", id="src", property="editable",
            context={"mode": "test"},
        )
        assert val == "false"

    def test_test_stage_test_dir_editable(self, cicd_engine):
        val = cicd_engine.resolve(
            type="dir", id="tests", property="editable",
            context={"mode": "test"},
        )
        assert val == "true"

    def test_test_stage_network_blocked(self, cicd_engine):
        val = cicd_engine.resolve(
            type="network", id="npmjs", property="allow",
            context={"mode": "test"},
        )
        assert val == "false"

    def test_deploy_stage_enables_docker(self, cicd_engine):
        val = cicd_engine.resolve(
            type="exec", id="docker", property="path",
            context={"mode": "deploy"},
        )
        assert val == "/usr/bin/docker"

    def test_deploy_stage_allows_cloud_secrets(self, cicd_engine):
        val = cicd_engine.resolve(
            type="env", id="AWS_ACCESS_KEY_ID", property="allow",
            context={"mode": "deploy"},
        )
        assert val == "true"

    def test_deploy_stage_still_blocks_db_secrets(self, cicd_engine):
        val = cicd_engine.resolve(
            type="env", id="DATABASE_URL", property="allow",
            context={"mode": "deploy"},
        )
        assert val == "false"

    def test_lint_stage_restricts_resources(self, cicd_engine):
        val = cicd_engine.resolve(
            type="resource", id="ci-budget", property="memory",
            context={"mode": "lint"},
        )
        assert val == "512MB"

    def test_lint_stage_blocks_dangerous_tools(self, cicd_engine):
        val = cicd_engine.resolve(
            type="tool", id="Bash", property="allow",
            context={"mode": "lint"},
        )
        assert val == "false"


class TestFixedConstraintsInfra:
    """Test fixed constraints for infrastructure safety invariants."""

    def test_fixed_blocks_sensitive_dir_visibility(self, cicd_engine_with_fixed):
        val = cicd_engine_with_fixed.resolve(type="dir", id="secrets", property="visible")
        assert val == "false"

    def test_fixed_blocks_sensitive_dir_editing(self, cicd_engine_with_fixed):
        val = cicd_engine_with_fixed.resolve(type="dir", id="secrets", property="editable")
        assert val == "false"

    def test_fixed_blocks_secret_env(self, cicd_engine_with_fixed):
        val = cicd_engine_with_fixed.resolve(type="env", id="AWS_ACCESS_KEY_ID", property="allow")
        assert val == "false"

    def test_fixed_blocks_production_network(self, cicd_engine_with_fixed):
        val = cicd_engine_with_fixed.resolve(type="network", id="production-api", property="allow")
        assert val == "false"

    def test_fixed_doesnt_affect_normal_dir(self, cicd_engine_with_fixed):
        val = cicd_engine_with_fixed.resolve(type="dir", id="src", property="editable")
        assert val == "true"

    def test_fixed_doesnt_affect_runtime_env(self, cicd_engine_with_fixed):
        val = cicd_engine_with_fixed.resolve(type="env", id="NODE_ENV", property="allow")
        assert val == "true"


class TestTraceAcrossTypes:
    """Test trace debugging with different entity types."""

    def test_trace_dir_editable(self, base_cicd_engine):
        result = base_cicd_engine.trace(type="dir", id="src", property="editable")
        assert result.value == "true"
        assert len(result.candidates) >= 2

    def test_trace_env_with_mode(self, cicd_engine):
        result = cicd_engine.trace(
            type="env", id="AWS_ACCESS_KEY_ID", property="allow",
            context={"mode": "deploy"},
        )
        assert result.value == "true"
        assert len(result.candidates) >= 2


class TestExtendForPipelineVariants:
    """Test extend() for pipeline variant configurations."""

    def test_staging_variant(self, base_cicd_engine):
        staging = base_cicd_engine.extend(
            entities=[
                {"type": "network", "id": "staging-api", "classes": ["staging"]},
            ],
            stylesheet="network.staging { allow: true; }",
        )
        val = staging.resolve(type="network", id="staging-api", property="allow")
        assert val == "true"
        assert staging.check(type="network", id="production-api", allow="false")

    def test_extended_pipeline_adds_exec(self, base_cicd_engine):
        extended = base_cicd_engine.extend(
            entities=[
                {"type": "exec", "id": "python3", "classes": ["runtime"]},
            ],
            stylesheet="exec.runtime { path: /usr/local/bin/python3; }",
        )
        execs = extended.resolve_all(type="exec")
        assert len(execs) == 4  # 3 base + 1 new
        val = extended.resolve(type="exec", id="python3", property="path")
        assert val == "/usr/local/bin/python3"


class TestSaveReloadCrossType:
    """Test persistence with multiple entity types."""

    def test_round_trip_preserves_all_types(self, base_cicd_engine, tmp_path):
        db_path = tmp_path / "cicd.db"
        base_cicd_engine.save(str(db_path))

        reloaded = PolicyEngine.from_db(str(db_path))
        assert len(reloaded.resolve_all(type="dir")) == 3
        assert len(reloaded.resolve_all(type="exec")) == 3
        assert len(reloaded.resolve_all(type="env")) == 2
        assert len(reloaded.resolve_all(type="network")) == 3
        assert reloaded.check(type="dir", id="secrets", visible="false")
        assert reloaded.check(type="env", id="AWS_ACCESS_KEY_ID", allow="false")


class TestLintCrossType:
    """Test lint on a policy spanning multiple entity types."""

    def test_lint_runs_without_error(self, cicd_engine):
        warnings = cicd_engine.lint()
        assert isinstance(warnings, list)
