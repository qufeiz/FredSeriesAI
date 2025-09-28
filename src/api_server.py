import logging
from typing import List, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
from retrieval_graph.graph import graph

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Query(BaseModel):
    text: str
    conversation: List[Dict[str, str]] = []
    user_id: str = "default_user"


@app.get("/")
async def root():
    return {"message": "LangGraph backend is running", "status": "healthy"}


@app.post("/ask")
async def ask(query: Query):
    logger.info(f"Query from user {query.user_id}: {query.text[:100]}...")

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
            {"messages": messages},
            {"configurable": {"user_id": query.user_id}}
        )

        for message in reversed(result["messages"]):
            if hasattr(message, 'content') and message.content:
                logger.info(f"Response sent to user {query.user_id}")
                return {"response": message.content}

        logger.warning(f"No response generated for user {query.user_id}")
        return {"response": "No response"}

    except Exception as e:
        logger.error(f"Error processing query for user {query.user_id}: {e}")
        return {"response": f"Error: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)