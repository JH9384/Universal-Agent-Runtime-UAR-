"""UOR Integration Example for UAR.

This example demonstrates how to use the UOR integration layer
and UOR Foundation assets in the UAR system.
"""

from uar.core.uor_integration import (
    UORObject,
    ObjectMode,
    wrap_input_data,
    wrap_output_data,
)
from uar.core.sigmatics_integration import (
    create_sigil,
    create_sigil_expression,
)
from uar.core.atlas_embeddings import create_golden_seed
from uar.core.ego_guard_forge import (
    create_security_policy,
    get_ego_guard_integrator,
)
from uar.core.prism_integration import (
    create_prism,
    PrismFacet,
)
from uar.core.uor_helpers import (
    UORHelper,
    UORAssetHelper,
    UORMetricsHelper,
    UORValidationHelper,
)


def example_basic_uor():
    """Example: Basic UOR object usage."""
    print("=== Basic UOR Example ===")

    # Create a UOR object
    data = {"message": "Hello, UAR!"}
    uor_obj = UORObject(data=data, mode=ObjectMode.IMMUTABLE_SINGULAR)

    # Compute digest
    digest = uor_obj.compute_digest()
    print(f"Digest: {digest}")

    # Get base attributes
    base_attrs = uor_obj.get_base_attributes()
    print(f"Base attributes: {base_attrs}")

    # Add provenance
    uor_obj.add_provenance(source="example", operation="create")
    print(f"Provenance: {uor_obj.provenance}")


def example_sigmatics():
    """Example: Sigmatics (Atlas Sigil Algebra) usage."""
    print("\n=== Sigmatics Example ===")

    # Create sigils
    sigil1 = create_sigil("A", value=10)
    sigil2 = create_sigil("B", value=20)
    sigil3 = create_sigil("C", value=30)

    # Create expression
    expr = create_sigil_expression([sigil1, sigil2, sigil3], "sum")

    # Evaluate
    result = expr.evaluate()
    print(f"Sum result: {result}")

    # Wrap with UOR
    uor_obj = expr.wrap_with_uor(source="sigmatics_example")
    print(f"UOR digest: {uor_obj.digest}")


def example_atlas_embeddings():
    """Example: Atlas Embeddings (Golden Seed Vector) usage."""
    print("\n=== Atlas Embeddings Example ===")

    # Create Golden Seed Vector
    seed = create_golden_seed(dimensions=248, random=True)

    # Compute symmetry
    symmetry = seed.compute_symmetry()
    print(f"Symmetry properties: {symmetry}")

    # Normalize
    seed.normalize()
    print(f"Normalized vector norm: {seed.vector_data[:5]}")

    # Wrap with UOR
    uor_obj = seed.wrap_with_uor(source="atlas_example")
    print(f"UOR digest: {uor_obj.digest}")


def example_ego_guard_forge():
    """Example: Ego Guard Forge security policy usage."""
    print("\n=== Ego Guard Forge Example ===")

    # Create security policy
    policy = create_security_policy(
        policy_id="example_policy",
        name="Example Policy",
        description="Example security policy",
        rules={"access_level": "admin"},
    )

    # Evaluate policy
    context = {"access_level": "admin"}
    result = policy.evaluate(context)
    print(f"Policy evaluation result: {result}")

    # Wrap with UOR
    uor_obj = policy.wrap_with_uor(source="ego_guard_example")
    print(f"UOR digest: {uor_obj.digest}")

    # Get audit trail
    integrator = get_ego_guard_integrator()
    audit_trail = integrator.get_audit_trail()
    print(f"Audit trail size: {len(audit_trail)}")


def example_prism():
    """Example: Prism data transformation usage."""
    print("\n=== Prism Example ===")

    # Create facets
    facet1 = PrismFacet(facet_id="f1", name="uppercase", data="hello")
    facet2 = PrismFacet(facet_id="f2", name="lowercase", data="WORLD")

    # Create prism
    prism = create_prism(prism_id="example_prism", facets=[facet1, facet2])

    # Refract data
    results = prism.refract("test data")
    print(f"Refraction results count: {len(results)}")

    # Wrap with UOR
    uor_obj = prism.wrap_with_uor(source="prism_example")
    print(f"UOR digest: {uor_obj.digest}")


def example_uor_helpers():
    """Example: UOR helper utilities usage."""
    print("\n=== UOR Helpers Example ===")

    # Wrap data with UOR
    data = {"key": "value"}
    uor_obj = UORHelper.wrap_data_with_uor(data, source="helper_example")
    print(f"Wrapped digest: {uor_obj.digest}")

    # Get UOR summary
    summary = UORHelper.get_uor_summary(uor_obj)
    print(f"UOR summary: {summary}")

    # Validate UOR object
    validation = UORValidationHelper.validate_uor_object(uor_obj)
    print(f"Validation result: {validation}")

    # Collect metrics
    metrics = UORMetricsHelper.collect_uor_metrics()
    print(f"Metrics collected: {list(metrics.keys())}")


def example_computation_pipeline():
    """Example: Computation pipeline using UOR assets."""
    print("\n=== Computation Pipeline Example ===")

    # Create a computation pipeline
    results = UORAssetHelper.create_computation_pipeline(
        data=100,
        apply_sigil=True,
        apply_embedding=True,
        apply_security=True,
        apply_prism=True,
    )

    print(f"Pipeline results: {results}")


def example_end_to_end():
    """Example: End-to-end UOR integration workflow."""
    print("\n=== End-to-End Example ===")

    # Step 1: Wrap input data
    input_data = {"user_id": 123, "action": "read"}
    input_uor = wrap_input_data(input_data, source="user_request")
    print(f"Input digest: {input_uor.digest}")

    # Step 2: Process with Sigmatics
    sigil_expr = create_sigil_expression(
        [create_sigil("x", value=input_data["user_id"])], "sum"
    )
    sigil_result = sigil_expr.evaluate()
    print(f"Sigmatics result: {sigil_result}")

    # Step 3: Create embedding
    seed = create_golden_seed(dimensions=248, random=True)
    embedding_uor = seed.wrap_with_uor(source="embedding")
    print(f"Embedding digest: {embedding_uor.digest}")

    # Step 4: Security check
    policy = create_security_policy(
        policy_id="check_user",
        name="User Check",
        description="Validate user action",
        rules={"allowed_action": "read"},
    )
    is_allowed = policy.evaluate({"allowed_action": "read"})
    print(f"Security check: {is_allowed}")

    # Step 5: Wrap output
    output_data = {
        "user_id": input_data["user_id"],
        "action": input_data["action"],
        "sigil_result": sigil_result,
        "security_allowed": is_allowed,
    }
    output_uor = wrap_output_data(output_data, source="user_response")
    print(f"Output digest: {output_uor.digest}")

    # Step 6: Validate chain
    chain_validation = UORValidationHelper.validate_uor_chain(
        [input_uor, embedding_uor, output_uor]
    )
    print(f"Chain validation: {chain_validation['valid']}")


def main():
    """Run all examples."""
    print("UOR Integration Examples")
    print("=" * 50)

    example_basic_uor()
    example_sigmatics()
    example_atlas_embeddings()
    example_ego_guard_forge()
    example_prism()
    example_uor_helpers()
    example_computation_pipeline()
    example_end_to_end()

    print("\n" + "=" * 50)
    print("All examples completed!")

    # Cleanup
    print("\nCleaning up...")
    UORAssetHelper.reset_all_integrators()
    print("Integrators reset.")


if __name__ == "__main__":
    main()
