from app.ai.contracts import AICapability
from app.ai.prompt_registry import get_capability_prompt


def test_every_capability_has_a_versioned_prompt_contract():
    for capability in AICapability:
        contract = get_capability_prompt(capability)
        assert contract.capability is capability
        assert contract.version.endswith(".v1")
        assert len(contract.digest) == 64
        assert contract.system_prompt
        assert contract.output_schema["type"] == "object"
        assert contract.workflow_contract["clinical_use_enabled"] is False
        assert contract.workflow_contract["requires_clinician_review"] is True


def test_no_capability_has_implicit_tool_permissions():
    for capability in AICapability:
        assert get_capability_prompt(capability).tool_permissions == ()


def test_capability_prompts_are_distinct_and_versioned_independently():
    contracts = [get_capability_prompt(capability) for capability in AICapability]
    assert len({item.version for item in contracts}) == len(contracts)
    assert len({item.digest for item in contracts}) == len(contracts)
