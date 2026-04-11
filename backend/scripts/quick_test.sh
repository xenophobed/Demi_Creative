#!/bin/bash

# Quick Test Script - API quick test script
# Tests core functionality of API endpoints

echo "==================================="
echo "Creative Agent API - Quick Test"
echo "==================================="
echo ""

# Check if in the correct directory
if [ ! -f "backend/src/main.py" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

echo "📋 Test 1: Check file structure"
echo "-----------------------------------"

FILES=(
    "backend/src/main.py"
    "backend/src/api/models.py"
    "backend/src/api/routes/image_to_story.py"
    "backend/src/api/routes/interactive_story.py"
    "backend/src/services/session_manager.py"
    "backend/requirements.txt"
)

ALL_EXIST=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (missing)"
        ALL_EXIST=false
    fi
done

if [ "$ALL_EXIST" = true ]; then
    echo "✅ All required files exist"
else
    echo "⚠️  Some files are missing"
    exit 1
fi
echo ""

echo "📋 Test 2: Check Python environment"
echo "-----------------------------------"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Python installed: $PYTHON_VERSION"
else
    echo "❌ Python3 not installed"
    exit 1
fi
echo ""

echo "📋 Test 3: Check dependency installation status"
echo "-----------------------------------"

REQUIRED_PACKAGES=("fastapi" "uvicorn" "pydantic" "httpx")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        echo "✅ $package installed"
    else
        echo "⚠️  $package not installed"
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo "Hint: Install missing dependencies:"
    echo "  cd backend"
    echo "  pip install -r requirements.txt"
    echo ""
fi
echo ""

echo "📋 Test 4: Code syntax check"
echo "-----------------------------------"

SYNTAX_OK=true
for file in backend/src/**/*.py; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo "✅ $(basename $file)"
    else
        echo "❌ $(basename $file) - syntax error"
        SYNTAX_OK=false
    fi
done

if [ "$SYNTAX_OK" = true ]; then
    echo "✅ All Python files have correct syntax"
else
    echo "⚠️  Some files have syntax errors"
fi
echo ""

echo "📋 Test 5: Test file check"
echo "-----------------------------------"

TEST_FILES=(
    "tests/api/test_health.py"
    "tests/api/test_image_to_story.py"
    "tests/api/test_interactive_story.py"
    "tests/integration/test_session_integration.py"
    "tests/integration/test_end_to_end.py"
)

TEST_COUNT=0
for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
        TEST_COUNT=$((TEST_COUNT + 1))
    else
        echo "❌ $file (missing)"
    fi
done

echo "✅ Total test files: $TEST_COUNT"
echo ""

echo "==================================="
echo "Test Summary"
echo "==================================="

if [ "$ALL_EXIST" = true ] && [ "$SYNTAX_OK" = true ]; then
    echo "✅ All basic checks passed!"
    echo ""
    echo "Next steps:"
    echo "1. Install dependencies (if not already installed):"
    echo "   cd backend && pip install -r requirements.txt"
    echo ""
    echo "2. Start the service:"
    echo "   python3 -m backend.src.main"
    echo ""
    echo "3. Run tests in another terminal:"
    echo "   pytest tests/api/test_health.py -v"
    echo ""
    echo "4. Or test with curl:"
    echo "   curl http://localhost:8000/health"
else
    echo "⚠️  Some checks failed, please fix and retry"
    exit 1
fi
