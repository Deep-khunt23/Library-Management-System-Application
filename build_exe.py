"""
Build script to compile the Library Management System into a standalone Windows .exe using PyInstaller.
Includes all CustomTkinter assets, themes, and dependencies.
"""

import os
import sys
import subprocess
import shutil

def build():
    print("=" * 60)
    print("Building Library Management System (.exe)...")
    print("=" * 60)

    # Output directory
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
    build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--clean",
        "--name", "LibraryManagementSystem",
        "--collect-all", "customtkinter",
        "main.py"
    ]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe_path = os.path.join(dist_dir, "LibraryManagementSystem.exe")
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print(f"Executable created at: {exe_path}")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"File Size: {size_mb:.2f} MB")
        print("=" * 60)
    else:
        print("\nBUILD FAILED with error code:", result.returncode)
        sys.exit(result.returncode)

if __name__ == "__main__":
    build()
