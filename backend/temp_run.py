from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")

from om_client import OpenMetadataClient

client = OpenMetadataClient.from_env()

# Check all database services
services = client._get("/services/databaseServices", params={"limit": 20})
print("🔌 Database services:")
for s in services.get("data", []):
    print(f"   {s['name']}")

# Search for any tables at all
results = client._get("/search/query", params={
    "q": "*",
    "index": "table_search_index",
    "from": 0,
    "size": 20
})
hits = results.get("hits", {}).get("hits", [])
print(f"\n📋 Tables found: {len(hits)}")
for hit in hits:
    src = hit.get("_source", {})
    print(f"   {src.get('fullyQualifiedName', 'unknown')}")