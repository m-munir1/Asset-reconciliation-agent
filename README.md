## Running it

```bash
# 1. Clone and enter the project
git clone https://github.com/m-munir1/Asset-reconciliation-agent.git
cd Asset-reconciliation-agent

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the agent on both demo assets
python3 main.py

# 5. Run a single asset
python3 main.py AST-1042

# 6. Query the full audit trail for one field
python3 main.py AST-1042 --query location

# 7. Run the test suite
python3 -m pytest tests/ -v
```

No API key is required for any of the above — the core reconciliation
logic has zero external dependencies and runs fully offline.

### Optional: enable Gemini-written summaries

```bash
export GEMINI_API_KEY="your-key-here"   # get a free key at https://aistudio.google.com/apikey
python3 main.py
```

Without a key, the "Reviewer Summary" section falls back to a plain
template built from the same structured data — nothing about the
reconciliation result depends on the LLM being available.
