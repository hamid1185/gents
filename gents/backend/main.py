# main.py - NexusForge Python Backend with Gemini SDK
# pip install fastapi uvicorn google-generativeai sqlalchemy psycopg2-binary redis websockets

import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import redis

# ============================================
# CONFIGURATION
# ============================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://nexus:nexusforge@localhost:5432/nexusforge")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

genai.configure(api_key=GEMINI_API_KEY)

# ============================================
# DATABASE MODELS
# ============================================

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True)
    name = Column(String)
    description = Column(Text)
    status = Column(String, default="initializing")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON)

class ProjectFile(Base):
    __tablename__ = "project_files"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String)
    file_path = Column(String)
    content = Column(Text)
    size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String)
    agent_name = Column(String)
    level = Column(String)
    message = Column(Text)
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class SharedMemory(Base):
    __tablename__ = "shared_memory"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String)
    key = Column(String)
    value = Column(JSON)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(engine)

# ============================================
# REDIS CONNECTION
# ============================================

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

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
        self.model = genai.GenerativeModel(
            'gemini-2.0-flash-exp',
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
        )
    
    async def execute(self, project_id: str, task: str, context: Dict) -> TaskResult:
        """Execute a task using Gemini"""
        self.status = "working"
        
        try:
            # Get shared memory
            db = SessionLocal()
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
        "/path/to/file.ext": "complete file content here",
        "/another/file.ext": "complete file content here"
    }},
    "shared_memory_updates": {{
        "key_name": "value to share with team"
    }},
    "next_steps": ["recommended next step", "another step"],
    "blockers": ["any issues or dependencies"]
}}

Generate complete, production-ready code. No placeholders, no TODOs."""

            # Call Gemini
            response = self.model.generate_content(prompt)
            text = response.text
            
            # Extract JSON from response
            json_start = text.find('{')
            json_end = text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                result = json.loads(json_str)
            else:
                result = {"output": text, "reasoning": "No structured response"}
            
            # Update shared memory
            if "shared_memory_updates" in result:
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
            log = AgentLog(
                project_id=project_id,
                agent_name=self.role.value,
                level="success",
                message=f"Completed: {result.get('output', 'Task done')[:200]}",
                metadata={"task": task}
            )
            db.add(log)
            db.commit()
            db.close()
            
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
            db = SessionLocal()
            log = AgentLog(
                project_id=project_id,
                agent_name=self.role.value,
                level="error",
                message=f"Error: {str(e)}",
                metadata={"task": task, "error": str(e)}
            )
            db.add(log)
            db.commit()
            db.close()
            
            raise e

# ============================================
# SPECIALIZED AGENTS
# ============================================

class ProductManagerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.PRODUCT_MANAGER,
            """You are an expert Product Manager with 15+ years experience at top tech companies.
            
Your responsibilities:
- Analyze project requirements and user needs
- Create detailed user stories and acceptance criteria
- Define MVP scope and feature prioritization
- Create product roadmaps and timelines
- Ensure technical feasibility aligns with business goals

Be thorough, practical, and focus on delivering business value."""
        )

class SystemArchitectAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.SYSTEM_ARCHITECT,
            """You are a senior System Architect with expertise in distributed systems, microservices, and cloud architecture.

Your responsibilities:
- Design scalable, maintainable system architectures
- Choose appropriate technologies and frameworks
- Define API contracts and data models
- Design database schemas and relationships
- Plan for security, performance, and reliability
- Create technical specifications

Use modern best practices, SOLID principles, and proven design patterns."""
        )

class BackendEngineerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.BACKEND_ENGINEER,
            """You are a senior Backend Engineer expert in Node.js, Python, Go, and Java.

Your responsibilities:
- Implement RESTful APIs and GraphQL endpoints
- Write clean, efficient, production-ready code
- Implement business logic and data processing
- Handle authentication and authorization
- Implement error handling and logging
- Write database queries and ORM models

