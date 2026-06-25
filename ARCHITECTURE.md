# Architectural Decisions: Enterprise Snowflake Intelligence Agent

## Overview
In the modern AI world, large language models (LLMs) are transitioning from simple conversational chatbots to autonomous "Agents" capable of taking actions, using tools, and reasoning through multi-step processes. 

This project implements an **Agentic Workflow** specifically designed for enterprise data stacks (Snowflake). It prioritizes deterministic behavior, strict evidence hierarchies, and hallucination prevention, which are critical in a corporate environment.

## 1. Agent Orchestration: LangGraph vs. Simple RAG
### The Problem with RAG
Standard Retrieval-Augmented Generation (RAG) is a linear process: Retrieve -> Generate. This is insufficient for complex enterprise data queries which often require multiple steps (e.g., finding the table -> understanding the business definition -> generating SQL -> validating the result).

### The Solution: LangGraph
We use **LangGraph** to model the agent as a state machine (a cyclic graph). This allows us to implement a rigid, multi-stage workflow:
1.  **Intent Classification**: Determines what tools are needed.
2.  **Planning**: Formulates a strategy.
3.  **Tool Execution**: Interacts with external systems (Snowflake).
4.  **Validation**: Checks if the retrieved data fully answers the query or if more tools need to be called.

This cyclical reasoning loop closely mirrors how a human data engineer investigates an issue.

## 2. API Layer: FastAPI
To make this agent production-ready, it cannot just be a Python script. It must be a microservice.
*   **FastAPI** was chosen because it is highly performant, natively supports asynchronous operations (essential for LLM calls and database queries), and automatically generates OpenAPI documentation.
*   This allows other enterprise applications (like an internal portal or a Slack bot) to seamlessly consume the agent's capabilities.

## 3. Tooling and Snowflake Integration
The agent relies on a "Tooling Layer" rather than raw access to Snowflake.
*   **Separation of Concerns**: Tools (e.g., `MetadataTool`, `GovernanceTool`) abstract the complex SQL required to fetch metadata (like parsing `INFORMATION_SCHEMA`).
*   **Safety**: By restricting the agent to specific, read-only tools, we prevent destructive operations (DROP, ALTER) natively.
*   **Snowpark**: The architecture is designed to support Snowflake Snowpark, allowing for secure, scalable data operations directly within the Snowflake compute environment if needed.

## 4. Frontend: Streamlit
*   **Streamlit** is the industry standard for rapidly prototyping and deploying data/AI applications. It allows us to build a chat interface that can easily render complex responses, including markdown, data tables, and structured evidence.

## Conclusion
By combining the reasoning capabilities of LLMs with the structured state management of LangGraph and the robust compute of Snowflake, we create an AI agent that is not just smart, but safe, reliable, and deeply integrated into the enterprise data workflow.
