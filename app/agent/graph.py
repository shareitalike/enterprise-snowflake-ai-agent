from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from app.agent.state import AgentState
from app.agent.prompts import SYSTEM_PROMPT, INTENT_CLASSIFICATION_PROMPT, PLANNING_PROMPT
from app.agent.tools import TOOLS
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
import os

# Initialize LLM based on environment configuration
llm_provider = os.getenv("LLM_PROVIDER", "OLLAMA").upper()

try:
    if llm_provider == "OPENAI":
        # Uses OPENAI_API_KEY from environment
        llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
        print("Initialized LLM using OpenAI.")
    else:
        # Default to local Ollama
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        llm = ChatOllama(model=ollama_model, base_url=ollama_base_url, temperature=0)
        print(f"Initialized LLM using Local Ollama ({ollama_model}).")
except Exception as e:
    print(f"Warning: Could not initialize LLM. Error: {e}")

def classify_intent(state: AgentState):
    """Step 1: Classify the user's intent using Local LLaMA."""
    last_message = state["messages"][-1].content
    prompt = INTENT_CLASSIFICATION_PROMPT + f"\n\nUser Request: {last_message}"
    
    try:
        response = llm.invoke(prompt)
        # Parse comma separated intents
        intent_list = [i.strip() for i in response.content.split(",")]
    except:
        intent_list = ["Data Exploration"] # Fallback
        
    return {"intent": intent_list}

def plan_execution(state: AgentState):
    """Step 2: Plan which tools to use using Local LLaMA."""
    intents = ", ".join(state.get("intent", []))
    prompt = PLANNING_PROMPT.format(intents=intents)
    
    try:
        response = llm.invoke(prompt)
        plan = response.content
    except:
        plan = "Execute MetadataTool" # Fallback
        
    return {"plan": plan}

def execute_tools(state: AgentState):
    """Step 3 & 4: Retrieve evidence using tools."""
    last_message = state["messages"][-1].content
    plan = state.get("plan", "").lower()
    evidence = []
    
    # Very basic routing based on the plan text
    # In a production setup, you would use function calling (if supported by your local model)
    from app.agent.tools import metadata_tool, documentation_tool, lineage_tool, governance_tool, data_quality_tool
    
    if "metadata" in plan or "table" in plan:
        res = metadata_tool.invoke(last_message)
        evidence.append({"tool": "MetadataTool", "result": res})
    
    if "documentation" in plan or "definition" in plan or "glossary" in plan:
        res = documentation_tool.invoke(last_message)
        evidence.append({"tool": "DocumentationTool", "result": res})
        
    if "lineage" in plan or "upstream" in plan or "downstream" in plan:
        res = lineage_tool.invoke(last_message)
        evidence.append({"tool": "LineageTool", "result": res})
        
    if "governance" in plan or "owner" in plan or "policy" in plan or "tag" in plan:
        res = governance_tool.invoke(last_message)
        evidence.append({"tool": "GovernanceTool", "result": res})
        
    if "quality" in plan or "count" in plan or "null" in plan:
        res = data_quality_tool.invoke(last_message)
        evidence.append({"tool": "DataQualityTool", "result": res})
        
    # If plan didn't explicitly match, run metadata as default safeguard
    if not evidence:
        res = metadata_tool.invoke(last_message)
        evidence.append({"tool": "MetadataTool (Fallback)", "result": res})
        
    return {"evidence": evidence}

def validate_and_respond(state: AgentState):
    """Step 5: Validate evidence and generate response using Local LLaMA."""
    evidence = state.get("evidence", [])
    last_message = state["messages"][-1].content
    
    if not evidence or all("No Access" in str(e["result"]) or "error" in str(e["result"]).lower() for e in evidence):
        response = "No supporting evidence was found, or access was denied due to least-privilege policies."
    else:
        # Build prompt with evidence
        formatted_evidence = "\n".join([f"Tool: {e['tool']}\nResult: {e['result']}" for e in evidence])
        prompt = f"""
        User Question: {last_message}
        
        Retrieved Evidence from Snowflake:
        {formatted_evidence}
        
        Using ONLY the evidence above, generate a final response following the Response Format rules (Business Summary, Technical Details, Evidence, Confidence).
        """
        
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]
        
        try:
            llm_response = llm.invoke(messages)
            response = llm_response.content
        except:
            # Fallback if local LLM fails
            response = f"## Evidence Retrieved\n\n{formatted_evidence}\n\n*Note: Local LLM failed to generate a formatted summary.*"
        
    return {"final_response": response, "validation_status": "Complete"}

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
