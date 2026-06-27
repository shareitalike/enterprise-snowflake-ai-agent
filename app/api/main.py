from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.agent.graph import agent_executor
from langchain_core.messages import HumanMessage
import os
import uuid
import logging
from dotenv import load_dotenv
from app.utils.db import SnowflakeDB

# Configure global logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("snowflake_agent.api")

load_dotenv()

app = FastAPI(
    title="Enterprise Snowflake Intelligence Agent API",
    description="API for querying enterprise data assets in Snowflake via an agentic workflow.",
    version="1.0.0"
)

class QueryRequest(BaseModel):
    query: str
    session_id: str = None

class QueryResponse(BaseModel):
    response: str
    intents: list[str]
    plan: str

@app.get("/")
def read_root():
    return {"status": "Agent API is running"}

@app.get("/health/snowflake")
def snowflake_health():
    """Validates connectivity and active session context in Snowflake."""
    query = """
        SELECT 
            CURRENT_ACCOUNT() AS account,
            CURRENT_USER() AS user,
            CURRENT_ROLE() AS role,
            CURRENT_WAREHOUSE() AS warehouse,
            CURRENT_DATABASE() AS database,
            CURRENT_SCHEMA() AS schema
    """
    res = SnowflakeDB.execute_query(query)
    
    if res.get("status") == "success":
        return {"status": "healthy", "context": res["data"][0]}
    else:
        return {"status": "unhealthy", "error": res}

@app.post("/query", response_model=QueryResponse)
async def process_query(req: QueryRequest):
    try:
        session_id = req.session_id or str(uuid.uuid4())
        logger.info(f"Processing query for session_id: {session_id}")
        
        # Initialize state with the user's message
        initial_state = {
            "messages": [HumanMessage(content=req.query)],
            "intent": [],
            "plan": "",
            "evidence": [],
            "validation_status": "",
            "final_response": "",
            "session_id": session_id,
            "tool_calls": []
        }
        
        # Execute the LangGraph workflow with memory thread_id
        config = {"configurable": {"thread_id": session_id}}
        result = agent_executor.invoke(initial_state, config=config)
        
        logger.info(f"Query completed for session_id: {session_id}")
        
        return QueryResponse(
            response=result.get("final_response", "No response generated."),
            intents=result.get("intent", []),
            plan=result.get("plan", "")
        )
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
