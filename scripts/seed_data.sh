#!/bin/bash
set -e

echo "🌱 Running data ingestion pipeline"
echo "==================================="

cd backend

if [ ! -f .venv/bin/activate ]; then
  echo "Run scripts/setup.sh first."
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

if [ ! -f data/resume.pdf ]; then
  echo "❌ Resume not found at backend/data/resume.pdf"
  echo "   Place your resume PDF there and re-run."
  exit 1
fi

echo "📄 Ingesting resume..."
echo "🔗 Ingesting GitHub repos..."
python -m app.ingestion.run_ingestion

echo ""
echo "✅ Data ingestion complete!"
echo "   Your vector store is ready."
