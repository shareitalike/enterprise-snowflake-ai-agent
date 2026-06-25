# Enterprise Snowflake Intelligence Agent - Runbook

## 1. Overview and Purpose
The Enterprise Snowflake Intelligence Agent is a state-of-the-art AI microservice designed to help users discover, understand, govern, and analyze enterprise data assets in Snowflake. 

Unlike standard conversational chatbots or linear Retrieval-Augmented Generation (RAG) applications, this agent uses an **Agentic Workflow** to autonomously plan, execute tools, retrieve live data from Snowflake, and validate its own findings before responding. This eliminates AI hallucinations and ensures 100% traceability for enterprise governance.

---

## 2. Core Design Decisions

### 2.1 LangGraph over Linear RAG
*   **Decision:** We utilized `LangGraph` to build the agent as a state machine rather than a simple LangChain pipeline.
*   **Reasoning:** Enterprise data questions are complex (e.g., "What is the lineage of the sales table and who owns it?"). A linear RAG model cannot handle multi-step reasoning reliably. LangGraph forces the agent into a cyclical loop: **Intent Classification -> Planning -> Tool Execution -> Validation**. If the agent does not find sufficient evidence, it is explicitly programmed to stop and report "No Access" rather than guessing.

### 2.2 Tool Abstraction vs. Direct LLM SQL Generation
*   **Decision:** The AI is not allowed to write arbitrary SQL to query Snowflake metadata. Instead, it is given strict python tools (e.g., `MetadataTool`, `GovernanceTool`).
*   **Reasoning:** Security and determinism. By abstracting the SQL into predefined Python tools inside `app/agent/tools.py`, we prevent prompt injection or accidental destructive queries. The LLM only decides *which* tool to call and with *what* parameters.

### 2.3 Least-Privilege Architecture
*   **Decision:** The Snowflake connection (`app/utils/db.py`) catches `snowflake.connector.errors.ProgrammingError` natively.
*   **Reasoning:** In an enterprise, the agent will likely run under a role that does not have `ACCOUNTADMIN`. When it tries to query `SNOWFLAKE.ACCOUNT_USAGE` (for lineage) and fails, the application does not crash. Instead, it catches the error and returns a structured JSON payload to the LLM: `{"status": "error", "message": "No Access..."}`. The LLM understands this and politely informs the user that it lacks the permissions to view that specific data.

### 2.4 API-First Design
*   **Decision:** Wrapped the LangGraph execution engine in **FastAPI**.
*   **Reasoning:** To be production-ready, AI models must be accessible as microservices. FastAPI provides an asynchronous, highly performant REST endpoint (`POST /query`) that can be consumed by Slack bots, internal portals, or our Streamlit UI.

---

## 3. Setup and Configuration

### 3.1 Prerequisites
*   Python 3.10+
*   Snowflake Account (with appropriate role access)

### 3.2 Environment Variables
Create a `.env` file in the root directory by copying `.env.example`:
```bash
cp .env.example .env
```
Fill in the following required variables:
*   `SNOWFLAKE_ACCOUNT`
*   `SNOWFLAKE_USER`
*   `SNOWFLAKE_PASSWORD`
*   `SNOWFLAKE_ROLE`
*   `SNOWFLAKE_WAREHOUSE`
*   `SNOWFLAKE_DATABASE`
*   `SNOWFLAKE_SCHEMA`

*(Optional)* If you have a custom Business Glossary table, configure:
*   `BUSINESS_GLOSSARY_DATABASE`
*   `BUSINESS_GLOSSARY_SCHEMA`
*   `BUSINESS_GLOSSARY_TABLE`

---

## 4. Operational Procedures

### 4.1 Starting the Services
The application is split into a Backend API and a Frontend UI.

**Terminal 1 (Start the API):**
```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```
*The API Swagger documentation will be available at `http://localhost:8000/docs`.*

**Terminal 2 (Start the UI):**
```bash
streamlit run app/ui/streamlit_app.py
```
*The Streamlit interface will open in your browser at `http://localhost:8501`.*

### 4.2 Health Checks
To verify that the API is running and can successfully authenticate with Snowflake using the provided `.env` credentials, call the health endpoint:
```bash
curl http://localhost:8000/health/snowflake
```
**Expected Output (Healthy):**
```json
{
  "status": "healthy",
  "context": {
    "ACCOUNT": "your_account",
    "USER": "your_user",
    "ROLE": "your_role",
    "WAREHOUSE": "your_warehouse",
    "DATABASE": "your_database",
    "SCHEMA": "your_schema"
  }
}
```

---

## 5. Troubleshooting Guide

### 5.1 API Fails to Start (ModuleNotFoundError)
*   **Cause:** Python dependencies are not installed in your current environment.
*   **Fix:** Ensure you are in your virtual environment and run `pip install -r requirements.txt`.

### 5.2 Snowflake Health Check Returns "unhealthy"
*   **Cause:** Incorrect credentials in `.env`, or network rules blocking the connection to Snowflake.
*   **Fix:** Verify the variables in `.env`. If using SSO or external browser auth in your company, the standard PASSWORD auth method in `app/utils/db.py` may need to be updated to support `authenticator='externalbrowser'`.

### 5.3 Agent States "No Access" for Lineage or Governance Queries
*   **Cause:** The role defined in `SNOWFLAKE_ROLE` does not have access to the `SNOWFLAKE.ACCOUNT_USAGE` schema.
*   **Fix:** This is expected behavior based on our Least-Privilege design. To fix it, you must grant the agent's role the `GOVERNANCE_VIEWER` role or `ACCOUNTADMIN` in Snowflake.
    ```sql
    GRANT DATABASE ROLE SNOWFLAKE.GOVERNANCE_VIEWER TO ROLE <your_agent_role>;
    ```

### 5.4 Streamlit Shows "ConnectionError"
*   **Cause:** The Streamlit UI cannot reach the FastAPI backend.
*   **Fix:** Ensure `uvicorn app.api.main:app` is actively running in another terminal window on port 8000.

---

## 6. Future Enhancements & Roadmap
*   **Key-Pair Authentication:** Abstracted in `app/utils/db.py`. Update to load the `.p8` private key file for non-password service account authentication.
*   **Snowpark Integration:** Transitioning `SnowflakeDB.execute_query` from the standard Python connector to Snowpark DataFrames for heavier data profiling tasks.
*   **Agent Memory:** Implement `langgraph.checkpoint.sqlite.SqliteSaver` to give the agent long-term memory across different user sessions.
