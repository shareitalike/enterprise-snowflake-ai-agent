import os
import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from app.agent.state import AgentState
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

logger = logging.getLogger("snowflake_agent.graph")

# Initialize LLM
llm_provider = os.getenv("LLM_PROVIDER", "OLLAMA").upper()
llm_with_tools = None

try:
    if llm_provider == "OPENAI":
        llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
        logger.info("Initialized LLM using OpenAI.")
    else:
        ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        llm = ChatOllama(model=ollama_model, base_url=ollama_base_url, temperature=0)
        logger.info(f"Initialized LLM using Local Ollama ({ollama_model}).")
    
    # Bind tools for LLM Function Calling
    llm_with_tools = llm.bind_tools(TOOLS)
except Exception as e:
    logger.error(f"Could not initialize LLM. Error: {e}", exc_info=True)

def agent_decide(state: AgentState):
    """Step 1: LLM decides whether to use a tool or respond directly."""
    logger.info("agent_decide node invoked")
    messages = state["messages"]
    
    # Ensure system prompt is present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        
    try:
        response = llm_with_tools.invoke(messages)
        
        # We need to maintain compatibility with the old API contract (final_response, intent, plan)
        # We extract them manually to avoid breaking the frontend
        intents = [t["name"] for t in response.tool_calls] if hasattr(response, "tool_calls") and response.tool_calls else ["Conversation"]
        
        return {
            "messages": [response],
            "final_response": response.content,
            "intent": intents,
            "plan": "LLM Function Calling" if intents != ["Conversation"] else "Direct Response"
        }
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}", exc_info=True)
        err_msg = "Error: LLM failed to respond."
        return {
            "messages": [HumanMessage(content=err_msg)],
            "final_response": err_msg
        }

def should_continue(state: AgentState) -> str:
    """Routing logic: If tool calls exist, execute them. Otherwise, end."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info(f"LLM decided to call tools: {[t['name'] for t in last_message.tool_calls]}")
        return "execute_tools"
    logger.info("No tool calls. Ending workflow.")
    return END

def execute_tools(state: AgentState):
    """Step 2: Execute the tools requested by the LLM."""
    logger.info("execute_tools node invoked")
    last_message = state["messages"][-1]
    tool_messages = []
    
    # Map tool names to actual functions
    tool_map = {tool.name: tool for tool in TOOLS}
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        logger.info(f"Executing {tool_name} with args {tool_args}")
        
        try:
            if tool_name in tool_map:
                result = tool_map[tool_name].invoke(tool_args)
                tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
            else:
                logger.warning(f"Tool {tool_name} not found.")
                tool_messages.append(ToolMessage(content="Error: Tool not found.", tool_call_id=tool_call["id"]))
        except Exception as e:
            logger.error(f"Tool {tool_name} execution failed: {e}", exc_info=True)
            tool_messages.append(ToolMessage(content=f"Error executing tool: {e}", tool_call_id=tool_call["id"]))
            
    return {"messages": tool_messages}

def build_graph():
    """Constructs the LangGraph with memory and function calling."""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent_decide", agent_decide)
    workflow.add_node("execute_tools", execute_tools)
    
    workflow.set_entry_point("agent_decide")
    
    # Conditional routing
    workflow.add_conditional_edges(
        "agent_decide",
        should_continue,
        {"execute_tools": "execute_tools", END: END}
    )
    
    # After tools run, go back to agent to summarize/decide next steps
    workflow.add_edge("execute_tools", "agent_decide")
    
    # Add memory checkpointing using MemorySaver
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

# The compiled graph
agent_executor = build_graph()
