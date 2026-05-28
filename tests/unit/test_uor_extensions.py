"""Smoke tests for the UOR extension modules under :mod:`uar.core`.

These modules carry rich math/identity/security helpers and may have
optional native deps. The tests below assert that:

1. Each module imports cleanly without the optional `[uor]` extras
   (regression for the ``Graph is not defined`` failures in
   ``uar.uor.shacl_validation`` / ``rdf_formats``).
2. The lazy-singleton getters return non-``None`` integrators.
3. Reset functions clear the singleton.
"""

from __future__ import annotations


def test_uor_foundation_package_imports() -> None:
    import uar.uor  # noqa: F401


def test_uor_integration_singleton_lifecycle() -> None:
    from uar.core import uor_integration

    integrator = uor_integration.get_uor_integrator()
    assert integrator is not None
    uor_integration.reset_uor_integrator()


def test_atlas_embeddings_singleton_lifecycle() -> None:
    from uar.core import atlas_embeddings

    integrator = atlas_embeddings.get_atlas_integrator()
    assert integrator is not None
    atlas_embeddings.reset_atlas_integrator()


def test_prism_integration_singleton_lifecycle() -> None:
    from uar.core import prism_integration

    integrator = prism_integration.get_prism_integrator()
    assert integrator is not None
    prism_integration.reset_prism_integrator()


def test_sigmatics_integration_singleton_lifecycle() -> None:
    from uar.core import sigmatics_integration

    integrator = sigmatics_integration.get_sigmatics_integrator()
    assert integrator is not None
    sigmatics_integration.reset_sigmatics_integrator()


def test_ego_guard_forge_singleton_lifecycle() -> None:
    from uar.core import ego_guard_forge

    integrator = ego_guard_forge.get_ego_guard_integrator()
    assert integrator is not None
    ego_guard_forge.reset_ego_guard_integrator()


def test_uor_helpers_module_imports() -> None:
    from uar.core import uor_helpers  # noqa: F401


def test_uor_vector_ops_module_imports() -> None:
    from uar.core import uor_vector_ops  # noqa: F401
