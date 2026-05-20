"""UOR Ecosystem Integration Example.

Demonstrates how to use the UOR Ecosystem layer from Python:
- Canonicalize data with UOR-ADDR-1
- Call the live UOR Foundation API
- Check ecosystem health
- Query Hologram and Moltbook (with graceful degradation)

Run with:
    python examples/uor_ecosystem_example.py
"""

from uar.core.uor_ecosystem import (
    get_uor_ecosystem,
    UORAddrClient,
    UORFoundationClient,
)


def example_canonicalize() -> None:
    """Canonicalize data and compute SHA-256 digest."""
    print("=== UOR-ADDR Canonicalization ===")
    client = UORAddrClient()
    data = {
        "project": "my-app",
        "version": "1.2.3",
        "dependencies": ["fastapi"],
    }
    envelope = client.canonicalize(data)
    print(f"  Digest: {envelope['digest']}")
    print(f"  Size: {envelope['size']} bytes")
    print(f"  MediaType: {envelope['mediaType']}")

    # Wrap as UOR object for provenance tracking
    uor_obj = client.wrap_with_uor(data, source="example_script")
    print(f"  Provenance: {len(uor_obj.provenance)} entries")


def example_foundation_api() -> None:
    """Call the live UOR Foundation API."""
    print("\n=== UOR Foundation Live API ===")
    client = UORFoundationClient()
    result = client.verify(x=42)
    print(f"  Verify(x=42): {result}")


def example_ecosystem_status() -> None:
    """Check health of all ecosystem integrations."""
    print("\n=== Ecosystem Status ===")
    eco = get_uor_ecosystem()
    status = eco.status()
    for name, info in status.items():
        print(f"  {name}: {info}")


def example_hologram_mock() -> None:
    """Hologram query with graceful mock fallback (no API key)."""
    print("\n=== Hologram Query (mock fallback) ===")
    eco = get_uor_ecosystem()
    result = eco.hologram.query("test-model", {"input": "hello"})
    print(f"  Status: {result['status']}")
    print(f"  Note: {result.get('note', 'N/A')}")


def example_moltbook_mock() -> None:
    """Moltbook forum access with graceful mock fallback (no API key)."""
    print("\n=== Moltbook List (mock fallback) ===")
    eco = get_uor_ecosystem()
    result = eco.moltbook.list_topics()
    print(f"  Status: {result['status']}")


def main() -> None:
    print("UOR Ecosystem Integration Examples")
    print("=" * 50)

    example_canonicalize()
    example_foundation_api()
    example_ecosystem_status()
    example_hologram_mock()
    example_moltbook_mock()

    print("\n" + "=" * 50)
    print("Done. Set HOLOGRAM_API_KEY / MOLTBOOK_API_KEY for live calls.")


if __name__ == "__main__":
    main()
