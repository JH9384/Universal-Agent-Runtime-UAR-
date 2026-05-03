# 🚀 UAR Onboarding Guide (Zero to Running)

## 🎯 Who This Guide Is For

Perfect for anyone who:
- **New to UAR** - Never seen this system before
- **Non-technical** - Just wants to use it, not understand the code
- **Quick starter** - Wants to see results in minutes
- **First-time user** - Needs step-by-step guidance

---

## 🧠 What UAR Is (Simple Explanation)

**UAR = Universal Agent Runtime**

Think of it like a **smart assistant** that:

1. **You give it a goal** → "Analyze this codebase"
2. **It plans the work** → Chooses the right tools
3. **It executes step-by-step** → Runs AI skills in sequence
4. **You get results** → Complete analysis with visual feedback

**Mental Model**: `Your Goal → UAR's Brain → AI Tools → Your Results`

---

## ⚡ Quick Start (Recommended)

The fastest way to get running:

```bash
# Clone and setup automatically
git clone <repository-url>
cd Universal-Agent-Runtime-UAR-

# Run the quickstart script
./scripts/quickstart.sh
```

This script handles everything: dependencies, setup, and launches both the API and web interface.

---

## 🔧 Manual Setup (Step-by-Step)

### Prerequisites

You'll need:
- **Python 3.11+** (recommended: 3.11)
- **Node.js 18+** (for the web interface)
- **Ollama** (for local AI execution)

### Step 1: Install Ollama

```bash
# Install Ollama (macOS)
brew install ollama

# Or download from: https://ollama.com

# Pull the recommended model
ollama pull llama3.2:3b
```

### Step 2: Start Ollama

```bash
ollama serve
```

**Keep this running in a separate terminal window.**

### Step 3: Setup Python Environment

```bash
# Install Python dependencies
python3.11 -m pip install -e '.[dev]'

# Or use the provided script
./scripts/run.sh
```

### Step 4: Setup Web Interface

```bash
# Navigate to web app
cd apps/web

# Install Node.js dependencies
npm install

# Start development server
npm run dev
```

### Step 5: Verify Setup

You should have:
- **API Server**: `http://127.0.0.1:8000`
- **Web Interface**: `http://localhost:5173`

---

## 🎮 Your First Task (Web Interface)

### Using the Modern Web UI

1. **Open Browser**: Navigate to `http://localhost:5173`
2. **Enter Goal**: Type something like:
   - "Analyze this codebase and generate documentation"
   - "Explain how this system works"
   - "Find all Python files and their dependencies"
3. **Click Execute**: Watch the real-time processing
4. **View Results**: See the dependency graph and event log

### What You'll See

- **🎯 Goal Input**: Clean, validated text field
- **⚡ Loading States**: Real-time progress indicators
- **📊 Graph Visualization**: Interactive dependency graph
- **📋 Event Log**: Formatted execution events
- **🛡️ Error Handling**: User-friendly error messages

---

## 🖥️ Your First Task (Command Line)

If you prefer the command line:

```bash
curl -X POST http://localhost:8000/api/uar/stream \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Explain gravity simply",
    "skills": ["doc_ingest", "dependency_map", "sum_review"],
    "input_path": "./"
  }'
```

---

## 🎯 Understanding What Happened

### The Magic Behind UAR

1. **Goal Processing**: Your text is analyzed and validated
2. **Skill Selection**: UAR chooses the right AI skills:
   - `doc_ingest` - Reads and analyzes files
   - `dependency_map` - Maps code relationships
   - `sum_review` - Creates summaries
3. **Orchestration**: Skills run in the optimal sequence
4. **Result Aggregation**: All results combined and formatted
5. **Visualization**: Interactive graph shows the workflow

### Real-Time Feedback

- **Loading Spinner**: Shows processing is happening
- **Progress Events**: See each skill executing
- **Graph Updates**: Watch the dependency graph build
- **Success/Error**: Clear feedback on completion

---

## 🎨 Exploring the Modern Interface

### Key Features

- **📱 Mobile Responsive**: Works on phones and tablets
- **♿ Accessible**: Screen reader compatible, keyboard navigation
- **🌙 Dark Theme**: Easy on the eyes, professional look
- **⚡ Fast**: Optimized for performance
- **🛡️ Safe**: Input validation and error protection

### Navigation Tips

- **Tab Key**: Navigate through all interactive elements
- **Enter Key**: Submit forms and buttons
- **Escape Key**: Cancel operations (where available)
- **Scroll**: View long event lists and graphs

---

## 🔧 Advanced Usage

### Custom Goals

Try these examples:

```text
"Find all JavaScript files and create a dependency map"
"Analyze the API endpoints and document their usage"
"Review the test coverage and suggest improvements"
"Extract all configuration settings and validate them"
```

### Understanding Skills

- **doc_ingest**: Processes documents and extracts content
- **dependency_map**: Analyzes code relationships
- **sum_review**: Creates intelligent summaries
- **ollama_generate**: Uses local AI for text generation

---

## 🚨 Troubleshooting

### Common Issues & Solutions

#### "Nothing happens when I click Execute"

**Check:**
1. Ollama is running: `ollama serve`
2. API server is up: `curl http://localhost:8000/api/uar/runs`
3. Web server is running: `curl http://localhost:5173`

#### "Error about missing model"

**Fix:**
```bash
ollama pull llama3.2:3b
```

#### "Connection refused"

**Check:**
1. All services are running in separate terminals
2. Correct ports: API (8000), Web (5173)
3. No firewall blocking the ports

#### "Web interface looks broken"

**Fix:**
1. Clear browser cache
2. Try a different browser
3. Check browser console for errors

#### "Python version errors"

**Fix:**
```bash
# Use Python 3.11 specifically
python3.11 -m pip install -e '.[dev]'
```

### Getting Help

- **Documentation**: Check the [docs/](docs/) folder
- **Issues**: Open an issue on GitHub
- **Logs**: Check terminal output for error messages

---

## 🎓 Success Criteria

You're successfully onboarded when you can:

1. ✅ **Start all services** without errors
2. ✅ **Execute a goal** through the web interface
3. ✅ **See real-time feedback** during processing
4. ✅ **View the results** in the graph and event log
5. ✅ **Understand the basic workflow**

---

## 🚀 What's Next?

### Explore Further

- **Try different goals** to see how UAR handles various tasks
- **Check the event log** to understand the execution flow
- **Examine the graph** to see skill dependencies
- **Read the documentation** for advanced features

### Development (Optional)

If you want to contribute:
- **Read [CONTRIBUTING.md](CONTRIBUTING.md)**
- **Check the [Architecture Guide](docs/ARCHITECTURE.md)**
- **Explore the codebase** structure

---

## 🎉 Congratulations!

**You're now a UAR user!** 🎊

You've successfully:
- Set up a complete AI agent runtime system
- Used the modern web interface
- Executed your first AI-orchestrated task
- Understood the basic concepts

Everything else is just expanding on these fundamentals. Welcome to the world of AI agent orchestration!

---

## 📚 Additional Resources

- **[Complete Documentation](DOCUMENTATION_INDEX.md)** - Full documentation index
- **[API Reference](docs/API.md)** - Backend API documentation
- **[Architecture Guide](docs/ARCHITECTURE.md)** - System design overview
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Advanced troubleshooting

---

*Happy agent orchestrating! 🤖✨*
