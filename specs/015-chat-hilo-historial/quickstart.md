# Quickstart: 015 hilo e historial

```powershell
# Backend (desde backend/, DB local de test)
.\.venv\Scripts\python.exe -m pytest tests/unit/test_chat_threads.py tests/contract/test_chat_threads_api.py tests/contract/test_chat_api.py -q

# Frontend
cd frontend
npx vitest run tests/SessionChatPanel.test.tsx
```

Migración: `alembic upgrade head` incluye `0017_chat_threads`.

Demostración grounding: redactor falso en contract tests; sin Azure de pago.
