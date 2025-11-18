import os
import json
import uuid
import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import redis
from dotenv import load_dotenv


# ============================================
# CONFIGURATION
# ============================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    # Try to load from .env file directly as fallback
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('GEMINI_API_KEY='):
                    GEMINI_API_KEY = line.split('=', 1)[1].strip()
                    break
    except:
        pass

if not GEMINI_API_KEY:
    print("❌ ERROR: GEMINI_API_KEY environment variable is required")
    print("💡 Please create a .env file with your Gemini API key:")
    print("   GEMINI_API_KEY=your_actual_api_key_here")

# ============================================
# DATABASE MODELS - FORCE SQLITE
# ============================================

# Use the new declarative_base import
Base = declarative_base()

# FORCE SQLITE - completely ignore any PostgreSQL settings
DATABASE_URL = "sqlite:///./nexusforge.db"
print(f"🔧 Using database: {DATABASE_URL}")

# SQLite engine with proper configuration
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False},
    echo=True  # This will show SQL queries for debugging
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="initializing")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Changed from 'metadata' to 'project_metadata'
    project_metadata = Column(JSON, default=dict)

class ProjectFile(Base):
    __tablename__ = "project_files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    content = Column(Text)
    size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    level = Column(String, default="info")
    message = Column(Text)
    # Changed from 'metadata' to 'log_metadata'
    log_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class SharedMemory(Base):
    __tablename__ = "shared_memory"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSON)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
try:
    Base.metadata.create_all(engine)
    print("✅ Database tables created successfully")
except Exception as e:
    print(f"❌ Database error: {e}")
    # If there's still an error, create a simple SQLite connection as fallback
    import sqlite3
    try:
        conn = sqlite3.connect('./nexusforge.db')
        conn.close()
        print("✅ SQLite database file created as fallback")
    except Exception as e2:
        print(f"❌ Fallback also failed: {e2}")

# ============================================
# REDIS CONNECTION
# ============================================

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    print("✅ Redis connected successfully")
except Exception as e:
    print(f"⚠️ Redis connection failed: {e}")
    redis_client = None

# ============================================
# HELPER FUNCTIONS
# ============================================

def extract_json_from_text(text: str) -> dict:
    """Extract JSON from text that may contain markdown or other content"""
    try:
        # Try direct parse first
        return json.loads(text)
    except:
        pass
    
    # Remove markdown code blocks
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # Find JSON object
    json_start = text.find('{')
    json_end = text.rfind('}') + 1
    
    if json_start >= 0 and json_end > json_start:
        json_str = text[json_start:json_end]
        try:
            return json.loads(json_str)
        except:
            pass
    
    # Return minimal structure if parsing fails
    return {
        "output": text,
        "reasoning": "Failed to parse structured response",
        "files": {},
        "next_steps": []
    }

# ============================================
# MODELS
# ============================================

class AgentRole(str, Enum):
    PRODUCT_MANAGER = "ProductManager"
    SYSTEM_ARCHITECT = "SystemArchitect"
    BACKEND_ENGINEER = "BackendEngineer"
    FRONTEND_ENGINEER = "FrontendEngineer"
    DATABASE_ENGINEER = "DatabaseEngineer"
    QA_ENGINEER = "QAEngineer"
    DEVOPS_ENGINEER = "DevOpsEngineer"
    SECURITY_ENGINEER = "SecurityEngineer"
    MOBILE_ENGINEER = "MobileEngineer"
    ML_ENGINEER = "MLEngineer"
    DOCUMENTATION_SPECIALIST = "DocumentationSpecialist"
    UX_DESIGNER = "UXDesigner"

class ProjectCreate(BaseModel):
    name: str
    description: str

class FileCreate(BaseModel):
    path: str
    content: str

class TaskResult(BaseModel):
    success: bool
    output: str
    files: Optional[Dict[str, str]] = {}
    next_steps: Optional[List[str]] = []

# ============================================
# AGENT SYSTEM
# ============================================

