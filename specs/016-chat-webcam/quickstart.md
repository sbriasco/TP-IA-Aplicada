# Quickstart: 016-chat-webcam

```powershell
cd backend
$env:FLOWSIGHT_TEST_DATABASE_URL = "postgresql+psycopg://flowsight:flowsight@127.0.0.1:5432/flowsight"
.\.venv\Scripts\python.exe -m pytest tests/unit/test_chat_live_metrics.py tests/contract/test_live_results.py -q
```

```powershell
cd frontend
npx vitest run tests/LiveResultsPage.test.tsx tests/SessionChatPanel.test.tsx
```
