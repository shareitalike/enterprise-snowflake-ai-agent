# Enterprise Snowflake Intelligence Agent

This repository contains the source code for the Enterprise Snowflake Intelligence Agent, an evidence-driven, retrieval-first AI agent designed for querying, discovering, and governing enterprise data assets in Snowflake.

## Features

- **Agentic Workflow**: Utilizes LangGraph for a strict Intent Classification -> Routing -> Planning -> Retrieval -> Validation loop.
- **Evidence-Driven**: The agent refuses to hallucinate and strictly relies on retrieved metadata and data.
- **Tools**: Includes tools for Metadata, Documentation, Lineage, Governance, Cortex Search, SQL Generation, and Query Execution.
- **Production Ready**: Built with a FastAPI backend and a Streamlit frontend for demonstration.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Create a `.env` file in the root directory with the following variables:
   ```env
   OPENAI_API_KEY=your_openai_api_key
   SNOWFLAKE_ACCOUNT=your_account
   SNOWFLAKE_USER=your_user
   SNOWFLAKE_PASSWORD=your_password
   SNOWFLAKE_ROLE=your_role
   SNOWFLAKE_WAREHOUSE=your_warehouse
   SNOWFLAKE_DATABASE=your_database
   SNOWFLAKE_SCHEMA=your_schema
   ```

3. **Run the API (Backend)**:
   ```bash
   uvicorn app.api.main:app --reload
   ```

4. **Run the UI (Frontend)**:
   ```bash
   streamlit run app/ui/streamlit_app.py
   ```

## Architecture

```mermaid
graph TD
    %% Define Styles
    classDef frontend fill:#ff4b4b,stroke:#fff,stroke-width:2px,color:#fff
    classDef backend fill:#009688,stroke:#fff,stroke-width:2px,color:#fff
    classDef langgraph fill:#673ab7,stroke:#fff,stroke-width:2px,color:#fff
    classDef llm fill:#f39c12,stroke:#fff,stroke-width:2px,color:#fff
    classDef snowflake fill:#29b5e8,stroke:#fff,stroke-width:2px,color:#fff
    
    %% Frontend Layer
    subgraph UI ["Frontend (Streamlit)"]
        A[User Chat Interface]:::frontend
        B[Session Manager <br/>UUID Generation]:::frontend
    end
    
    %% API Layer
    subgraph API ["Backend (FastAPI)"]
        C[REST API Endpoint <br/>/query]:::backend
        D[Pydantic Validation]:::backend
    end
    
    %% AI Orchestration Layer
    subgraph Core ["LangGraph Orchestration"]
        E[Agent State <br/>Messages, Context]:::langgraph
        F[MemorySaver <br/>Thread Checkpointing]:::langgraph
        
        G((agent_decide)):::langgraph
        H{should_continue?}:::langgraph
        I((execute_tools)):::langgraph
    end
    
    %% LLM Layer
    subgraph Models ["LLM Provider (Factory)"]
        J[Local LLaMA 3.2 <br/>Ollama]:::llm
        K[OpenAI gpt-4o <br/>Fallback]:::llm
    end
    
    %% Tool Layer & DB
    subgraph Data ["Data & Execution"]
        L[Tools: Metadata, Lineage, <br/>Data Quality, Governance]:::backend
        M[(Snowflake DB <br/>Key-Pair Auth)]:::snowflake
    end

    %% Flows
    A -- "Natural Language Query" --> B
    B -- "Query + session_id" --> C
    C --> D
    D --> E
    
    E -- "Invoke Graph" --> G
    
    %% LLM Binding
    G -- "bind_tools()" --> J
    G -. "bind_tools()" .-> K
    
    J -- "Structured JSON Tool Call" --> G
    
    %% Graph Logic
    G --> H
    H -- "Tool Calls Found" --> I
    I -- "Invoke Tool" --> L
    L -- "Execute Parameterized SQL" --> M
    M -- "Return Evidence (JSON)" --> L
    L -- "ToolMessage" --> E
    E -- "Loop Back" --> G
    
    H -- "No Tool Calls" --> N[Final Response generated]:::backend
    N -- "Return QueryResponse" --> C
    C -- "HTTP 200 OK" --> A
```