class Agent:
    """Base Agent class with Gemini integration"""
    
    def __init__(self, role: AgentRole, system_prompt: str):
        self.role = role
        self.system_prompt = system_prompt
        self.status = "idle"
        # Initialize Gemini only if API key is available
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                'gemini-2.0-flash',
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                }
            )
        else:
            self.model = None
    
    async def execute(self, project_id: str, task: str, context: Dict) -> TaskResult:
        """Execute a task using Gemini"""
        if not self.model:
            return TaskResult(
                success=False,
                output="Gemini API key not configured",
                files={},
                next_steps=[]
            )
            
        self.status = "working"
        db = SessionLocal()
        
        try:
            # Get shared memory
            shared_memory = db.query(SharedMemory).filter_by(project_id=project_id).all()
            memory_dict = {sm.key: sm.value for sm in shared_memory}
            
            # Build prompt
            prompt = f"""You are a {self.role.value} in an autonomous software development team.

SYSTEM CONTEXT:
{self.system_prompt}

SHARED TEAM MEMORY:
{json.dumps(memory_dict, indent=2)}

CURRENT TASK:
{task}

ADDITIONAL CONTEXT:
{json.dumps(context, indent=2)}

CRITICAL: Respond with ONLY a valid JSON object in this EXACT format:
{{
    "reasoning": "your detailed thought process and approach",
    "output": "your main deliverable (description, code, design, etc)",
    "files": {{
        "/path/to/file.ext": "complete file content here"
    }},
    "shared_memory_updates": {{
        "key_name": "value to share with team"
    }},
    "next_steps": ["recommended next step"],
    "blockers": []
}}

Generate complete, production-ready code. No placeholders, no TODOs."""

            # Call Gemini
            response = self.model.generate_content(prompt)
            text = response.text
            
            # Extract JSON from response
            result = extract_json_from_text(text)
            
            # Update shared memory
            if "shared_memory_updates" in result and result["shared_memory_updates"]:
                for key, value in result["shared_memory_updates"].items():
                    existing = db.query(SharedMemory).filter_by(
                        project_id=project_id, key=key
                    ).first()
                    
                    if existing:
                        existing.value = value
                        existing.updated_at = datetime.utcnow()
                    else:
                        new_mem = SharedMemory(
                            project_id=project_id,
                            key=key,
                            value=value
                        )
                        db.add(new_mem)
                
                db.commit()
            
            # Save generated files
            if "files" in result and result["files"]:
                for file_path, content in result["files"].items():
                    # Ensure path starts with /
                    if not file_path.startswith('/'):
                        file_path = '/' + file_path
                    
                    existing_file = db.query(ProjectFile).filter_by(
                        project_id=project_id, file_path=file_path
                    ).first()
                    
                    if existing_file:
                        existing_file.content = content
                        existing_file.size = len(content)
                        existing_file.updated_at = datetime.utcnow()
                    else:
                        new_file = ProjectFile(
                            project_id=project_id,
                            file_path=file_path,
                            content=content,
                            size=len(content)
                        )
                        db.add(new_file)
                
                db.commit()
            
            # Log success
            output_preview = result.get('output', 'Task completed')[:200]
            log = AgentLog(
                project_id=project_id,
                agent_name=self.role.value,
                level="success",
                message=f"✅ Completed: {output_preview}",
                # Updated to use log_metadata
                log_metadata={"task": task[:200]} 
                )
            db.add(log)
            db.commit()
            
            self.status = "idle"
            
            return TaskResult(
                success=True,
                output=result.get("output", ""),
                files=result.get("files", {}),
                next_steps=result.get("next_steps", [])
            )
            
        except Exception as e:
            self.status = "error"
            
            # Log error
            log = AgentLog(
                project_id=project_id,
                agent_name=self.role.value,
                level="error",
                message=f"❌ Error: {str(e)}",
                # Updated to use log_metadata
                log_metadata={"task": task[:200], "error": str(e)}
            )
            db.add(log)
            db.commit()
            
            return TaskResult(
                success=False,
                output=f"Error: {str(e)}",
                files={},
                next_steps=[]
            )
        finally:
            db.close()

# Agent implementations (same as before)
class ProductManagerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior Product Manager. Your role is to:
1. Analyze project requirements and create detailed user stories
2. Define feature specifications and acceptance criteria
3. Create product roadmap and prioritize features
4. Define user personas and use cases
5. Create product documentation and user guides

Focus on business value, user experience, and market viability."""
        super().__init__(AgentRole.PRODUCT_MANAGER, system_prompt)

class SystemArchitectAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior System Architect. Your role is to:
1. Design complete system architecture and technical specifications
2. Select appropriate technology stack and frameworks
3. Define API contracts and data models
4. Design microservices or monolithic architecture as needed
5. Plan for scalability, performance, and security
6. Create system diagrams and documentation

Focus on clean architecture, maintainability, and technical excellence."""
        super().__init__(AgentRole.SYSTEM_ARCHITECT, system_prompt)

class BackendEngineerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior Backend Engineer. Your role is to:
1. Implement RESTful APIs and GraphQL endpoints
2. Develop business logic and service layers
3. Implement authentication and authorization
4. Create database models and ORM configurations
5. Write unit and integration tests
6. Implement caching and performance optimizations
7. Ensure code quality and best practices

