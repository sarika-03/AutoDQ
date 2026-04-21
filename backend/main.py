"""
main.py
CLI entrypoint for dq-pilot.
"""

import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

# Ensure we load .env from the project root
load_dotenv(Path(__file__).parent.parent / ".env")

from om_client import OpenMetadataClient
from recommender import DQRecommender
from test_creator import TestCreator
from formatter import Formatter, Colors

def setup_logging():
    logging.basicConfig(
        level=logging.WARNING, # keep mostly quiet to focus on AI output
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

def main():
    setup_logging()
    
    parser = argparse.ArgumentParser(description="dq-pilot: AI-powered OpenMetadata test recommender")
    parser.add_argument("--table", required=True, help="FQN of the table (e.g. sample_data.ecommerce_db.customers)")
    parser.add_argument("--dry-run", action="store_true", help="Print recommendations without applying to OM")
    parser.add_argument("--apply", action="store_true", help="Create draft test cases in OpenMetadata")
    
    args = parser.parse_args()
    
    if not (args.dry_run or args.apply):
        print(f"{Colors.CRITICAL}Error: You must specify either --dry-run or --apply{Colors.ENDC}")
        parser.print_help()
        sys.exit(1)
        
    print(f"Initializing clients...")
    try:
        om = OpenMetadataClient.from_env()
        if not om.ping():
             print(f"{Colors.WARNING}Warning: OpenMetadata API not reachable or ping timed out. Check connection.{Colors.ENDC}")
        recommender = DQRecommender.from_env()
    except KeyError as e:
        print(f"{Colors.CRITICAL}Configuration Error: Missing environment variable {e}{Colors.ENDC}")
        print("Please ensure your .env file is set up properly.")
        sys.exit(1)
        
    print(f"Fetching table profile for {Colors.BOLD}{args.table}{Colors.ENDC}...")
    try:
        table_profile = om.get_table_profile(args.table)
        test_definitions = om.get_test_definitions()
        existing_tests = om.get_existing_tests(args.table)
    except Exception as e:
        print(f"{Colors.CRITICAL}Error fetching data from OpenMetadata:{Colors.ENDC} {e}")
        sys.exit(1)
        
    print(f"Generating data quality recommendations using AI...")
    try:
        recommendations, summary = recommender.recommend(table_profile, test_definitions, existing_tests)
    except Exception as e:
        print(f"{Colors.CRITICAL}AI Recommendation Error:{Colors.ENDC} {e}")
        sys.exit(1)
        
    # Always print recommendations
    Formatter.print_recommendations(recommendations, summary, is_dry_run=args.dry_run and not args.apply)
    
    if args.apply:
        creator = TestCreator(client=om)
        creator.apply(args.table, recommendations)

if __name__ == "__main__":
    main()
