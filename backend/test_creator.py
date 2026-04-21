"""
test_creator.py
Handles creating test cases via OpenMetadata API.
"""

import logging
from om_client import OpenMetadataClient
from recommender import TestRecommendation
from formatter import Colors

logger = logging.getLogger(__name__)

class TestCreator:
    def __init__(self, client: OpenMetadataClient):
        self.client = client

    def apply(self, fqn: str, recommendations: list[TestRecommendation]) -> None:
        logger.info(f"Applying {len(recommendations)} tests to {fqn}")
        success_count = 0
        
        print(f"\n{Colors.BOLD}{Colors.HEADER}=== Creating Tests in OpenMetadata ==={Colors.ENDC}\n")
        
        for rec in recommendations:
            table_name = fqn.split('.')[-1]
            safe_col_name = (rec.column_name or 'table').replace('"', '').replace("'", "")
            test_case_name = f"dq_pilot_{table_name}_{safe_col_name}_{rec.test_definition_name}"
            
            # OpenMetadata test case names usually need to be unique and specific format
            try:
                self.client.create_test_case(
                    fqn=fqn,
                    test_definition_name=rec.test_definition_name,
                    test_case_name=test_case_name,
                    column_name=rec.column_name,
                    parameters=rec.parameters,
                    description=rec.reasoning
                )
                success_count += 1
                print(f" {Colors.GREEN}✓{Colors.ENDC} Created: {test_case_name}")
            except Exception as e:
                logger.error("Failed to create test case %s: %s", test_case_name, e)
                print(f" {Colors.CRITICAL}✗{Colors.ENDC} Failed to create: {test_case_name} ({e})")
                
        print(f"\n{Colors.BOLD}Applied {success_count} out of {len(recommendations)} tests successfully.{Colors.ENDC}")
