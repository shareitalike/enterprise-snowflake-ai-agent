from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from app.agent.state import AgentState
from app.agent.prompts import SYSTEM_PROMPT, INTENT_CLASSIFICATION_PROMPT
from app.agent.tools import TOOLS
from langchain_openai import ChatOpenAI
import os

# Initialize LLM
# In a real app, this is configured via env vars
# llm = ChatOpenAI(temperature=0) 

def classify_intent(state: AgentState):
    """Step 1: Classify the user's intent."""
    last_message = state["messages"][-1].content
    # MOCK: In reality, call the LLM with INTENT_CLASSIFICATION_PROMPT
    intent = ["Table Discovery"] if "table" in last_message.lower() else ["Documentation Search"]
    return {"intent": intent}

def plan_execution(state: AgentState):
    """Step 2: Plan which tools to use."""
    # MOCK: Determine tools based on intent
    plan = "Plan: Execute MetadataTool"
    return {"plan": plan}

def execute_tools(state: AgentState):
    """Step 3 & 4: Retrieve evidence using tools."""
    last_message = state["messages"][-1].content
    evidence = []
    
    # We map string intents/plans to actual python functions in TOOLS
    # For this demo, we'll just force the metadata tool if table is requested
    if "Table Discovery" in state["intent"]:
        from app.agent.tools import metadata_tool
        result = metadata_tool.invoke(last_message)
        evidence.append({"tool": "MetadataTool", "result": result})
        
    return {"evidence": evidence}

def validate_and_respond(state: AgentState):
    """Step 5: Validate evidence and generate response."""
    evidence = state.get("evidence", [])
    if not evidence or all("No metadata" in e["result"] for e in evidence):
        response = "No supporting evidence was found."
    else:
        # MOCK: Build the formatted response based on the SYSTEM_PROMPT format
        formatted_evidence = "\n".join([f"**{e['tool']}**: {e['result']}" for e in evidence])
        response = f"## Business Summary\nFound relevant data based on your request.\n\n## Evidence\n{formatted_evidence}\n\n## Confidence\nHigh"
        
    return {"final_response": response, "validation_status": "Valid"}

def build_graph():
    """Constructs the LangGraph."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("classify", classify_intent)
    workflow.add_node("plan", plan_execution)
    workflow.add_node("execute", execute_tools)
    workflow.add_node("respond", validate_and_respond)
    
    # Define edges
    workflow.set_entry_point("classify")
    workflow.add_edge("classify", "plan")
    workflow.add_edge("plan", "execute")
    workflow.add_edge("execute", "respond")
    workflow.add_edge("respond", END)
    
    return workflow.compile()

# The compiled graph
agent_executor = build_graph()
