from catchain.production import production_checklist


def test_production_checklist_blocks_without_external_gates():
    result = production_checklist({})
    assert result.status == "blocked"
    assert {"real_gold", "approved_policy", "registry_sync"} <= set(result.blockers)


def test_production_checklist_is_ready_only_when_every_gate_is_evidenced():
    evidence = {
        code: True
        for code in (
            "real_gold",
            "approved_policy",
            "registry_sync",
            "production_storage",
            "review_api",
            "observability",
        )
    }
    result = production_checklist(evidence)
    assert result.status == "ready"
    assert result.blockers == ()