Generate complete, working code with proper error handling, validation, and documentation."""
        )

class FrontendEngineerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.FRONTEND_ENGINEER,
            """You are a senior Frontend Engineer expert in React, Vue, Angular, and modern web technologies.

Your responsibilities:
- Build responsive, accessible user interfaces
- Implement state management (Redux, Zustand, etc)
- Create reusable components following best practices
- Integrate with backend APIs
- Implement routing and navigation
- Ensure cross-browser compatibility

Generate complete, production-ready React/Vue/Angular code with proper TypeScript types."""
        )

class DatabaseEngineerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.DATABASE_ENGINEER,
            """You are a Database Engineer expert in PostgreSQL, MongoDB, Redis, and database optimization.

Your responsibilities:
- Design normalized database schemas
- Write efficient queries and indexes
- Plan data migrations and versioning
- Optimize query performance
- Design caching strategies
- Ensure data integrity and consistency

Generate complete SQL/NoSQL schemas, migrations, and optimized queries."""
        )

class QAEngineerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.QA_ENGINEER,
            """You are a QA Engineer expert in test automation, quality assurance, and best practices.

Your responsibilities:
- Write comprehensive unit tests
- Create integration and E2E tests
- Perform code reviews for quality
- Identify bugs and edge cases
- Test API endpoints and UI flows
- Ensure code coverage and quality metrics

Generate complete test suites using Jest, Pytest, Playwright, etc."""
        )

class DevOpsEngineerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.DEVOPS_ENGINEER,
            """You are a DevOps Engineer expert in Docker, Kubernetes, CI/CD, and cloud platforms.

Your responsibilities:
- Create Dockerfiles and docker-compose configurations
- Design Kubernetes deployments and services
- Build CI/CD pipelines (GitHub Actions, GitLab CI)
- Configure monitoring and logging
- Implement infrastructure as code
- Plan deployment strategies

Generate complete, production-ready deployment configurations."""
        )

class SecurityEngineerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.SECURITY_ENGINEER,
            """You are a Security Engineer expert in application security, cryptography, and secure coding.

Your responsibilities:
- Identify security vulnerabilities
- Implement authentication and authorization
- Configure HTTPS and security headers
- Handle sensitive data properly
- Implement rate limiting and DDOS protection
- Ensure OWASP Top 10 compliance

Generate secure code with proper input validation, sanitization, and encryption."""
        )

class MobileEngineerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.MOBILE_ENGINEER,
            """You are a Mobile Engineer expert in React Native, Flutter, iOS, and Android development.

Your responsibilities:
- Build cross-platform mobile applications
- Implement native features and APIs
- Optimize for mobile performance
- Handle offline functionality
- Implement push notifications
- Ensure responsive mobile UI

Generate complete React Native or Flutter code with proper navigation and state management."""
        )

class MLEngineerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.ML_ENGINEER,
            """You are a Machine Learning Engineer expert in TensorFlow, PyTorch, and ML pipelines.

Your responsibilities:
- Design ML model architectures
- Implement data preprocessing pipelines
- Train and evaluate models
- Deploy models to production
- Implement model monitoring
- Optimize inference performance

Generate complete ML code with proper data handling, training loops, and deployment."""
        )

class DocumentationSpecialistAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.DOCUMENTATION_SPECIALIST,
            """You are a Documentation Specialist expert in technical writing and developer documentation.

Your responsibilities:
- Write clear, comprehensive documentation
- Create API references and guides
- Write README files and setup instructions
- Document architecture and design decisions
- Create code comments and docstrings
- Write user guides and tutorials

Generate well-structured, clear documentation in Markdown format."""
        )

class UXDesignerAgent(Agent):
    def __init__(self):
        super().__init__(
            AgentRole.UX_DESIGNER,
            """You are a UX Designer expert in user research, interaction design, and usability.