Focus on robust, scalable, and secure backend systems."""
        super().__init__(AgentRole.BACKEND_ENGINEER, system_prompt)

class FrontendEngineerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior Frontend Engineer. Your role is to:
1. Build responsive React components with modern hooks
2. Implement state management (Context API/Redux)
3. Create routing and navigation
4. Style with CSS-in-JS or modern CSS frameworks
5. Integrate with backend APIs
6. Implement client-side validation and error handling
7. Ensure cross-browser compatibility and accessibility

Focus on user experience, performance, and maintainable code."""
        super().__init__(AgentRole.FRONTEND_ENGINEER, system_prompt)

class DatabaseEngineerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior Database Engineer. Your role is to:
1. Design normalized database schemas
2. Create SQL migration scripts
3. Define indexes and query optimizations
4. Implement database security and access controls
5. Design data models and relationships
6. Create backup and recovery strategies
7. Optimize for performance and scalability

Focus on data integrity, performance, and security."""
        super().__init__(AgentRole.DATABASE_ENGINEER, system_prompt)

class QAEngineerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior QA Engineer. Your role is to:
1. Create comprehensive test strategies
2. Write unit tests, integration tests, and E2E tests
3. Implement test automation frameworks
4. Create test cases and scenarios
5. Perform security and performance testing
6. Ensure code coverage and quality metrics
7. Create testing documentation

Focus on quality assurance, test coverage, and automation."""
        super().__init__(AgentRole.QA_ENGINEER, system_prompt)

class DevOpsEngineerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior DevOps Engineer. Your role is to:
1. Create Docker configurations and containerization
2. Design CI/CD pipelines
3. Implement infrastructure as code
4. Set up monitoring and logging
5. Configure deployment strategies
6. Implement security scanning
7. Create deployment documentation

Focus on automation, reliability, and scalability."""
        super().__init__(AgentRole.DEVOPS_ENGINEER, system_prompt)

class SecurityEngineerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior Security Engineer. Your role is to:
1. Perform security code reviews
2. Implement authentication and authorization
3. Set up encryption and data protection
4. Implement security headers and policies
5. Conduct vulnerability assessments
6. Create security documentation
7. Implement security best practices

Focus on application security, data protection, and compliance."""
        super().__init__(AgentRole.SECURITY_ENGINEER, system_prompt)

class MobileEngineerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior Mobile Engineer. Your role is to:
1. Build cross-platform mobile applications
2. Implement native or React Native components
3. Create mobile-optimized UI/UX
4. Integrate with device features and APIs
5. Optimize for performance and battery life
6. Implement mobile-specific security
7. Create app store deployment packages

Focus on mobile-first design, performance, and user experience."""
        super().__init__(AgentRole.MOBILE_ENGINEER, system_prompt)

class MLEngineerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior ML Engineer. Your role is to:
1. Design and implement machine learning models
2. Create data preprocessing pipelines
3. Implement model training and evaluation
4. Deploy ML models to production
5. Create API endpoints for model inference
6. Implement monitoring and retraining pipelines
7. Create ML documentation

Focus on model accuracy, performance, and scalability."""
        super().__init__(AgentRole.ML_ENGINEER, system_prompt)

class DocumentationSpecialistAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior Documentation Specialist. Your role is to:
1. Create comprehensive technical documentation
2. Write API documentation with examples
3. Create user guides and tutorials
4. Generate README files and setup guides
5. Create architecture and design documents
6. Write deployment and operations guides
7. Ensure documentation clarity and completeness

Focus on clear, comprehensive, and user-friendly documentation."""
        super().__init__(AgentRole.DOCUMENTATION_SPECIALIST, system_prompt)

class UXDesignerAgent(Agent):
    def __init__(self):
        system_prompt = """You are a Senior UX Designer. Your role is to:
1. Create user experience designs and wireframes
2. Design user interfaces and component libraries
3. Create user flows and interaction designs
4. Implement design systems and style guides
5. Ensure accessibility and usability
6. Create responsive design specifications
7. Design for optimal user experience

