import pytest
from langchain_core.messages import HumanMessage
from langsmith import expect

from retrieval_graph import graph

# live = pytest.mark.skipif(
#     os.getenv("RUN_LIVE_GRAPH_TEST") != "1",
#     reason="Live graph test disabled; set RUN_LIVE_GRAPH_TEST=1 to run",
# )


# @live
@pytest.mark.asyncio
# @unit
async def test_graph_live_roundtrip() -> None:
    """Exercise the full graph against live Bedrock/FRED if enabled."""
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Show me the latest FOMC decision")],
            "tool_call_count": 0,
        },
        {"configurable": {"user_id": "integration-test-user"}},
    )

    response = str(result["messages"][-1].content)
    expect(response.lower()).to_contain("fomc")

    assert "messages" in result
    assert result["messages"], "No AI message returned from graph"
