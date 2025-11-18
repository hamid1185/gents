#!/usr/bin/env python3
"""
Test script for NexusForge AI Agents - FIXED VERSION
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the current directory to path so we can import from main
sys.path.append('.')

try:
    from main import SessionLocal, Project, ProjectFile, AgentLog, Orchestrator
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 Make sure you're running this from the backend directory")
    sys.exit(1)

async def test_agents():
    """Test all agents with a simple project"""
    print("🧪 Testing NexusForge AI Agents...")
    
    # Create test project with unique ID
    db = SessionLocal()
    try:
        # Clean up any existing test project first
        db.query(ProjectFile).filter(ProjectFile.project_id.like("test-project-%")).delete()
        db.query(AgentLog).filter(AgentLog.project_id.like("test-project-%")).delete()
        db.query(Project).filter(Project.id.like("test-project-%")).delete()
        db.commit()
        
        # Create new test project with timestamp for uniqueness
        test_id = f"test-project-{int(datetime.now().timestamp())}"
        test_project = Project(
            id=test_id,
            name="Test Project",
            description="Build a simple todo application with React frontend and Node.js backend",
            status="testing"
        )
        db.add(test_project)
        db.commit()
        
        print(f"✅ Test project created: {test_id}")
        
        # Initialize orchestrator
        orchestrator = Orchestrator()
        
        print("🚀 Starting agent tests...")
        
        # Test a few key agents (not all to save time)
        test_agents_list = [
            ("ProductManager", "Analyze requirements for the todo app"),
            ("SystemArchitect", "Design system architecture")
        ]
        
        for agent_name, task in test_agents_list:
            print(f"📋 Testing {agent_name}...")
            try:
                agent = orchestrator.agents[agent_name]
                result = await agent.execute(
                    test_id, 
                    task,
                    {}
                )
                print(f"   Result: {'✅ Success' if result.success else '❌ Failed'}")
                if result.success:
                    print(f"   Output: {result.output[:100]}...")
                    print(f"   Files created: {len(result.files)}")
                else:
                    print(f"   Error: {result.output}")
            except Exception as e:
                print(f"   ❌ Agent error: {e}")
        
        # Check what was created
        files = db.query(ProjectFile).filter_by(project_id=test_id).all()
        logs = db.query(AgentLog).filter_by(project_id=test_id).all()
        
        print(f"\n📊 Test Results:")
        print(f"   Files created: {len(files)}")
        print(f"   Log entries: {len(logs)}")
        
        if files:
            print(f"   File examples: {[f.file_path for f in files[:3]]}")
        
        print("🎉 Agent tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        db.rollback()
    finally:
        db.close()

def quick_test():
    """Quick test without async/agents"""
    print("🧪 Quick Database Test...")
    db = SessionLocal()
    try:
        # Test basic database operations
        test_id = f"quick-test-{int(datetime.now().timestamp())}"
        
        # Create project
        project = Project(
            id=test_id,
            name="Quick Test",
            description="Quick database test"
        )
        db.add(project)
        
        # Create log
        log = AgentLog(
            project_id=test_id,
            agent_name="Test",
            message="Quick test completed"
        )
        db.add(log)
        
        db.commit()
        print("✅ Quick test passed - Database operations working")
        
        # Clean up
        db.query(AgentLog).filter_by(project_id=test_id).delete()
        db.query(Project).filter_by(id=test_id).delete()
        db.commit()
        
    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Run quick test first
    quick_test()
    
    # Then run full agent test
    asyncio.run(test_agents())