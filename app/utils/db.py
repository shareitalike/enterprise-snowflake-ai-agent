import os
import snowflake.connector
from snowflake.connector.errors import ProgrammingError
import json
from dotenv import load_dotenv

load_dotenv()

class SnowflakeDB:
    """
    Abstracts the Snowflake connection layer.
    Currently uses PASSWORD auth, but designed to be extended for KEY_PAIR based on SNOWFLAKE_AUTH_METHOD.
    """
    @staticmethod
    def get_connection():
        auth_method = os.getenv("SNOWFLAKE_AUTH_METHOD", "PASSWORD")
        
        # Base connection params
        conn_params = {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "role": os.getenv("SNOWFLAKE_ROLE"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
            "database": os.getenv("SNOWFLAKE_DATABASE"),
            "schema": os.getenv("SNOWFLAKE_SCHEMA"),
        }

        if auth_method == "PASSWORD":
            conn_params["password"] = os.getenv("SNOWFLAKE_PASSWORD")
        elif auth_method == "KEY_PAIR":
            # Future implementation: load private key bytes here
            raise NotImplementedError("KEY_PAIR auth not yet fully implemented.")
        
        return snowflake.connector.connect(**conn_params)

    @staticmethod
    def execute_query(query: str, params: tuple = None) -> dict:
        """
        Executes a query and returns structured JSON results or graceful error payload.
        Ensures least-privilege compliance by trapping permission errors.
        """
        try:
            with SnowflakeDB.get_connection() as conn:
                with conn.cursor(snowflake.connector.DictCursor) as cur:
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                    
                    results = cur.fetchall()
                    # Convert to JSON serializable list
                    # DictCursor returns rows as dicts
                    return {"status": "success", "data": results}
        except ProgrammingError as e:
            # Check for standard privilege/access errors
            if "not authorized" in str(e).lower() or "does not exist or not authorized" in str(e).lower():
                return {
                    "status": "error",
                    "error_type": "PrivilegeError",
                    "message": "No Access: The current role lacks sufficient privileges for this operation.",
                    "details": str(e)
                }
            return {
                "status": "error",
                "error_type": "DatabaseError",
                "message": "Failed to execute query.",
                "details": str(e)
            }
        except Exception as e:
            return {
                "status": "error",
                "error_type": "SystemError",
                "message": "An unexpected error occurred.",
                "details": str(e)
            }
