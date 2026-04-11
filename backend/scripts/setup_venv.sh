#!/bin/bash

# Virtual environment setup script

echo "=========================================="
echo "Creating virtual environment"
echo "=========================================="
echo ""

# Check current directory
echo "Current directory: $(pwd)"
echo ""

# Create virtual environment
echo "Step 1: Creating virtual environment..."
python3 -m venv venv

# Check if creation succeeded
if [ -d "venv" ]; then
    echo "✅ Virtual environment created successfully!"
    echo ""

    echo "Step 2: Checking virtual environment structure..."
    ls -la venv/
    echo ""

    echo "=========================================="
    echo "✅ Virtual environment is ready!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Activate the virtual environment:"
    echo "   source venv/bin/activate"
    echo ""
    echo "2. Install dependencies:"
    echo "   pip install -r backend/requirements.txt"
    echo ""
    echo "3. Start the service:"
    echo "   python -m backend.src.main"
    echo ""
else
    echo "❌ Virtual environment creation failed"
    echo ""
    echo "Possible reasons:"
    echo "1. Python venv module not installed"
    echo "2. Insufficient disk space"
    echo "3. Permission issues"
    echo ""
    echo "Try using virtualenv instead:"
    echo "  virtualenv venv"
    exit 1
fi
