"""Pressure tests: Data Pipeline Governance domain.

Novel domain that exercises:
- Custom entity types (dataset, transform, sink) registered via plugin-style vocabulary
- Programmatic PolicyEngine constructor with custom vocabulary
- Class-based specificity for PII classification
- extend() for per-team policy forks
- Multi-property resolution on non-tool entities
- Context qualifiers with custom entity types
- Save/reload round-trip with custom types
"""
from __future__ import annotations

import pytest

from umwelt.errors import PolicyDenied
from umwelt.policy import PolicyEngine
from umwelt.registry import AttrSchema, register_entity, register_property, register_taxon
from umwelt.registry.taxa import registry_scope


@pytest.fixture(autouse=True)
def _pipeline_vocabulary():
    """Register a data pipeline vocabulary — mimics what a third-party plugin would do."""
    with registry_scope():
        register_taxon(name="data", description="Data pipeline entities")
        register_entity(
            taxon="data", name="dataset",
            attributes={
                "name": AttrSchema(type=str, description="Dataset name"),
                "owner": AttrSchema(type=str, description="Owning team"),
                "format": AttrSchema(type=str, description="Storage format"),
            },
            description="A named dataset.",
        )
        register_entity(
            taxon="data", name="transform",
            attributes={
                "name": AttrSchema(type=str, description="Transform name"),
                "runtime": AttrSchema(type=str, description="Execution runtime"),
            },
            description="A data transformation step.",
        )
        register_entity(
            taxon="data", name="sink",
            attributes={
                "name": AttrSchema(type=str, description="Sink name"),
                "region": AttrSchema(type=str, description="Deployment region"),
            },
            description="An output destination.",
        )
        register_property(taxon="data", entity="dataset", name="retention", value_type=str,
                          description="Data retention period.")
        register_property(taxon="data", entity="dataset", name="access", value_type=str,
                          description="Access level: read, write, restricted, denied.")
        register_property(taxon="data", entity="dataset", name="visible", value_type=bool,
                          description="Whether the dataset is visible.")
        register_property(taxon="data", entity="dataset", name="audit-required", value_type=bool,
                          description="Whether audit logging is required.")
        register_property(taxon="data", entity="dataset", name="audit-trail", value_type=str,
                          description="Audit trail level.")
        register_property(taxon="data", entity="transform", name="allow", value_type=bool,
                          description="Whether the transform is permitted.")
        register_property(taxon="data", entity="transform", name="cost-tier", value_type=str,
                          description="Cost classification.")
        register_property(taxon="data", entity="transform", name="audit-trail", value_type=str,
                          description="Audit trail level.")
        register_property(taxon="data", entity="sink", name="allow", value_type=bool,
                          description="Whether the sink is permitted.")
        register_property(taxon="data", entity="sink", name="encryption", value_type=str,
                          description="Encryption requirement.")
        register_property(taxon="data", entity="sink", name="pii-check", value_type=str,
                          description="PII check level.")
        yield


def _build_pipeline_entities():
    return [
        {"type": "dataset", "id": "user-profiles", "classes": ["pii", "sensitive"],
         "attributes": {"owner": "identity-team", "format": "parquet"}},
        {"type": "dataset", "id": "click-events", "classes": ["behavioral"],
         "attributes": {"owner": "analytics-team", "format": "avro"}},
        {"type": "dataset", "id": "anonymized-clicks", "classes": ["behavioral", "anonymized"],
         "attributes": {"owner": "analytics-team", "format": "parquet"}},
        {"type": "dataset", "id": "payment-records", "classes": ["pii", "financial", "sensitive"],
         "attributes": {"owner": "billing-team", "format": "parquet"}},
        {"type": "transform", "id": "anonymize", "classes": ["privacy"],
         "attributes": {"runtime": "spark"}},
        {"type": "transform", "id": "aggregate", "classes": ["analytics"],
         "attributes": {"runtime": "duckdb"}},
        {"type": "transform", "id": "enrich", "classes": ["ml"],
         "attributes": {"runtime": "spark"}},
        {"type": "sink", "id": "warehouse", "classes": ["internal"],
         "attributes": {"region": "us-east-1"}},
        {"type": "sink", "id": "public-api", "classes": ["external", "public"],
         "attributes": {"region": "us-east-1"}},
        {"type": "sink", "id": "partner-export", "classes": ["external"],
         "attributes": {"region": "eu-west-1"}},
        {"type": "mode", "id": "production"},
        {"type": "mode", "id": "development"},
        {"type": "mode", "id": "audit"},
        {"type": "principal", "id": "analytics-team"},
        {"type": "principal", "id": "billing-team"},
    ]