Focus on usability, accessibility, and beautiful design."""
        super().__init__(AgentRole.UX_DESIGNER, system_prompt)

# ============================================
# ORCHESTRATOR
# ============================================

class Orchestrator:
    """Coordinates all agents to build complete software projects"""
    
    def __init__(self):
        self.agents = {
            AgentRole.PRODUCT_MANAGER: ProductManagerAgent(),
            AgentRole.SYSTEM_ARCHITECT: SystemArchitectAgent(),
            AgentRole.BACKEND_ENGINEER: BackendEngineerAgent(),
            AgentRole.FRONTEND_ENGINEER: FrontendEngineerAgent(),
            AgentRole.DATABASE_ENGINEER: DatabaseEngineerAgent(),
            AgentRole.QA_ENGINEER: QAEngineerAgent(),
            AgentRole.DEVOPS_ENGINEER: DevOpsEngineerAgent(),
            AgentRole.SECURITY_ENGINEER: SecurityEngineerAgent(),
            AgentRole.MOBILE_ENGINEER: MobileEngineerAgent(),
            AgentRole.ML_ENGINEER: MLEngineerAgent(),
            AgentRole.DOCUMENTATION_SPECIALIST: DocumentationSpecialistAgent(),
            AgentRole.UX_DESIGNER: UXDesignerAgent(),
        }
    
    async def execute_workflow(self, project_id: str, description: str):
        """Execute complete software development workflow"""
        
        db = SessionLocal()
        
        try:
            # Update project status
            project = db.query(Project).filter_by(id=project_id).first()
            if not project:
                raise Exception("Project not found")
            
            project.status = "running"
            db.commit()
            
            # Log start
            await self._log(project_id, "Orchestrator", "🚀 Starting autonomous development workflow")
            
            # Execute phases
            phases = [
                (AgentRole.PRODUCT_MANAGER, "📋 Analyzing requirements...", 
                 f"Analyze this project and create detailed requirements:\n{description}"),
                (AgentRole.UX_DESIGNER, "🎨 Designing user experience...",
                 "Design the user experience, user flows, and UI mockups based on requirements"),
                (AgentRole.SYSTEM_ARCHITECT, "🏗️ Designing system architecture...",
                 "Design complete system architecture including tech stack, API design, and component structure"),
                (AgentRole.DATABASE_ENGINEER, "🗄️ Designing database schema...",
                 "Design the database schema, relationships, indexes, and migrations"),
                (AgentRole.BACKEND_ENGINEER, "⚙️ Implementing backend...",
                 "Implement the complete backend with APIs, business logic, authentication, and database integration"),
                (AgentRole.FRONTEND_ENGINEER, "💻 Building frontend...",
                 "Implement the complete frontend with React components, state management, API integration, and routing"),
                (AgentRole.SECURITY_ENGINEER, "🔒 Security review...",
                 "Review code for security vulnerabilities and implement security best practices"),
                (AgentRole.QA_ENGINEER, "🧪 Writing tests...",
                 "Create comprehensive test suites including unit, integration, and E2E tests"),
                (AgentRole.DEVOPS_ENGINEER, "🚀 Setting up deployment...",
                 "Create Docker configuration, CI/CD pipeline, and deployment documentation"),
                (AgentRole.DOCUMENTATION_SPECIALIST, "📚 Writing documentation...",
                 "Create comprehensive documentation including README, API docs, and setup guides"),
            ]
            
            for role, log_msg, task in phases:
                await self._log(project_id, role.value, log_msg)
                result = await self.agents[role].execute(project_id, task, {})
                
                if not result.success:
                    raise Exception(f"{role.value} phase failed")
            
            # Complete
            project.status = "completed"
            db.commit()
            
            await self._log(project_id, "Orchestrator", "✅ Project generation completed successfully!")
            
        except Exception as e:
            project = db.query(Project).filter_by(id=project_id).first()
            if project:
                project.status = "failed"
                db.commit()
            
            await self._log(project_id, "Orchestrator", f"❌ Workflow failed: {str(e)}")
            raise e
        finally:
            db.close()
    
    async def _log(self, project_id: str, agent: str, message: str):
        """Helper to log messages"""
        db = SessionLocal()
        try:
            log = AgentLog(
                project_id=project_id,
                agent_name=agent,
                level="info",
                message=message,
                log_metadata={}
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(title="NexusForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = Orchestrator()

@app.get("/")
async def root():
    return {"message": "NexusForge API - Autonomous AI Development System", "status": "running"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "agents": len(orchestrator.agents),
        "database": "connected",
        "redis": "connected" if redis_client else "disconnected"
    }

@app.post("/api/projects")
async def create_project(project: ProjectCreate, background_tasks: BackgroundTasks):
    """Create a new project"""
    db = SessionLocal()
    
    try:
        project_id = str(uuid.uuid4())
        new_project = Project(
            id=project_id,
            name=project.name,
            description=project.description,
            status="initializing",
            project_metadata={}
        )
        
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        
        return {
            "success": True,
            "project": {
                "id": project_id,
                "name": project.name,
                "description": project.description,
                "status": "initializing"
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/api/projects/{project_id}/build")
async def start_build(project_id: str, background_tasks: BackgroundTasks):
    """Start autonomous build process"""
    db = SessionLocal()
    
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Run workflow in background
        background_tasks.add_task(
            orchestrator.execute_workflow,
            project_id,
            project.description
        )
        
        return {"success": True, "message": "Build started"}
    finally:
        db.close()

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details"""
    db = SessionLocal()
    
    try:
        project = db.query(Project).filter_by(id=project_id).first()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get files
        files = db.query(ProjectFile).filter_by(project_id=project_id).all()
        file_list = {f.file_path: f.content for f in files}
        
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
            "files": file_list
        }
    finally:
        db.close()

