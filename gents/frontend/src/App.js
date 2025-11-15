import React, { useState, useRef, useEffect } from 'react';
import { Play, Terminal, FileText, Users, Cpu, FolderTree, Plus, Save, Activity } from 'lucide-react';

// API Configuration
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export default function NexusForge() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [projects, setProjects] = useState([]);
  const [currentProject, setCurrentProject] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [files, setFiles] = useState([]);
  const [logs, setLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [projectIdea, setProjectIdea] = useState('');
  const [agentStatus, setAgentStatus] = useState({});
  const editorRef = useRef(null);
  const logIntervalRef = useRef(null);

  // Fetch logs periodically
  useEffect(() => {
    if (currentProject && logIntervalRef.current === null) {
      logIntervalRef.current = setInterval(async () => {
        try {
          const response = await fetch(`${API_URL}/api/projects/${currentProject.id}/logs`);
          const data = await response.json();
          setLogs(data.logs || []);
          
          // Check project status
          const projectResponse = await fetch(`${API_URL}/api/projects/${currentProject.id}`);
          const projectData = await projectResponse.json();
          
          if (projectData.status === 'completed' || projectData.status === 'failed') {
            setIsRunning(false);
            if (logIntervalRef.current) {
              clearInterval(logIntervalRef.current);
              logIntervalRef.current = null;
            }
            
            // Refresh files
            await fetchFiles(currentProject.id);
          }
        } catch (error) {
          console.error('Error fetching logs:', error);
        }
      }, 2000);
    }
    
    return () => {
      if (logIntervalRef.current) {
        clearInterval(logIntervalRef.current);
        logIntervalRef.current = null;
      }
    };
  }, [currentProject]);

  // Load file content when selected
  useEffect(() => {
    if (selectedFile && currentProject) {
      fetchFileContent(currentProject.id, selectedFile);
    }
  }, [selectedFile, currentProject]);

  const fetchFiles = async (projectId) => {
    try {
      const response = await fetch(`${API_URL}/api/projects/${projectId}/files`);
      const data = await response.json();
      setFiles(data.files || []);
    } catch (error) {
      console.error('Error fetching files:', error);
    }
  };

  const fetchFileContent = async (projectId, filePath) => {
    try {
      const cleanPath = filePath.startsWith('/') ? filePath.substring(1) : filePath;
      const response = await fetch(`${API_URL}/api/projects/${projectId}/files/${cleanPath}`);
      const data = await response.json();
      setFileContent(data.content || '');
    } catch (error) {
      console.error('Error fetching file:', error);
      setFileContent('// Error loading file');
    }
  };

  const startAutonomousBuild = async () => {
    if (!projectIdea.trim()) {
      alert('Please enter a project description');
      return;
    }

    setIsRunning(true);
    setCurrentView('logs');
    setLogs([]);

    try {
      // Create project
      const createResponse = await fetch(`${API_URL}/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: projectIdea.substring(0, 50),
          description: projectIdea
        })
      });
      
      const createData = await createResponse.json();
      
      if (!createData.success) {
        throw new Error('Failed to create project');
      }
      
      const project = createData.project;
      setCurrentProject(project);
      
      // Start build
      const buildResponse = await fetch(`${API_URL}/api/projects/${project.id}/build`, {
        method: 'POST'
      });
      
      const buildData = await buildResponse.json();
      
      if (!buildData.success) {
        throw new Error('Failed to start build');
      }
      
      setLogs([{ 
        timestamp: new Date().toISOString(), 
        agent: 'System', 
        level: 'info', 
        message: '🚀 Build started! Agents are working...' 
      }]);
      
    } catch (error) {
      console.error('Error:', error);
      setLogs([{ 
        timestamp: new Date().toISOString(), 
        agent: 'System', 
        level: 'error', 
        message: `❌ Error: ${error.message}` 
      }]);
      setIsRunning(false);
    }
  };

  const saveFile = async () => {
    if (!currentProject || !selectedFile) return;
    
    try {
      await fetch(`${API_URL}/api/projects/${currentProject.id}/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: selectedFile,
          content: fileContent
        })
      });
      
      alert('File saved successfully!');
    } catch (error) {
      console.error('Error saving file:', error);
      alert('Error saving file');
    }
  };

  const createNewFile = () => {
    const filename = prompt('Enter filename (e.g., /src/app.js):');
    if (filename && filename.startsWith('/') && currentProject) {
      fetch(`${API_URL}/api/projects/${currentProject.id}/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: filename,
          content: '// New file\n'
        })
      }).then(() => {
        fetchFiles(currentProject.id);
        setSelectedFile(filename);
      });
    }
  };

  const renderDashboard = () => (
    <div className="p-6 space-y-6">
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 p-8 rounded-lg text-white">
        <h1 className="text-4xl font-bold mb-2">NexusForge</h1>
        <p className="text-lg opacity-90">Autonomous Multi-Agent AI Software Development System</p>
        <p className="text-sm opacity-75 mt-2">Powered by Google Gemini 2.0 Flash • 12 Specialized AI Agents</p>
      </div>

      <div className="bg-white p-6 rounded-lg border-2 border-gray-200">
        <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
          <Play className="w-6 h-6" />
          Create New Project
        </h2>
        <textarea
          className="w-full h-32 p-4 border-2 border-gray-300 rounded-lg mb-4 font-mono text-sm"
          placeholder="Describe your project idea in detail...&#10;&#10;Example: Build a full-stack task management application with user authentication, real-time updates, drag-and-drop interface, and mobile support. Include PostgreSQL database, React frontend, Node.js backend, and deploy to Docker."
          value={projectIdea}
          onChange={(e) => setProjectIdea(e.target.value)}
          disabled={isRunning}
        />
        <button
          onClick={startAutonomousBuild}
          disabled={isRunning}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg font-semibold flex items-center gap-2"
        >
          {isRunning ? (
            <>
              <Activity className="w-5 h-5 animate-spin" />
              Building...
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Start Autonomous Build
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-lg border-2 border-gray-200">
          <Users className="w-8 h-8 text-blue-600 mb-3" />
          <h3 className="font-bold text-lg mb-2">AI Agents</h3>
          <p className="text-gray-600 text-sm">12 specialized agents ready</p>
          <p className="text-xs text-gray-500 mt-2">PM • Architect • Backend • Frontend • Database • QA • DevOps • Security • Mobile • ML • Docs • UX</p>
        </div>
        <div className="bg-white p-6 rounded-lg border-2 border-gray-200">
          <FileText className="w-8 h-8 text-green-600 mb-3" />
          <h3 className="font-bold text-lg mb-2">Files Generated</h3>
          <p className="text-gray-600 text-sm">{files.length} files in workspace</p>
        </div>
        <div className="bg-white p-6 rounded-lg border-2 border-gray-200">
          <Cpu className="w-8 h-8 text-purple-600 mb-3" />
          <h3 className="font-bold text-lg mb-2">Status</h3>
          <p className="text-gray-600 text-sm">{isRunning ? 'Building...' : currentProject?.status || 'Ready'}</p>
        </div>
      </div>
    </div>
  );

  const renderEditor = () => (
    <div className="flex h-full">
      <div className="w-64 bg-gray-50 border-r-2 border-gray-200 overflow-y-auto">
        <div className="p-4 border-b-2 border-gray-200 flex justify-between items-center">
          <h3 className="font-bold flex items-center gap-2">
            <FolderTree className="w-5 h-5" />
            Files
          </h3>
          <button
            onClick={createNewFile}
            className="p-1 hover:bg-gray-200 rounded"
            disabled={!currentProject}
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
        {files.length === 0 ? (
          <div className="p-4 text-gray-500 text-sm text-center">
            No files yet. Start a build first.
          </div>
        ) : (
          files.map(path => (
            <div
              key={path}
              onClick={() => setSelectedFile(path)}
              className={`px-4 py-2 cursor-pointer hover:bg-gray-200 ${
                selectedFile === path ? 'bg-blue-100 border-l-4 border-blue-600' : ''
              }`}
            >
              <FileText className="w-4 h-4 inline mr-2" />
              <span className="text-sm">{path}</span>
            </div>
          ))
        )}
      </div>

      <div className="flex-1 flex flex-col">
        <div className="bg-gray-800 text-white px-4 py-2 flex justify-between items-center">
          <span className="font-mono text-sm">{selectedFile || 'No file selected'}</span>
          <button
            onClick={saveFile}
            disabled={!selectedFile}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-3 py-1 rounded text-sm flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            Save
          </button>
        </div>
        <textarea
          ref={editorRef}
          value={fileContent}
          onChange={(e) => setFileContent(e.target.value)}
          className="flex-1 p-4 font-mono text-sm bg-gray-900 text-gray-100 focus:outline-none"
          spellCheck={false}
          placeholder={selectedFile ? "Loading..." : "Select a file to edit"}
        />
      </div>
    </div>
  );

  const renderLogs = () => (
    <div className="h-full bg-gray-900 text-gray-100 p-4 overflow-y-auto font-mono text-sm">
      <div className="flex justify-between items-center mb-4 pb-2 border-b border-gray-700">
        <h3 className="font-bold flex items-center gap-2">
          <Terminal className="w-5 h-5" />
          Build Logs & Agent Activity
        </h3>
        {isRunning && (
          <Activity className="w-5 h-5 text-green-400 animate-spin" />
        )}
      </div>

      {logs.map((log, i) => (
        <div
          key={i}
          className={`mb-2 ${
            log.level === 'error' ? 'text-red-400' :
            log.level === 'success' ? 'text-green-400' :
            'text-gray-300'
          }`}
        >
          <span className="text-gray-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
          {' '}
          <span className="text-blue-400">[{log.agent}]</span>
          {' '}
          {log.message}
        </div>
      ))}
      
      {logs.length === 0 && !isRunning && (
        <div className="text-gray-500 text-center mt-8">
          No build logs yet. Start a project from the dashboard.
        </div>
      )}
      
      {isRunning && logs.length === 0 && (
        <div className="text-yellow-400 animate-pulse">
          Initializing agents...
        </div>
      )}
    </div>
  );

  const renderAgents = () => (
    <div className="p-6 space-y-4 overflow-y-auto">
      <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
        <Users className="w-6 h-6" />
        AI Agent Team (Gemini 2.0 Flash)
      </h2>
      
      {[
        { name: 'Product Manager', desc: 'Requirements analysis and product strategy', color: 'blue' },
        { name: 'System Architect', desc: 'System design and technical architecture', color: 'purple' },
        { name: 'Backend Engineer', desc: 'API development and server-side logic', color: 'green' },
        { name: 'Frontend Engineer', desc: 'User interface and client-side development', color: 'cyan' },
        { name: 'Database Engineer', desc: 'Schema design and data optimization', color: 'yellow' },
        { name: 'QA Engineer', desc: 'Testing and quality assurance', color: 'red' },
        { name: 'DevOps Engineer', desc: 'Deployment and infrastructure', color: 'orange' },
        { name: 'Security Engineer', desc: 'Security review and best practices', color: 'pink' },
        { name: 'Mobile Engineer', desc: 'Mobile app development', color: 'indigo' },
        { name: 'ML Engineer', desc: 'Machine learning and AI features', color: 'violet' },
        { name: 'Documentation Specialist', desc: 'Technical documentation and guides', color: 'teal' },
        { name: 'UX Designer', desc: 'User experience and interface design', color: 'rose' }
      ].map((agent, i) => (
        <div key={i} className="bg-white p-6 rounded-lg border-2 border-gray-200">
          <div className="flex justify-between items-start mb-2">
            <h3 className="font-bold text-lg">{agent.name}</h3>
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
              Ready
            </span>
          </div>
          <p className="text-gray-600">{agent.desc}</p>
        </div>
      ))}
    </div>
  );

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <div className="bg-white border-b-2 border-gray-200 px-6 py-3 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Cpu className="w-6 h-6 text-blue-600" />
          <span className="font-bold text-xl">NexusForge</span>
          <span className="text-xs text-gray-500 ml-2">Gemini 2.0 Flash</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setCurrentView('dashboard')}
            className={`px-4 py-2 rounded-lg ${
              currentView === 'dashboard' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => setCurrentView('editor')}
            className={`px-4 py-2 rounded-lg ${
              currentView === 'editor' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
          >
            Editor
          </button>
          <button
            onClick={() => setCurrentView('logs')}
            className={`px-4 py-2 rounded-lg ${
              currentView === 'logs' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
          >
            Logs
          </button>
          <button
            onClick={() => setCurrentView('agents')}
            className={`px-4 py-2 rounded-lg ${
              currentView === 'agents' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
          >
            Agents
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {currentView === 'dashboard' && renderDashboard()}
        {currentView === 'editor' && renderEditor()}
        {currentView === 'logs' && renderLogs()}
        {currentView === 'agents' && renderAgents()}
      </div>
    </div>
  );
}