import React, { useState, useRef, useEffect } from 'react';
import './App.css';

// API Configuration
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Simple icon components to replace lucide-react
const Icon = ({ children, className = '' }) => (
  <span className={`icon ${className}`}>{children}</span>
);

const PlayIcon = () => <Icon>▶</Icon>;
const TerminalIcon = () => <Icon>💻</Icon>;
const FileTextIcon = () => <Icon>📄</Icon>;
const UsersIcon = () => <Icon>👥</Icon>;
const CpuIcon = () => <Icon>⚡</Icon>;
const FolderTreeIcon = () => <Icon>📁</Icon>;
const PlusIcon = () => <Icon>➕</Icon>;
const SaveIcon = () => <Icon>💾</Icon>;
const ActivityIcon = () => <Icon>🔄</Icon>;
const DownloadIcon = () => <Icon>📥</Icon>;
const TrashIcon = () => <Icon>🗑️</Icon>;

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
  const logsEndRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logsEndRef.current && currentView === 'logs') {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, currentView]);

  // Fetch logs periodically
  useEffect(() => {
    if (currentProject && currentView === 'logs') {
      if (logIntervalRef.current === null) {
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
    }
    
    return () => {
      if (logIntervalRef.current) {
        clearInterval(logIntervalRef.current);
        logIntervalRef.current = null;
      }
    };
  }, [currentProject, currentView]);

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
      const response = await fetch(`${API_URL}/api/projects/${currentProject.id}/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: selectedFile,
          content: fileContent
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        alert('File saved successfully!');
      }
    } catch (error) {
      console.error('Error saving file:', error);
      alert('Error saving file');
    }
  };

  const createNewFile = () => {
    const filename = prompt('Enter filename (e.g., /src/app.js):');
    if (filename && currentProject) {
      const path = filename.startsWith('/') ? filename : '/' + filename;
      fetch(`${API_URL}/api/projects/${currentProject.id}/files`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: path,
          content: '// New file\n'
        })
      }).then(() => {
        fetchFiles(currentProject.id);
        setSelectedFile(path);
      });
    }
  };

  

  const downloadProject = () => {
    if (!currentProject || files.length === 0) {
      alert('No files to download');
      return;
    }

    // Create a simple download of all files as text
    let content = `# ${currentProject.name}\n\n`;
    files.forEach(file => {
      content += `\n\n## File: ${file}\n\n`;
      // Would need to fetch each file content - simplified for now
    });

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentProject.name.replace(/\s+/g, '_')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getFileLanguage = (path) => {
    const ext = path.split('.').pop();
    const langMap = {
      'js': 'javascript',
      'jsx': 'javascript',
      'ts': 'typescript',
      'tsx': 'typescript',
      'py': 'python',
      'json': 'json',
      'css': 'css',
      'html': 'html',
      'md': 'markdown',
      'sql': 'sql',
      'sh': 'bash',
      'yml': 'yaml',
      'yaml': 'yaml',
      'txt': 'text'
    };
    return langMap[ext] || 'text';
  };

  const renderDashboard = () => (
    <div className="p-6 space-y-6">
      <div className="hero-gradient p-8 rounded-lg text-white">
        <h1 className="text-4xl font-bold mb-2">NexusForge</h1>
        <p className="text-lg opacity-90">Autonomous Multi-Agent AI Software Development System</p>
        <p className="text-sm opacity-75 mt-2">Powered by Google Gemini 2.0 Flash • 12 Specialized AI Agents</p>
      </div>

      <div className="card">
        <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
          <PlayIcon />
          Create New Project
        </h2>
        <textarea
          className="w-full h-32 p-4 border-2 border-gray-300 rounded-lg mb-4 font-mono text-sm focus:border-blue-500 focus:outline-none"
          placeholder="Describe your project idea in detail...&#10;&#10;Example: Build a full-stack task management application with user authentication, real-time updates, drag-and-drop interface, and mobile support. Include PostgreSQL database, React frontend, Node.js backend, and deploy to Docker."
          value={projectIdea}
          onChange={(e) => setProjectIdea(e.target.value)}
          disabled={isRunning}
        />
        <button
          onClick={startAutonomousBuild}
          disabled={isRunning}
          className="btn btn-primary"
        >
          {isRunning ? (
            <>
              <ActivityIcon />
              Building...
            </>
          ) : (
            <>
              <PlayIcon />
              Start Autonomous Build
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="stat-card">
          <UsersIcon />
          <h3 className="font-bold text-lg mb-2">AI Agents</h3>
          <p className="text-gray-600 text-sm">12 specialized agents ready</p>
          <p className="text-xs text-gray-500 mt-2">PM • Architect • Backend • Frontend • Database • QA • DevOps • Security • Mobile • ML • Docs • UX</p>
        </div>
        <div className="stat-card">
          <FileTextIcon />
          <h3 className="font-bold text-lg mb-2">Files Generated</h3>
          <p className="text-gray-600 text-sm">{files.length} files in workspace</p>
        </div>
        <div className="stat-card">
          <CpuIcon />
          <h3 className="font-bold text-lg mb-2">Status</h3>
          <p className="text-gray-600 text-sm">{isRunning ? 'Building...' : currentProject?.status || 'Ready'}</p>
        </div>
      </div>

      {currentProject && (
        <div className="card">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-xl font-bold">Current Project</h3>
            <button onClick={downloadProject} className="btn btn-secondary">
              <DownloadIcon />
              Download
            </button>
          </div>
          <p className="text-gray-600 mb-2"><strong>Name:</strong> {currentProject.name}</p>
          <p className="text-gray-600 mb-2"><strong>Status:</strong> <span className={`badge ${currentProject.status === 'completed' ? 'badge-success' : currentProject.status === 'failed' ? 'badge-error' : 'badge-warning'}`}>{currentProject.status}</span></p>
          <p className="text-gray-600"><strong>Files:</strong> {files.length}</p>
        </div>
      )}
    </div>
  );


  //filter project files
const filterProjectFiles = (files) => {
  const projectFilePatterns = [
    /\.html$/, /\.css$/, /\.js$/, /\.json$/, 
    /\/src\//, /\/public\//, /^[^/]+\.[^/]+$/ 
  ];
  
  const configFilePatterns = [
    /Dockerfile/, /docker-compose/, /\.yml$/, /\.yaml$/,
    /package\.json/, /requirements\.txt/, /\.config\.js$/,
    /\.gitignore/, /\.env/, /alembic/, /migrations/,
    /tests?\//, /\.test\./, /spec\./, /e2e\//
  ];

  return files.filter(file => 
    projectFilePatterns.some(pattern => pattern.test(file)) &&
    !configFilePatterns.some(pattern => pattern.test(file))
  );
};

  const renderEditor = () => (
    <div className="flex h-full">
      <div className="file-tree">
        <div className="file-tree-header">
          <h3 className="font-bold flex items-center gap-2">
            <FolderTreeIcon />
            Files
          </h3>
          <button
            onClick={createNewFile}
            className="p-1 hover:bg-gray-200 rounded"
            disabled={!currentProject}
            title="Create new file"renderLogs 
          >
            <PlusIcon />
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
              className={`file-item ${selectedFile === path ? 'file-item-active' : ''}`}
            >
              <FileTextIcon />
              <span className="text-sm truncate">{path}</span>
            </div>
          ))
        )}
      </div>

      <div className="flex-1 flex flex-col">
        <div className="editor-header">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm">{selectedFile || 'No file selected'}</span>
            {selectedFile && (
              <span className="badge badge-secondary">{getFileLanguage(selectedFile)}</span>
            )}
          </div>
          <button
            onClick={saveFile}
            disabled={!selectedFile}
            className="btn btn-primary btn-sm"
          >
            <SaveIcon />
            Save
          </button>
        </div>
        <textarea
          ref={editorRef}
          value={fileContent}
          onChange={(e) => setFileContent(e.target.value)}
          className="code-editor"
          spellCheck={false}
          placeholder={selectedFile ? "Loading..." : "Select a file to edit"}
        />
      </div>
    </div>
  );

  const renderLogs = () => (
  <div className="log-container">
    <div className="log-header">
      <h3 className="font-bold flex items-center gap-2">
        <TerminalIcon />
        Live Agent Activity
      </h3>
      <div className="agent-status">
        {isRunning && (
          <div className="flex items-center gap-2">
            <ActivityIcon />
            <span className="text-sm">Agents Working...</span>
          </div>
        )}
      </div>
    </div>

    <div className="log-content">
      {logs.map((log, i) => (
        <div key={i} className={`log-entry log-${log.level} agent-${log.agent.toLowerCase()}`}>
          <span className="log-time">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
          {' '}
          <span className={`log-agent agent-${log.agent.toLowerCase()}`}>
            [{log.agent}]
          </span>
          {' '}
          <span className="log-message">{log.message}</span>
        </div>
      ))}
      <div ref={logsEndRef} />
    </div>
  </div>
);

  const renderAgents = () => (
    <div className="p-6 space-y-4 overflow-y-auto">
      <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
        <UsersIcon />
        AI Agent Team (Gemini 2.0 Flash)
      </h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[
          { name: 'Product Manager', desc: 'Requirements analysis and product strategy', icon: '📋', color: 'blue' },
          { name: 'System Architect', desc: 'System design and technical architecture', icon: '🏗️', color: 'purple' },
          { name: 'Backend Engineer', desc: 'API development and server-side logic', icon: '⚙️', color: 'green' },
          { name: 'Frontend Engineer', desc: 'User interface and client-side development', icon: '💻', color: 'cyan' },
          { name: 'Database Engineer', desc: 'Schema design and data optimization', icon: '🗄️', color: 'yellow' },
          { name: 'QA Engineer', desc: 'Testing and quality assurance', icon: '🧪', color: 'red' },
          { name: 'DevOps Engineer', desc: 'Deployment and infrastructure', icon: '🚀', color: 'orange' },
          { name: 'Security Engineer', desc: 'Security review and best practices', icon: '🔒', color: 'pink' },
          { name: 'Mobile Engineer', desc: 'Mobile app development', icon: '📱', color: 'indigo' },
          { name: 'ML Engineer', desc: 'Machine learning and AI features', icon: '🤖', color: 'violet' },
          { name: 'Documentation Specialist', desc: 'Technical documentation and guides', icon: '📚', color: 'teal' },
          { name: 'UX Designer', desc: 'User experience and interface design', icon: '🎨', color: 'rose' }
        ].map((agent, i) => (
          <div key={i} className="agent-card">
            <div className="flex justify-between items-start mb-2">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{agent.icon}</span>
                <h3 className="font-bold text-lg">{agent.name}</h3>
              </div>
              <span className="badge badge-success">Ready</span>
            </div>
            <p className="text-gray-600">{agent.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="flex items-center gap-2">
          <CpuIcon />
          <span className="font-bold text-xl">NexusForge</span>
          <span className="text-xs text-gray-500 ml-2">Gemini 2.0 Flash</span>
        </div>
        <nav className="nav-tabs">
          <button
            onClick={() => setCurrentView('dashboard')}
            className={`nav-tab ${currentView === 'dashboard' ? 'nav-tab-active' : ''}`}
          >
            Dashboard
          </button>
          <button
            onClick={() => setCurrentView('editor')}
            className={`nav-tab ${currentView === 'editor' ? 'nav-tab-active' : ''}`}
          >
            Editor
          </button>
          <button
            onClick={() => setCurrentView('logs')}
            className={`nav-tab ${currentView === 'logs' ? 'nav-tab-active' : ''}`}
          >
            Logs
          </button>
          <button
            onClick={() => setCurrentView('agents')}
            className={`nav-tab ${currentView === 'agents' ? 'nav-tab-active' : ''}`}
          >
            Agents
          </button>
        </nav>
      </header>

      <main className="app-main">
        {currentView === 'dashboard' && renderDashboard()}
        {currentView === 'editor' && renderEditor()}
        {currentView === 'logs' && renderLogs()}
        {currentView === 'agents' && renderAgents()}
      </main>
    </div>
  );
}