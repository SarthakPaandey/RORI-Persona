#!/bin/bash
set -e

echo "🚀 AI Persona — Full Setup"
echo "================================"

command -v python3 >/dev/null 2>&1 || { echo "python3 required"; exit 1; }
command -v node >/dev/null 2>&1    || { echo "node required"; exit 1; }
command -v npm >/dev/null 2>&1     || { echo "npm required"; exit 1; }

if [ ! -f .env ]; then
  cp .env.example .env
  echo "📝 .env created — fill in your API keys before continuing."
  exit 0
fi

echo "✅ .env found"

echo ""
echo "📦 Installing backend dependencies..."
cd backend
python3 -m venv .venv
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -r requirements.txt --quiet
echo "✅ Backend deps installed"
cd ..

echo ""
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --silent
echo "✅ Frontend deps installed"
cd ..

echo ""
echo "================================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Fill in .env with your API keys"
echo "  2. Place your resume at backend/data/resume.pdf"
echo "  3. Run:  make ingest"
echo "  4. Run:  make run-all"
echo "  5. Run:  cd voice && python setup_vapi.py"
