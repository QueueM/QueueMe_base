#!/bin/bash

# Intelligent Code Cleaner for Django Projects
# By ChatGPT for QueueMe — Clean, Check, and Auto-Fix Your Entire Codebase

# =================== CONFIG ====================
EXCLUDE_DIRS="venv,staticfiles,.git,__pycache__"
PROJECT_ROOT="."
PYLINT_DIRS=$(find $PROJECT_ROOT -type d | grep -Ev "($EXCLUDE_DIRS)")
# ===============================================

echo "🔧 [0/10] Fixing file permissions..."
sudo chown -R $USER:$USER .

echo "🎨 [1/10] Formatting code with Black..."
black $PROJECT_ROOT --exclude '/venv/'

echo "📦 [2/10] Sorting imports with isort..."
isort $PROJECT_ROOT --skip venv

echo "🧽 [3/10] Removing unused imports & variables with autoflake..."
autoflake --remove-all-unused-imports --remove-unused-variables --in-place -r $PROJECT_ROOT

echo "🧠 [4/10] Running mypy type checker..."
mypy $PROJECT_ROOT --exclude venv > mypy_report.txt

echo "🧹 [5/10] Running flake8 linter..."
flake8 $PROJECT_ROOT --exclude venv > flake8_report.txt

echo "🔍 [6/10] Running pylint for deep code analysis..."
pylint $PYLINT_DIRS --output-format=text > pylint_report.txt

echo "🛡️ [7/10] Running Bandit for security issues..."
bandit -r $PROJECT_ROOT --exclude venv > bandit_report.txt

echo "🔓 [8/10] Checking package vulnerabilities with safety..."
safety check > safety_report.txt

echo "🧟 [9/10] Detecting dead code with vulture..."
vulture $PROJECT_ROOT > vulture_report.txt

echo "🧬 [10/10] Detecting duplicated code (R0801)..."
pylint $PYLINT_DIRS --disable=all --enable=R0801 > duplicate_code_report.txt

echo ""
echo "✅ All scans and fixes complete!"
echo ""
echo "📁 Reports generated:"
echo " - mypy_report.txt"
echo " - flake8_report.txt"
echo " - pylint_report.txt"
echo " - bandit_report.txt"
echo " - safety_report.txt"
echo " - vulture_report.txt"
echo " - duplicate_code_report.txt"
echo ""
echo "💡 Tip: Upload any of these reports here, and I will help you fix the rest intelligently."
