#!/usr/bin/env python3
"""
Script to apply refactoring changes to the LORAG codebase.
"""

import os
import shutil
import sys

def backup_file(file_path):
    """Create a backup of a file."""
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup: {backup_path}")

def apply_refactoring():
    """Apply refactoring changes to the LORAG codebase."""
    # Define the files to refactor
    files_to_refactor = [
        ("lorag/database.py", "lorag/database_refactored.py"),
        ("lorag/batch.py", "lorag/batch_refactored.py"),
        ("lorag/core.py", "lorag/core_refactored.py")
    ]
    
    # Create backups and apply changes
    for original, refactored in files_to_refactor:
        if os.path.exists(original):
            # Create backup
            backup_file(original)
            
            # Replace with refactored version
            shutil.copy2(refactored, original)
            print(f"Replaced {original} with {refactored}")
        else:
            print(f"Warning: Original file {original} not found")
    
    print("\nRefactoring applied successfully!")
    print("You can run the tests with: python run_tests.py")

if __name__ == "__main__":
    # Ask for confirmation
    print("This script will apply refactoring changes to the LORAG codebase.")
    print("Backups will be created with .bak extension.")
    response = input("Do you want to continue? (y/n): ")
    
    if response.lower() == 'y':
        apply_refactoring()
    else:
        print("Refactoring cancelled.")
        sys.exit(0)