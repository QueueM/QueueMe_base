#!/usr/bin/env python
"""
Script to audit API documentation quality and consistency.
This script checks for:
1. Missing documentation on API views
2. Duplicate parameter definitions
3. Inconsistent parameter naming
4. Missing response definitions

Usage:
    python scripts/audit_api_docs.py [--fix]
"""

import os
import re
import sys
import glob
from collections import defaultdict

# Check if --fix flag is passed
FIX_MODE = "--fix" in sys.argv

# Paths to scan
API_PATHS = [
    "api/v1/views",
    "apps/*/views.py",
    "apps/*/api",
]

# Patterns to look for
SWAGGER_DECORATOR_PATTERN = r"@swagger_auto_schema\("
PARAMETER_DEFINITION_PATTERN = r"openapi\.Parameter\(\s*[\'\"]([\w_]+)[\'\"]\s*,"
DEDUPE_USAGE_PATTERN = r"dedupe_manual_parameters\("
VIEWSET_CLASS_PATTERN = r"class\s+(\w+)\((?!QueueMeViewSet)"
MISSING_RESPONSES_PATTERN = r"@swagger_auto_schema\([^)]*(?!responses=)"

# Setup result storage
issues_found = {
    "missing_swagger": [],
    "missing_dedupe": [],
    "duplicate_params": [],
    "not_using_base_viewset": [],
    "missing_responses": [],
}

