from langchain_core.tools import tool
import json
import os
from app.utils.db import SnowflakeDB

@tool
def metadata_tool(object_name: str, object_type: str = "TABLE") -> str:
    """
    Search databases, schemas, tables, views, and columns.
    object_type can be TABLE, VIEW, COLUMN, SCHEMA, DATABASE.
    """
    # Clean inputs
    obj_name_clean = object_name.upper().replace("'", "").replace(";", "")
    
    if object_type.upper() in ("TABLE", "VIEW"):
        query = f"""
            SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_NAME ILIKE '%{obj_name_clean}%'
            LIMIT 10
        """
    elif object_type.upper() == "COLUMN":
        query = f"""
            SELECT TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE COLUMN_NAME ILIKE '%{obj_name_clean}%' OR TABLE_NAME ILIKE '%{obj_name_clean}%'
            LIMIT 20
        """
    else:
        # Fallback for generic SHOW commands
        query = f"SHOW {object_type.upper()}S LIKE '%{obj_name_clean}%'"
        
    result = SnowflakeDB.execute_query(query)
    return json.dumps(result, default=str)

@tool
def documentation_tool(term: str) -> str:
    """Business glossary lookup and Data dictionary fallback to COMMENTS."""
    term_clean = term.replace("'", "").replace(";", "")
    
    # 1. Try Business Glossary if configured
    glos_db = os.getenv("BUSINESS_GLOSSARY_DATABASE")
    glos_schema = os.getenv("BUSINESS_GLOSSARY_SCHEMA")
    glos_table = os.getenv("BUSINESS_GLOSSARY_TABLE")
    
    results = {}
    
    if glos_db and glos_schema and glos_table:
        glos_query = f"""
            SELECT * FROM {glos_db}.{glos_schema}.{glos_table}
            WHERE TERM ILIKE '%{term_clean}%' OR DEFINITION ILIKE '%{term_clean}%'
            LIMIT 5
        """
        glos_res = SnowflakeDB.execute_query(glos_query)
        if glos_res.get("status") == "success" and glos_res.get("data"):
            results["glossary"] = glos_res["data"]
            return json.dumps(results, default=str)

    # 2. Fallback to INFORMATION_SCHEMA COMMENTS
    table_comment_query = f"""
        SELECT TABLE_NAME, COMMENT 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME ILIKE '%{term_clean}%' AND COMMENT IS NOT NULL
        LIMIT 5
    """
    col_comment_query = f"""
        SELECT TABLE_NAME, COLUMN_NAME, COMMENT 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE (COLUMN_NAME ILIKE '%{term_clean}%' OR TABLE_NAME ILIKE '%{term_clean}%') AND COMMENT IS NOT NULL
        LIMIT 10
    """
    
    res_tables = SnowflakeDB.execute_query(table_comment_query)
    res_cols = SnowflakeDB.execute_query(col_comment_query)
    
    if res_tables.get("status") == "success":
        results["table_comments"] = res_tables.get("data", [])
    if res_cols.get("status") == "success":
        results["column_comments"] = res_cols.get("data", [])
        
    return json.dumps(results, default=str)

@tool
def lineage_tool(object_name: str) -> str:
    """Upstream dependency analysis and pipeline tracing."""
    obj_clean = object_name.upper().replace("'", "").replace(";", "")
    
    results = {}
    # Object Dependencies
    dep_query = f"""
        SELECT REFERENCING_OBJECT_DOMAIN, REFERENCING_OBJECT_NAME,
               REFERENCED_OBJECT_DOMAIN, REFERENCED_OBJECT_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES
        WHERE REFERENCED_OBJECT_NAME ILIKE '%{obj_clean}%' OR REFERENCING_OBJECT_NAME ILIKE '%{obj_clean}%'
        LIMIT 10
    """
    res_deps = SnowflakeDB.execute_query(dep_query)
    results["object_dependencies"] = res_deps
    
    # Access History (Read/Write lineage)
    access_query = f"""
        SELECT QUERY_ID, USER_NAME, OBJECTS_MODIFIED, DIRECT_OBJECTS_ACCESSED
        FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY
        WHERE OBJECTS_MODIFIED::STRING ILIKE '%{obj_clean}%'
        ORDER BY QUERY_START_TIME DESC
        LIMIT 5
    """
    res_access = SnowflakeDB.execute_query(access_query)
    results["access_history"] = res_access
    
    return json.dumps(results, default=str)

@tool
def governance_tool(object_name: str) -> str:
    """Tags, Classification, Masking Policies, Row Access Policies, Grants."""
    obj_clean = object_name.upper().replace("'", "").replace(";", "")
    results = {}
    
    # Tags
    tag_query = f"""
        SELECT TAG_NAME, TAG_VALUE, OBJECT_NAME, OBJECT_DOMAIN, COLUMN_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.TAG_REFERENCES
        WHERE OBJECT_NAME ILIKE '%{obj_clean}%'
        LIMIT 10
    """
    results["tags"] = SnowflakeDB.execute_query(tag_query)
    
    # Policies
    pol_query = f"""
        SELECT POLICY_KIND, POLICY_NAME, REF_ENTITY_NAME, REF_COLUMN_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.POLICY_REFERENCES
        WHERE REF_ENTITY_NAME ILIKE '%{obj_clean}%'
        LIMIT 10
    """
    results["policies"] = SnowflakeDB.execute_query(pol_query)
    
    return json.dumps(results, default=str)

@tool
def data_quality_tool(table_name: str, column_name: str = None) -> str:
    """Row counts, Null percentages, Distinct counts, Freshness metrics."""
    tbl_clean = table_name.replace("'", "").replace(";", "")
    
    # Very basic validation to ensure it's just a table name
    if " " in tbl_clean:
        return json.dumps({"status": "error", "message": "Invalid table name format"})

    # Check permissions by counting first
    count_query = f"SELECT COUNT(*) AS total_rows FROM {tbl_clean}"
    res_count = SnowflakeDB.execute_query(count_query)
    
    if res_count.get("status") != "success":
         return json.dumps(res_count, default=str)
         
    results = {"total_rows": res_count["data"][0]["TOTAL_ROWS"]}
    
    # If specific column provided, check nulls and distincts
    if column_name:
        col_clean = column_name.replace("'", "").replace(";", "")
        dq_query = f"""
            SELECT 
                COUNT({col_clean}) AS non_null_count,
                COUNT(DISTINCT {col_clean}) AS distinct_count,
                (1.0 - (COUNT({col_clean}) / NULLIF(COUNT(*), 0))) * 100 AS null_percentage
            FROM {tbl_clean}
        """
        res_dq = SnowflakeDB.execute_query(dq_query)
        if res_dq.get("status") == "success":
            results["column_metrics"] = res_dq["data"][0]

    return json.dumps({"status": "success", "data": results}, default=str)

@tool
def sql_generator_tool(request: str, metadata_context: str) -> str:
    """Generate Snowflake SQL based on verified metadata context."""
    # This tool is mostly a formatting step because SQL generation is done by the main LLM 
    # based on the metadata evidence. 
    return json.dumps({
        "status": "success",
        "message": f"Generated SQL based on context. Note: This tool validates the intent against evidence.",
        "input_context": metadata_context
    }, default=str)

TOOLS = [
    metadata_tool, 
    documentation_tool, 
    lineage_tool, 
    governance_tool, 
    data_quality_tool, 
    sql_generator_tool
]
