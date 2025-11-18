#!/usr/bin/env python3
"""
Test script specifically for React + Node.js todo app
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.append('.')

from main import SessionLocal, Project, ProjectFile, AgentLog, Orchestrator

async def test_react_node_app():
    """Test building a React + Node.js todo app specifically"""
    print("🧪 Testing React + Node.js Todo App...")
    
    # Create test project
    db = SessionLocal()
    try:
        # Clean up any existing test projects
        db.query(ProjectFile).filter(ProjectFile.project_id.like("react-node-test-%")).delete()
        db.query(AgentLog).filter(AgentLog.project_id.like("react-node-test-%")).delete()
        db.query(Project).filter(Project.id.like("react-node-test-%")).delete()
        db.commit()
        
        # Create new test project with specific requirements
        test_id = f"react-node-test-{int(datetime.now().timestamp())}"
        test_project = Project(
            id=test_id,
            name="React Node Todo App",
            description="Build a simple todo application with React frontend and Node.js backend. Use React with hooks for frontend, Node.js with Express for backend, and SQLite for database.",
            status="testing"
        )
        db.add(test_project)
        db.commit()
        
        print(f"✅ Test project created: {test_id}")
        print("📋 Specific requirements: React frontend + Node.js backend")
        
        # Initialize orchestrator
        orchestrator = Orchestrator()
        
        print("🚀 Starting specialized agent tests...")
        
        # Test key agents with specific focus
        test_agents = [
            ("ProductManager", "Create user stories and requirements for a React + Node.js todo app"),
            ("SystemArchitect", "Design system architecture using React frontend, Node.js backend, and SQLite database"),
            ("FrontendEngineer", "Create React components for todo app with modern hooks and state management"),
            ("BackendEngineer", "Build Node.js Express API endpoints for todo CRUD operations")
        ]
        
        for agent_name, task in test_agents:
            print(f"📋 Testing {agent_name}...")
            try:
                agent = orchestrator.agents[agent_name]
                result = await agent.execute(test_id, task, {})
                print(f"   Result: {'✅ Success' if result.success else '❌ Failed'}")
                if result.success:
                    print(f"   Output preview: {result.output[:100]}...")
                    print(f"   Files created: {len(result.files)}")
                    # Show file names
                    for file_path in result.files.keys():
                        print(f"      - {file_path}")
                else:
                    print(f"   Error: {result.output}")
            except Exception as e:
                print(f"   ❌ Agent error: {e}")
        
        # Check final results
        files = db.query(ProjectFile).filter_by(project_id=test_id).all()
        logs = db.query(AgentLog).filter_by(project_id=test_id).all()
        
        print(f"\n📊 Final Results:")
        print(f"   Total files created: {len(files)}")
        print(f"   Log entries: {len(logs)}")
        
        # Show all generated files
        print(f"\n📁 All Generated Files:")
        for file in files:
            print(f"   • {file.file_path}")
            
        # Check for React/Node.js specific files
        react_files = [f for f in files if 'react' in f.file_path.lower() or '.jsx' in f.file_path or '.tsx' in f.file_path]
        node_files = [f for f in files if 'node' in f.file_path.lower() or 'express' in f.file_path.lower() or 'package.json' in f.file_path]
        
        print(f"\n🔍 Technology Stack Check:")
        print(f"   React files: {len(react_files)}")
        print(f"   Node.js files: {len(node_files)}")
        
        if len(react_files) > 0 and len(node_files) > 0:
            print("🎉 SUCCESS: React + Node.js stack detected!")
        else:
            print("⚠️  WARNING: May not be using requested technology stack")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_react_node_app())
    
    