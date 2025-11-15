# test_agents.py
# Test script to verify all agents work

import asyncio
import sys
from main import Orchestrator

async def test_agents():
    """Test that all agents can execute tasks"""
    
    orchestrator = Orchestrator()
    
    print("🧪 Testing all agents...")
    print(f"📊 Total agents: {len(orchestrator.agents)}")
    print()
    
    # Test each agent with a simple task
    for role, agent in orchestrator.agents.items():
        print(f"Testing {role.value}...", end=" ")
        try:
            result = await agent.execute(
                "test-project",
                f"Provide a brief description of your role as {role.value}",
                {}
            )
            if result.success:
                print("✅")
            else:
                print("❌")
        except Exception as e:
            print(f"❌ Error: {str(e)[:50]}")
    
    print()
    print("✅ Agent testing complete!")

if __name__ == "__main__":
    asyncio.run(test_agents())

