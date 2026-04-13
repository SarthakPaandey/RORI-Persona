#!/bin/bash
set -e

echo "🚀 Deploying AI Persona"
echo "================================"

echo ""
echo "📡 Deploying backend to Railway..."

if ! command -v railway &>/dev/null; then
  echo "Installing Railway CLI..."
  npm install -g @railway/cli --silent
fi

cd backend
railway up --detach
BACKEND_URL=$(railway status --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('url',''))" 2>/dev/null || echo "")
cd ..

if [ -n "$BACKEND_URL" ]; then
  echo "✅ Backend deployed: $BACKEND_URL"
else
  echo "⚠️  Could not detect Railway URL automatically. Check Railway dashboard."
  read -r -p "Enter your Railway backend URL: " BACKEND_URL
fi

echo ""
echo "🌐 Deploying frontend to Vercel..."

if ! command -v vercel &>/dev/null; then
  npm install -g vercel --silent
fi

cd frontend
# Rewrites in next.config.js use BACKEND_URL; leave NEXT_PUBLIC_API_URL unset so the browser uses same-origin /api.
BACKEND_URL="$BACKEND_URL" vercel --prod --yes
cd ..

echo ""
echo "================================"
echo "✅ Deployment complete!"
echo ""
echo "  Backend:  $BACKEND_URL"
echo "  Frontend: Check Vercel output above"
echo ""
echo "  Re-run Vapi setup with the new backend URL:"
echo "    BACKEND_URL=$BACKEND_URL python voice/setup_vapi.py"