_BASE_STYLESHEET = """\
dataset { visible: true; retention: 90d; access: read; }
dataset.pii { retention: 30d; access: restricted; }
dataset.sensitive { retention: 14d; }
dataset.financial { retention: 7y; }
dataset#payment-records { audit-required: true; }

transform { allow: true; cost-tier: standard; }
transform.privacy { cost-tier: premium; audit-trail: required; }
transform.ml { cost-tier: premium; }

sink { allow: true; encryption: required; }
sink.external { allow: false; encryption: aes-256; }
sink.public { pii-check: mandatory; }
"""

_MODE_STYLESHEET = """\
mode#production dataset { access: read; }
mode#production sink.external { allow: false; }

mode#development dataset { access: write; retention: 1d; }
mode#development sink { allow: true; }
mode#development sink.external { allow: true; }

mode#audit dataset { visible: true; access: read; audit-trail: full; }
mode#audit transform { allow: false; }
"""

_PRINCIPAL_STYLESHEET = """\
principal#billing-team dataset.financial { access: write; }
principal#analytics-team dataset.behavioral { access: write; }
"""


@pytest.fixture
def pipeline_engine():
    """Data pipeline engine with all rules including mode/principal."""
    engine = PolicyEngine()
    engine.add_entities(_build_pipeline_entities())
    engine.add_stylesheet(_BASE_STYLESHEET)
    engine.add_stylesheet(_MODE_STYLESHEET)
    engine.add_stylesheet(_PRINCIPAL_STYLESHEET)
    return engine


@pytest.fixture
def base_pipeline_engine():
    """Pipeline engine with only base rules (no mode/principal gating)."""
    engine = PolicyEngine()
    engine.add_entities(_build_pipeline_entities())
    engine.add_stylesheet(_BASE_STYLESHEET)
    return engine


class TestCustomEntityTypes:
    """Verify that custom vocabulary entity types work through PolicyEngine."""

    def test_dataset_type_resolves(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="dataset", id="click-events", property="retention")
        assert val == "90d"

    def test_transform_type_resolves(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="transform", id="aggregate", property="allow")
        assert val == "true"

    def test_sink_type_resolves(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="sink", id="warehouse", property="allow")
        assert val == "true"

    def test_unknown_entity_returns_none(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="dataset", id="nonexistent", property="retention")
        assert val is None


class TestDatasetCascade:
    """Test cascade resolution across dataset classification hierarchy."""

    def test_base_retention(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="dataset", id="click-events", property="retention")
        assert val == "90d"

    def test_pii_overrides_base(self, base_pipeline_engine):
        # user-profiles: [pii, sensitive] → .pii(30d), .sensitive(14d) same specificity, later wins
        val = base_pipeline_engine.resolve(type="dataset", id="user-profiles", property="retention")
        assert val == "14d"

    def test_financial_overrides_sensitive(self, base_pipeline_engine):
        # payment-records: [pii, financial, sensitive] → .financial(7y) is last class rule
        val = base_pipeline_engine.resolve(type="dataset", id="payment-records", property="retention")
        assert val == "7y"

    def test_behavioral_gets_base(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="dataset", id="anonymized-clicks", property="retention")
        assert val == "90d"

    def test_pii_access_restricted(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="dataset", id="user-profiles", property="access")
        assert val == "restricted"

    def test_nonpii_access_read(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="dataset", id="click-events", property="access")
        assert val == "read"

    def test_all_datasets_visible(self, base_pipeline_engine):
        datasets = base_pipeline_engine.resolve_all(type="dataset")
        for ds in datasets:
            assert ds["properties"].get("visible") == "true", f"{ds['entity_id']} not visible"

    def test_id_selector_audit_required(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="dataset", id="payment-records", property="audit-required")
        assert val == "true"

    def test_id_selector_doesnt_leak(self, base_pipeline_engine):
        val = base_pipeline_engine.resolve(type="dataset", id="user-profiles", property="audit-required")
        assert val is None


class TestTransformCascade:
    def test_base_allowed(self, base_pipeline_engine):
        assert base_pipeline_engine.check(type="transform", id="aggregate", allow="true")

    def test_privacy_premium_tier(self, base_pipeline_engine):
        assert base_pipeline_engine.resolve(type="transform", id="anonymize", property="cost-tier") == "premium"

    def test_analytics_standard_tier(self, base_pipeline_engine):
        assert base_pipeline_engine.resolve(type="transform", id="aggregate", property="cost-tier") == "standard"

    def test_privacy_audit_trail(self, base_pipeline_engine):
        assert base_pipeline_engine.resolve(type="transform", id="anonymize", property="audit-trail") == "required"

    def test_ml_premium_no_audit(self, base_pipeline_engine):
        assert base_pipeline_engine.resolve(type="transform", id="enrich", property="cost-tier") == "premium"
        assert base_pipeline_engine.resolve(type="transform", id="enrich", property="audit-trail") is None


