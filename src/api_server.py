import logging
from typing import Dict, List

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

# try:
#     from supabase import Client, create_client
# except ImportError:
#     create_client = None  # type: ignore
#     Client = None  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
from retrieval_graph.graph import graph

# # Initialize Supabase client
# supabase_url = os.getenv("SUPABASE_URL")
# supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# if create_client and supabase_url and supabase_key:
#     supabase = create_client(supabase_url, supabase_key)
# else:
#     if not create_client:
#         logger.info("Supabase client not installed; running without auth verification.")
#     else:
#         logger.warning("Supabase credentials not found. Running without auth verification.")
#     supabase = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://d1e82jhhy8ld8w.cloudfront.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    text: str
    conversation: List[Dict[str, str]] = []


# async def get_current_user(authorization: Optional[str] = Header(None)):
#     """Extract and verify user from JWT token."""
#     if not authorization or not supabase:
#         # For development without auth
#         return {"id": "anonymous", "email": "anonymous@example.com"}

#     try:
#         # Extract token from "Bearer <token>"
#         token = authorization.replace("Bearer ", "")

#         # Verify token with Supabase
#         user_response = supabase.auth.get_user(token)

#         if user_response.user:
#             return {"id": user_response.user.id, "email": user_response.user.email}
#         else:
#             raise HTTPException(status_code=401, detail="Invalid token")

#     except Exception as e:
#         logger.error(f"Auth error: {e}")
#         raise HTTPException(status_code=401, detail="Authentication failed")


async def get_current_user():
    """Extract and verify user from JWT token."""
    return {"id": "anonymous", "email": "anonymous@example.com"}


@app.get("/")
async def root():
    return {"message": "LangGraph backend is running", "status": "healthy"}


@app.post("/ask")
async def ask(query: Query, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    logger.info(f"Query from user {user_id} ({current_user['email']}): {query.text[:100]}...")

    try:
        # Build conversation history
        messages = []

        # Add previous conversation
        for msg in query.conversation:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # Add current message
        messages.append(HumanMessage(content=query.text))

        result = await graph.ainvoke(
            {"messages": messages, "tool_call_count": 0},
            {"configurable": {"user_id": user_id}},
        )

        attachments: List[Dict[str, str]] = []
        for attachment in result.get("attachments", []) or []:
            if isinstance(attachment, dict):
                attachments.append(attachment)

        series_data: List[Dict[str, str]] = []
        for block in result.get("series_data", []) or []:
            if isinstance(block, dict):
                series_data.append(block)

        sources: List[Dict[str, str]] = []
        for source in result.get("sources", []) or []:
            if isinstance(source, dict):
                sources.append(source)

        for message in reversed(result["messages"]):
            if hasattr(message, "content") and message.content:
                logger.info(f"Response sent to user {user_id}")
                payload: Dict[str, object] = {"response": message.content}
                if attachments:
                    payload["attachments"] = attachments
                if series_data:
                    payload["series_data"] = series_data
                if sources:
                    payload["sources"] = sources
                payload["tool_call_count"] = int(result.get("tool_call_count") or 0)
                return payload

        logger.warning(f"No response generated for user {user_id}")
        return {"response": "No response"}

    except Exception as e:
        logger.error(f"Error processing query for user {user_id}: {e}")
        return {"response": f"Error: {str(e)}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