@app.get("/api/projects/{project_id}/logs")
async def get_logs(project_id: str):
    """Get project logs"""
    db = SessionLocal()
    
    try:
        logs = db.query(AgentLog).filter_by(project_id=project_id).order_by(AgentLog.created_at.desc()).limit(100).all()
        
        return {
            "logs": [
                {
                    "timestamp": log.created_at.isoformat(),
                    "agent": log.agent_name,
                    "level": log.level,
                    "message": log.message
                }
                for log in reversed(logs)
            ]
        }
    finally:
        db.close()

@app.get("/api/projects/{project_id}/files")
async def list_files(project_id: str):
    """List all project files"""
    db = SessionLocal()
    
    try:
        files = db.query(ProjectFile).filter_by(project_id=project_id).all()
        return {"files": [f.file_path for f in files]}
    finally:
        db.close()

@app.get("/api/projects/{project_id}/files/{file_path:path}")
async def get_file(project_id: str, file_path: str):
    """Get file content"""
    db = SessionLocal()
    
    try:
        # Ensure path starts with /
        if not file_path.startswith('/'):
            file_path = '/' + file_path
        
        file = db.query(ProjectFile).filter_by(
            project_id=project_id,
            file_path=file_path
        ).first()
        
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        
        return {
            "path": file.file_path,
            "content": file.content,
            "size": file.size
        }
    finally:
        db.close()

@app.post("/api/projects/{project_id}/files")
async def create_file(project_id: str, file: FileCreate):
    """Create or update a file"""
    db = SessionLocal()
    
    try:
        # Ensure path starts with /
        file_path = file.path if file.path.startswith('/') else '/' + file.path
        
        existing = db.query(ProjectFile).filter_by(
            project_id=project_id,
            file_path=file_path
        ).first()
        
        if existing:
            existing.content = file.content
            existing.size = len(file.content)
            existing.updated_at = datetime.utcnow()
        else:
            new_file = ProjectFile(
                project_id=project_id,
                file_path=file_path,
                content=file.content,
                size=len(file.content)
            )
            db.add(new_file)
        
        db.commit()
        return {"success": True, "path": file_path}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
        
@app.get("/api/projects/{project_id}/files/project")
async def get_project_files(project_id: str):
    """Get only project files (filter out config/test files)"""
    db = SessionLocal()
    
    try:
        all_files = db.query(ProjectFile).filter_by(project_id=project_id).all()
        
        # Filter out configuration and test files
        project_files = []
        config_patterns = ['Dockerfile', 'docker-compose', '.yml', '.yaml', 
                          'package.json', 'requirements.txt', '.config.js',
                          '.gitignore', '.env', 'alembic', 'migrations',
                          'tests/', '.test.', 'spec.', 'e2e/']
        
        for file in all_files:
            if not any(pattern in file.file_path for pattern in config_patterns):
                project_files.append(file)
        
        return {"files": [f.file_path for f in project_files]}
    finally:
        db.close()

@app.get("/api/agents/status")
async def get_agent_status():
    """Get status of all agents"""
    return {
        "agents": {
            role.value: {
                "status": agent.status,
                "role": role.value
            }
            for role, agent in orchestrator.agents.items()
        }
    }



if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting NexusForge API Server...")
    print(f"📊 Database: {DATABASE_URL}")
    print(f"🔑 Gemini API: {'Configured' if GEMINI_API_KEY else 'Not Configured'}")
    print(f"🔧 Using SQLite database: nexusforge.db")
    print(f"🌐 Server will be available at: http://localhost:8000")
    print(f"📚 API Docs: http://localhost:8000/docs")
    print(f"❤️  Health check: http://localhost:8000/health")
    

    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")