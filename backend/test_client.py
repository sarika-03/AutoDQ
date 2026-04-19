import os
from dotenv import load_dotenv
from pathlib import Path

# Go one level up from backend/ to find .env
load_dotenv(Path(__file__).parent.parent / ".env")


from om_client import OpenMetadataClient

client = OpenMetadataClient.from_env()

# 1. Health check
print("✅ OM reachable:", client.ping())


tables = client._get("/tables", params={"limit": 20})
print("\n📋 Available tables:")
for t in tables.get("data", []):
    print(f"   {t['fullyQualifiedName']}")


# 2. Fetch table profile
profile = client.get_table_profile("sample_data.ecommerce_db.orders")
print(f"\n📊 Table: {profile.name}")
print(f"   Rows: {profile.row_count} | Columns: {profile.column_count}")
print(f"   Description: {profile.description or 'None'}")

print("\n📋 Columns:")
for col in profile.columns:
    print(f"   {col.name:<25} {col.data_type:<15} null%: {col.null_proportion:.1%}  unique%: {col.unique_proportion:.1%}")

# 3. Test definitions
definitions = client.get_test_definitions()
print(f"\n🧪 Available test definitions: {len(definitions)}")
for d in definitions[:8]:
    print(f"   [{d.entity_type:<6}] {d.name}")

# 4. Existing tests
existing = client.get_existing_tests("sample_data.ecommerce_db.orders")
print(f"\n🔍 Existing tests on this table: {len(existing)}")
for t in existing:
    print(f"   column: {t.column_name or 'TABLE':<20} test: {t.test_definition_name}")