#!/usr/bin/env bash
# Запуск: middleware на :4000 + LiteLLM на :4001

set -e

if [ -z "$GROQ_API_KEY" ]; then
  echo "❌ GROQ_API_KEY не задан!"
  echo "   export GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxx"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Запускаем LiteLLM на порту 4001 в фоне
echo "▶ Запуск LiteLLM на http://localhost:4001 ..."
litellm --config litellm_config.yaml --port 4001 &
LITELLM_PID=$!

# Даём LiteLLM стартовать
sleep 3

echo "▶ Запуск middleware на http://localhost:4000 ..."
echo ""
echo "В другом терминале задай:"
echo "   export ANTHROPIC_BASE_URL=http://localhost:4000"
echo "   export ANTHROPIC_API_KEY=sk-local-proxy"
echo "   claude"
echo ""

# Останавливаем LiteLLM при выходе
trap "kill $LITELLM_PID 2>/dev/null" EXIT

python3 middleware.py