class TestSinkCascade:
    def test_internal_allowed(self, base_pipeline_engine):
        assert base_pipeline_engine.check(type="sink", id="warehouse", allow="true")

    def test_external_denied(self, base_pipeline_engine):
        assert base_pipeline_engine.check(type="sink", id="partner-export", allow="false")

    def test_public_denied(self, base_pipeline_engine):
        assert base_pipeline_engine.check(type="sink", id="public-api", allow="false")

    def test_external_encryption_upgraded(self, base_pipeline_engine):
        assert base_pipeline_engine.resolve(type="sink", id="partner-export", property="encryption") == "aes-256"

    def test_internal_base_encryption(self, base_pipeline_engine):
        assert base_pipeline_engine.resolve(type="sink", id="warehouse", property="encryption") == "required"

    def test_public_pii_check(self, base_pipeline_engine):
        assert base_pipeline_engine.resolve(type="sink", id="public-api", property="pii-check") == "mandatory"


class TestModeContextFiltering:
    def test_development_allows_write(self, pipeline_engine):
        val = pipeline_engine.resolve(type="dataset", id="click-events", property="access",
                                      context={"mode": "development"})
        assert val == "write"

    def test_development_short_retention(self, pipeline_engine):
        val = pipeline_engine.resolve(type="dataset", id="click-events", property="retention",
                                      context={"mode": "development"})
        assert val == "1d"

    def test_development_allows_external_sink(self, pipeline_engine):
        val = pipeline_engine.resolve(type="sink", id="partner-export", property="allow",
                                      context={"mode": "development"})
        assert val == "true"

    def test_production_denies_external_sink(self, pipeline_engine):
        val = pipeline_engine.resolve(type="sink", id="partner-export", property="allow",
                                      context={"mode": "production"})
        assert val == "false"

    def test_audit_blocks_transforms(self, pipeline_engine):
        val = pipeline_engine.resolve(type="transform", id="anonymize", property="allow",
                                      context={"mode": "audit"})
        assert val == "false"

    def test_audit_full_audit_trail(self, pipeline_engine):
        val = pipeline_engine.resolve(type="dataset", id="click-events", property="audit-trail",
                                      context={"mode": "audit"})
        assert val == "full"

    def test_production_read_access(self, pipeline_engine):
        val = pipeline_engine.resolve(type="dataset", id="click-events", property="access",
                                      context={"mode": "production"})
        assert val == "read"


class TestPrincipalContextFiltering:
    def test_billing_team_writes_financial(self, pipeline_engine):
        val = pipeline_engine.resolve(type="dataset", id="payment-records", property="access",
                                      context=[("principal", "principal", "billing-team")])
        assert val == "write"

    def test_analytics_team_writes_behavioral(self, pipeline_engine):
        val = pipeline_engine.resolve(type="dataset", id="click-events", property="access",
                                      context=[("principal", "principal", "analytics-team")])
        assert val == "write"

    def test_analytics_team_cant_write_pii(self, pipeline_engine):
        val = pipeline_engine.resolve(type="dataset", id="user-profiles", property="access",
                                      context=[("principal", "principal", "analytics-team")])
        assert val == "restricted"


class TestMultiAxisContext:
    def test_billing_in_production(self, pipeline_engine):
        val = pipeline_engine.resolve(
            type="dataset", id="payment-records", property="access",
            context=[("state", "mode", "production"), ("principal", "principal", "billing-team")],
        )
        # principal#billing-team dataset.financial (cross-axis+class) > mode#production dataset (cross-axis+type)
        assert val == "write"

    def test_analytics_in_audit(self, pipeline_engine):
        val = pipeline_engine.resolve(
            type="transform", id="aggregate", property="allow",
            context=[("state", "mode", "audit"), ("principal", "principal", "analytics-team")],
        )
        assert val == "false"

    def test_analytics_in_development(self, pipeline_engine):
        val = pipeline_engine.resolve(
            type="dataset", id="click-events", property="access",
            context=[("state", "mode", "development"), ("principal", "principal", "analytics-team")],
        )
        assert val == "write"