Your responsibilities:
- Design user flows and wireframes
- Create UI mockups and prototypes
- Ensure accessibility (WCAG compliance)
- Design responsive layouts
- Choose color schemes and typography
- Optimize user experience

Provide design specifications, component descriptions, and UX recommendations."""
        )

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
            project.status = "running"
            db.commit()
            
            # Log start
            log = AgentLog(
                project_id=project_id,
                agent_name="Orchestrator",
                level="info",
                message="🚀 Starting autonomous development workflow",
                metadata={}
            )
            db.add(log)
            db.commit()
            
            # Phase 1: Product Requirements
            await self._log(project_id, "ProductManager", "📋 Analyzing requirements...")
            await self.agents[AgentRole.PRODUCT_MANAGER].execute(
                project_id,
                f"Analyze this project and create detailed requirements:\n{description}",
                {}
            )
            
            # Phase 2: UX Design
            await self._log(project_id, "UXDesigner", "🎨 Designing user experience...")
            await self.agents[AgentRole.UX_DESIGNER].execute(
                project_id,
                "Design the user experience, user flows, and UI mockups based on requirements",
                {}
            )
            
            # Phase 3: System Architecture
            await self._log(project_id, "SystemArchitect", "🏗️ Designing system architecture...")
            await self.agents[AgentRole.SYSTEM_ARCHITECT].execute(
                project_id,
                "Design complete system architecture including tech stack, API design, and component structure",
                {}
            )
            
            # Phase 4: Database Design
            await self._log(project_id, "DatabaseEngineer", "🗄️ Designing database schema...")
            await self.agents[AgentRole.DATABASE_ENGINEER].execute(
                project_id,
                "Design the database schema, relationships, indexes, and migrations",
                {}
            )
            
            # Phase 5: Backend Development
            await self._log(project_id, "BackendEngineer", "⚙️ Implementing backend...")
            await self.agents[AgentRole.BACKEND_ENGINEER].execute(
                project_id,
                "Implement the complete backend with APIs, business logic, authentication, and database integration",
                {}
            )
            
            # Phase 6: Frontend Development
            await self._log(project_id, "FrontendEngineer", "💻 Building frontend...")
            await self.agents[AgentRole.FRONTEND_ENGINEER].execute(
                project_id,
                "Implement the complete frontend with React components, state management, API integration, and routing",
                {}
            )
            
            # Phase 7: Mobile App (if needed)
            await self._log(project_id, "MobileEngineer", "📱 Building mobile app...")
            await self.agents[AgentRole.MOBILE_ENGINEER].execute(
                project_id,
                "Create a mobile app version using React Native with all core features",
                {}
            )
            
            # Phase 8: Security Review
            await self._log(project_id, "SecurityEngineer", "🔒 Security review...")
            await self.agents[AgentRole.SECURITY_ENGINEER].execute(
                project_id,
                "Review code for security vulnerabilities and implement security best practices",
                {}
            )
            
            # Phase 9: Testing
            await self._log(project_id, "QAEngineer", "🧪 Writing tests...")
            await self.agents[AgentRole.QA_ENGINEER].execute(
                project_id,
                "Create comprehensive test suites including unit, integration, and E2E tests",
                {}
            )
            
            # Phase 10: DevOps & Deployment
            await self._log(project_id, "DevOpsEngineer", "🚀 Setting up deployment...")
            await self.agents[AgentRole.DEVOPS_ENGINEER].execute(
                project_id,
                "Create Docker configuration, CI/CD pipeline, and deployment documentation",
                {}
            )
            
            # Phase 11: Documentation
            await self._log(project_id, "DocumentationSpecialist", "📚 Writing documentation...")
            await self.agents[AgentRole.DOCUMENTATION_SPECIALIST].execute(
                project_id,
                "Create comprehensive documentation including README, API docs, and setup guides",
                {}
            )
            
            # Complete
            project.status = "completed"
            db.commit()
            
            log = AgentLog(
                project_id=project_id,
                agent_name="Orchestrator",
                level="success",
                message="✅ Project generation completed successfully!",
                metadata={}
            )
            db.add(log)
            db.commit()
            
        except Exception as e:
            project.status = "failed"
            db.commit()
            
            log = AgentLog(
                project_id=project_id,
                agent_name="Orchestrator",
                level="error",
                message=f"❌ Workflow failed: {str(e)}",
                metadata={"error": str(e)}
            )
            db.add(log)
            db.commit()
            
            raise e
        finally:
            db.close()
    
    async def _log(self, project_id: str, agent: str, message: str):
        """Helper to log messages"""
        db = SessionLocal()
        log = AgentLog(
            project_id=project_id,
            agent_name=agent,
            level="info",
            message=message,
            metadata={}
        )
        db.add(log)
        db.commit()
        db.close()

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(title="NexusForge API")

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
    return {"message": "NexusForge API - Autonomous AI Development System"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "agents": len(orchestrator.agents)
    }

@app.post("/api/projects")
async def create_project(project: ProjectCreate, background_tasks: BackgroundTasks):
    """Create a new project"""
    db = SessionLocal()
    
    project_id = str(uuid.uuid4())
    new_project = Project(
        id=project_id,
        name=project.name,
        description=project.description,
        status="initializing",
        metadata={}
    )
    
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    db.close()
    
    return {
        "success": True,
        "project": {
            "id": project_id,
            "name": project.name,
            "description": project.description,
            "status": "initializing"
        }
    }

@app.post("/api/projects/{project_id}/build")
async def start_build(project_id: str, background_tasks: BackgroundTasks):
    """Start autonomous build process"""
    db = SessionLocal()
    project = db.query(Project).filter_by(id=project_id).first()
    db.close()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Run workflow in background
    background_tasks.add_task(
        orchestrator.execute_workflow,
        project_id,
        project.description
    )
    
    return {"success": True, "message": "Build started"}

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get project details"""
    db = SessionLocal()
    project = db.query(Project).filter_by(id=project_id).first()
    
    if not project:
        db.close()
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get files
    files = db.query(ProjectFile).filter_by(project_id=project_id).all()
    file_list = {f.file_path: f.content for f in files}
    
    db.close()
    
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
        "files": file_list
    }

