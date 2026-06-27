from typing import TypedDict, Annotated, Sequence, List
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """
    The state of our LangGraph agent. 
    This holds the conversation history and the specific context 
    needed for the Snowflake Intelligence Agent workflow.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    intent: List[str]
    plan: str
    evidence: List[dict]
    validation_status: str
    final_response: str
    session_id: str
    tool_calls: List[dict]