class TestExtendForTeamOverrides:
    def test_extend_with_id_override(self, base_pipeline_engine):
        """ID selector in extended stylesheet beats class selector in base."""
        strict = base_pipeline_engine.extend(
            stylesheet="dataset#user-profiles { access: denied; }",
        )
        assert strict.resolve(type="dataset", id="user-profiles", property="access") == "denied"
        assert base_pipeline_engine.resolve(type="dataset", id="user-profiles", property="access") == "restricted"

    def test_extend_adds_new_dataset(self, base_pipeline_engine):
        extended = base_pipeline_engine.extend(
            entities=[{"type": "dataset", "id": "new-feed", "classes": ["pii"]}],
            stylesheet="dataset#new-feed { retention: 3d; }",
        )
        assert extended.resolve(type="dataset", id="new-feed", property="retention") == "3d"
        ids = {d["entity_id"] for d in base_pipeline_engine.resolve_all(type="dataset")}
        assert "new-feed" not in ids

    def test_extend_chain_with_increasing_specificity(self, base_pipeline_engine):
        """Each extend level uses higher specificity to override previous."""
        level1 = base_pipeline_engine.extend(
            stylesheet="dataset#click-events { retention: 60d; }",
        )
        level2 = level1.extend(
            stylesheet="dataset#user-profiles { retention: 7d; }",
        )
        assert level2.resolve(type="dataset", id="user-profiles", property="retention") == "7d"
        assert level1.resolve(type="dataset", id="click-events", property="retention") == "60d"
        assert base_pipeline_engine.resolve(type="dataset", id="click-events", property="retention") == "90d"


class TestTrace:
    def test_competing_retention_rules(self, base_pipeline_engine):
        result = base_pipeline_engine.trace(type="dataset", id="payment-records", property="retention")
        assert result.value == "7y"
        assert len(result.candidates) >= 2
        values = {c.value for c in result.candidates}
        assert "7y" in values
        assert "90d" in values

    def test_trace_with_mode_context(self, pipeline_engine):
        result = pipeline_engine.trace(type="dataset", id="click-events", property="retention",
                                       context={"mode": "development"})
        assert result.value == "1d"

    def test_winner_has_highest_specificity(self, base_pipeline_engine):
        result = base_pipeline_engine.trace(type="dataset", id="payment-records", property="retention")
        winner = next(c for c in result.candidates if c.won)
        assert winner.value == "7y"


class TestResolveAll:
    def test_all_datasets(self, base_pipeline_engine):
        datasets = base_pipeline_engine.resolve_all(type="dataset")
        assert len(datasets) == 4
        assert {d["entity_id"] for d in datasets} == {"user-profiles", "click-events", "anonymized-clicks", "payment-records"}

    def test_all_transforms(self, base_pipeline_engine):
        assert len(base_pipeline_engine.resolve_all(type="transform")) == 3

    def test_all_sinks(self, base_pipeline_engine):
        assert len(base_pipeline_engine.resolve_all(type="sink")) == 3

    def test_with_mode(self, pipeline_engine):
        datasets = pipeline_engine.resolve_all(type="dataset", context={"mode": "development"})
        for ds in datasets:
            if ds["properties"].get("access"):
                assert ds["properties"]["access"] == "write"


class TestCheckAndRequire:
    def test_check_multiple_properties(self, base_pipeline_engine):
        assert base_pipeline_engine.check(type="sink", id="warehouse", allow="true", encryption="required")

    def test_check_fails_on_mismatch(self, base_pipeline_engine):
        assert not base_pipeline_engine.check(type="sink", id="partner-export", allow="true")

    def test_require_raises(self, base_pipeline_engine):
        with pytest.raises(PolicyDenied) as exc_info:
            base_pipeline_engine.require(type="sink", id="public-api", allow="true")
        assert exc_info.value.property == "allow"
        assert exc_info.value.actual == "false"

    def test_require_with_context(self, pipeline_engine):
        pipeline_engine.require(type="sink", id="partner-export", context={"mode": "development"}, allow="true")


class TestLint:
    def test_lint_runs(self, base_pipeline_engine):
        warnings = base_pipeline_engine.lint()
        assert isinstance(warnings, list)


class TestSaveAndReload:
    def test_round_trip(self, base_pipeline_engine, tmp_path):
        db_path = tmp_path / "pipeline.db"
        base_pipeline_engine.save(str(db_path))
        reloaded = PolicyEngine.from_db(str(db_path))
        assert reloaded.resolve(type="dataset", id="user-profiles", property="retention") == "14d"
        assert reloaded.resolve(type="sink", id="warehouse", property="allow") == "true"
        assert reloaded.resolve(type="transform", id="anonymize", property="cost-tier") == "premium"

    def test_entity_count_preserved(self, base_pipeline_engine, tmp_path):
        db_path = tmp_path / "pipeline.db"
        base_pipeline_engine.save(str(db_path))
        reloaded = PolicyEngine.from_db(str(db_path))
        assert len(reloaded.resolve_all(type="dataset")) == 4