@app.get("/api/projects/{project_id}/logs")
async def get_logs(project_id: str):
    """Get project logs"""
    db = SessionLocal()
    logs = db.query(AgentLog).filter_by(project_id=project_id).order_by(AgentLog.created_at.desc()).limit(100).all()
    db.close()
    
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

@app.get("/api/projects/{project_id}/files")
async def list_files(project_id: str):
    """List all project files"""
    db = SessionLocal()
    files = db.query(ProjectFile).filter_by(project_id=project_id).all()
    db.close()
    
    return {
        "files": [f.file_path for f in files]
    }

@app.get("/api/projects/{project_id}/files/{file_path:path}")
async def get_file(project_id: str, file_path: str):
    """Get file content"""
    db = SessionLocal()
    file = db.query(ProjectFile).filter_by(
        project_id=project_id,
        file_path=f"/{file_path}"
    ).first()
    db.close()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "path": file.file_path,
        "content": file.content
    }

@app.post("/api/projects/{project_id}/files")
async def create_file(project_id: str, file: FileCreate):
    """Create or update a file"""
    db = SessionLocal()
    
    existing = db.query(ProjectFile).filter_by(
        project_id=project_id,
        file_path=file.path
    ).first()
    
    if existing:
        existing.content = file.content
        existing.size = len(file.content)
        existing.updated_at = datetime.utcnow()
    else:
        new_file = ProjectFile(
            project_id=project_id,
            file_path=file.path,
            content=file.content,
            size=len(file.content)
        )
        db.add(new_file)
    
    db.commit()
    db.close()
    
    return {"success": True}

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
    uvicorn.run(app, host="0.0.0.0", port=8000)