def check_file(filepath):
    """Check a Python file for API documentation issues"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return
        
    # Check if this is an API view file that should be documented
    if "APIView" in content or "ViewSet" in content:
        
        # Find all class definitions in the file
        class_matches = re.finditer(r"class\s+(\w+)\(([^)]+)\):", content)
        for class_match in class_matches:
            class_name = class_match.group(1)
            parent_classes = class_match.group(2)
            
            # Skip if it's just a base class or a test
            if ("APIView" not in parent_classes and 
                "ViewSet" not in parent_classes and 
                "GenericAPIView" not in parent_classes):
                continue
                
            # Check if the class has swagger_auto_schema decorators
            class_start = class_match.start()
            next_class = content.find("\nclass ", class_start + 1)
            if next_class == -1:
                next_class = len(content)
            class_content = content[class_start:next_class]
            
            if "swagger_auto_schema" not in class_content and "APIView" in parent_classes:
                issues_found["missing_swagger"].append(f"{filepath} - {class_name}")
                continue
                
            # Check if using QueueMeViewSet
            if ("ViewSet" in parent_classes and 
                "QueueMeViewSet" not in parent_classes and 
                "test" not in filepath.lower()):
                issues_found["not_using_base_viewset"].append(f"{filepath} - {class_name}")
                
            # Check for dedupe_manual_parameters usage
            if "manual_parameters" in class_content and "dedupe_manual_parameters" not in class_content:
                issues_found["missing_dedupe"].append(f"{filepath} - {class_name}")
                
            # Check for duplicate parameter definitions
            params = re.findall(PARAMETER_DEFINITION_PATTERN, class_content)
            param_counts = defaultdict(int)
            for param in params:
                param_counts[param] += 1
                
            for param, count in param_counts.items():
                if count > 1:
                    issues_found["duplicate_params"].append(f"{filepath} - {class_name} - {param} ({count} times)")
                    
            # Check for missing responses
            if re.search(SWAGGER_DECORATOR_PATTERN, class_content):
                # Find all swagger decorators without responses
                swagger_matches = re.finditer(SWAGGER_DECORATOR_PATTERN, class_content)
                for swagger_match in swagger_matches:
                    # Get the decorator content
                    deco_start = swagger_match.start()
                    deco_end = find_closing_parenthesis(class_content, deco_start)
                    if deco_end == -1:
                        continue
                    
                    deco_content = class_content[deco_start:deco_end+1]
                    if "responses=" not in deco_content:
                        issues_found["missing_responses"].append(f"{filepath} - {class_name}")
                        break  # Only report once per class

def find_closing_parenthesis(text, start_pos):
    """Find the closing parenthesis for a decorator"""
    paren_count = 0
    for i in range(start_pos, len(text)):
        if text[i] == '(':
            paren_count += 1
        elif text[i] == ')':
            paren_count -= 1
            if paren_count == 0:
                return i
    return -1

# Function to apply automatic fixes
def fix_issues(filepath):
    """Apply automatic fixes to common issues"""
    if not FIX_MODE:
        return

    try:
        with open(filepath, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath} for fixing: {e}")
        return
    
    modified = False
    
    # Add imports if missing
    if "manual_parameters" in content and "dedupe_manual_parameters" not in content:
        import_line = "from api.documentation.utils import dedupe_manual_parameters\n"
        
        # Check if we have a swagger_auto_schema import to add after
        if "from drf_yasg.utils import swagger_auto_schema" in content:
            content = content.replace(
                "from drf_yasg.utils import swagger_auto_schema", 
                "from drf_yasg.utils import swagger_auto_schema\n" + import_line
            )
            modified = True
        else:
            # Add after the imports block
            import_section_end = content.find("\n\n", content.find("import"))
            if import_section_end > 0:
                content = content[:import_section_end] + "\n" + import_line + content[import_section_end:]
                modified = True
    
    # Fix missing dedupe calls
    if "manual_parameters=[" in content and "dedupe_manual_parameters([" not in content:
        content = content.replace(
            "manual_parameters=[", 
            "manual_parameters=dedupe_manual_parameters(["
        )
        # Fix closing parenthesis
        content = re.sub(r'manual_parameters=dedupe_manual_parameters\(\[(.*?)\]\)', 
                        r'manual_parameters=dedupe_manual_parameters([\1])', 
                        content)
        modified = True
        
    if modified:
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"✅ Applied fixes to {filepath}")
        except Exception as e:
            print(f"Error writing fixes to {filepath}: {e}")

# Main function
def main():
    """Main function to audit API documentation"""
    print("Auditing API documentation...")
    
    # Find all Python files to check
    files_to_check = []
    for path_pattern in API_PATHS:
        matching_files = glob.glob(f"{path_pattern}/**/*.py", recursive=True)
        matching_files.extend(glob.glob(f"{path_pattern}/*.py"))
        files_to_check.extend(matching_files)
    
    # Remove duplicates
    files_to_check = list(set(files_to_check))
    print(f"Found {len(files_to_check)} files to check")
    
    # Check each file
    for filepath in files_to_check:
        try:
            check_file(filepath)
            if FIX_MODE:
                fix_issues(filepath)
        except Exception as e:
            print(f"Error checking {filepath}: {e}")
    
    # Print results
    print("\n🔍 API Documentation Audit Results:")
    total_issues = sum(len(issues) for issues in issues_found.values())
    
    if total_issues == 0:
        print("✅ No issues found! Documentation looks great.")
        return 0
        
    print(f"Found {total_issues} issues:")
    
    for issue_type, issues in issues_found.items():
        if issues:
            print(f"\n⚠️ {issue_type.replace('_', ' ').title()} ({len(issues)}):")
            for issue in issues[:10]:  # Show first 10 issues only
                print(f"  - {issue}")
            
            if len(issues) > 10:
                print(f"  - ... and {len(issues) - 10} more issues")
                
    # Print recommendations
    print("\n📋 Recommendations:")
    if issues_found["missing_swagger"]:
        print("  - Add @swagger_auto_schema decorators to all API view methods")
    if issues_found["missing_dedupe"]:
        print("  - Use dedupe_manual_parameters for all manual parameter definitions")
    if issues_found["not_using_base_viewset"]:
        print("  - Convert ViewSets to inherit from QueueMeViewSet")
    if issues_found["duplicate_params"]:
        print("  - Remove duplicate parameter definitions and use centralized parameters")
    if issues_found["missing_responses"]:
        print("  - Add response definitions to all @swagger_auto_schema decorators")
    
    if FIX_MODE:
        print("\n🔧 Some issues were automatically fixed. Run the script again to check remaining issues.")
    else:
        print("\n💡 Run with --fix flag to automatically fix some issues: python scripts/audit_api_docs.py --fix")
    
    return 1 if total_issues > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
