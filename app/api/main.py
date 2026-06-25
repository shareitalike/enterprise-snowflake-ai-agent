from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.agent.graph import agent_executor
from langchain_core.messages import HumanMessage
import os
from dotenv import load_dotenv
from app.utils.db import SnowflakeDB

load_dotenv()

app = FastAPI(
    title="Enterprise Snowflake Intelligence Agent API",
    description="API for querying enterprise data assets in Snowflake via an agentic workflow.",
    version="1.0.0"
)

class QueryRequest(BaseModel):
    query: str

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
        # Initialize state with the user's message
        initial_state = {
            "messages": [HumanMessage(content=req.query)],
            "intent": [],
            "plan": "",
            "evidence": [],
            "validation_status": "",
            "final_response": ""
        }
        
        # Execute the LangGraph workflow
        result = agent_executor.invoke(initial_state)
        
        return QueryResponse(
            response=result["final_response"],
            intents=result["intent"],
            plan=result["plan"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
