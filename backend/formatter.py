"""
formatter.py
Handles CLI output styling for TestRecommendations.
"""

from recommender import TestRecommendation

# Terminal ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    CRITICAL = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ENDC = '\033[0m'

class Formatter:
    @staticmethod
    def print_recommendations(recommendations: list[TestRecommendation], summary: str, is_dry_run: bool):
        print(f"\n{Colors.BOLD}{Colors.HEADER}=== Data Quality AI Analysis ==={Colors.ENDC}\n")
        print(f"{Colors.BOLD}Summary:{Colors.ENDC} {summary}\n")
        
        if not recommendations:
            print(f"{Colors.GREEN}No data quality tests recommended (or all tests are already covered).{Colors.ENDC}\n")
            return
            
        print(f"Total tests recommended: {Colors.BOLD}{len(recommendations)}{Colors.ENDC}")
        mode_text = f"[{Colors.CYAN}DRY RUN{Colors.ENDC}]" if is_dry_run else f"[{Colors.GREEN}APPLY{Colors.ENDC}]"
        print(f"Mode: {mode_text}\n")
        
        print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")
        
        for i, rec in enumerate(recommendations, start=1):
            target = f"{Colors.BLUE}Column: {rec.column_name}{Colors.ENDC}" if rec.column_name else f"{Colors.BLUE}Table-level{Colors.ENDC}"
            
            # Severity color
            sev_color = Colors.CRITICAL if rec.severity == "CRITICAL" else Colors.WARNING
            
            print(f"{Colors.BOLD}{i}. {rec.display_name}{Colors.ENDC}  [{sev_color}{rec.severity}{Colors.ENDC}]")
            print(f"   Target:       {target}")
            print(f"   Definition:   {Colors.CYAN}{rec.test_definition_name}{Colors.ENDC}")
            
            # Parameters format
            if rec.parameters:
                params_str = ", ".join([f"{p['name']}={p['value']}" for p in rec.parameters])
                print(f"   Parameters:   {params_str}")
                
            print(f"   Confidence:   {rec.confidence}")
            print(f"   Reasoning:    {rec.reasoning}")
            print(f"{Colors.BOLD}{'-'*60}{Colors.ENDC}")
        
        print("\n")
