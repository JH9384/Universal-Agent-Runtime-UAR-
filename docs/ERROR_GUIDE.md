# Common Error Messages & Solutions

This guide helps you troubleshoot common errors and provides actionable solutions.

## Configuration Errors

### Error: "SECRET_KEY must be explicitly set"
**Cause**: Using default secret key in production
**Solution**:
```bash
# Generate a secure key
python -c 'import secrets; print(secrets.token_urlsafe(32))'
# Add to .env
SECRET_KEY=<generated-key>
```

### Error: "Variable name changed to METRICS_ENABLED"
**Cause**: Using deprecated environment variable name
**Solution**:
```bash
# In your .env file, rename:
ENABLE_METRICS=false  # OLD
METRICS_ENABLED=true  # NEW
```

### Error: "Port 99999 is out of valid range (1-65535)"
**Cause**: Invalid port number in configuration
**Solution**:
```bash
# Use a valid port in .env
API_PORT=8000  # Valid range: 1-65535
```

## Skill Errors

### Error: "Ollama connection refused"
**Cause**: Ollama service not running
**Solution**:
```bash
# Start Ollama
ollama serve

# Verify it's running
curl http://127.0.0.1:11434/api/tags
```

### Error: "Ollama model not found: llama3.2:3b"
**Cause**: Model not downloaded
**Solution**:
```bash
# Pull the model
ollama pull llama3.2:3b

# List available models
ollama list
```

### Error: "doc_ingest failed: No documents found"
**Cause**: Input path is empty or invalid
**Solution**:
```bash
# Verify your input_path is set correctly
# Use the file picker in the UI to select a valid directory
# Or set input_path to a real directory path
```

### Error: "GraphRAG workspace not initialized"
**Cause**: Trying to query GraphRAG index without initializing first
**Solution**:
```bash
# Run graphrag_init first, then graphrag_index
# Skills order: ['graphrag_init', 'graphrag_index', 'graphrag_query']
```

### Error: "autonomi package not installed"
**Cause**: Autonomi dependencies missing
**Solution**:
```bash
# Install optional dependencies
pip install -e '.[autonomi]'
```

### Error: "ALM service unreachable"
**Cause**: ALM service URL not configured or service not running
**Solution**:
```bash
# Add to .env
ALM_SERVICE_URL=http://your-alm-service:port
# Verify the service is running
curl $ALM_SERVICE_URL/health
```

## API Errors

### Error: "HTTP 401: Unauthorized"
**Cause**: Missing or invalid API key
**Solution**:
```bash
# Add API keys to .env
API_KEYS=your-key:user:admin
# Format: key:user:tier (comma-separated for multiple)
```

### Error: "HTTP 413: Payload Too Large"
**Cause**: File exceeds upload limit (default 50MB)
**Solution**:
```bash
# Increase limit in .env
UAR_MAX_UPLOAD_BYTES=104857600  # 100MB
```

### Error: "HTTP 400: Bad Request — validation error"
**Cause**: Invalid request data
**Solution**:
- Check goal is not empty
- Verify selected skills are valid
- Check input_path is within PROJECT_ROOT

## File System Errors

### Error: "Path traversal detected"
**Cause**: Attempting to access files outside allowed directory
**Solution**:
```bash
# Ensure input_path is within PROJECT_ROOT
# Use the file picker in the UI for safe selection
# Or set PROJECT_ROOT to the parent directory you need
```

### Error: "Permission denied"
**Cause**: Insufficient file system permissions
**Solution**:
```bash
# Check file permissions
ls -la /path/to/file
# Grant read access if needed
chmod +r /path/to/file
```

## Network Errors

### Error: "Connection refused"
**Cause**: Service not running or wrong port
**Solution**:
```bash
# Check if API server is running
curl http://localhost:8000/api/health

# If not running, start it:
make up
```

### Error: "Timeout"
**Cause**: Operation took longer than allowed time
**Solution**:
```bash
# Increase timeout in .env
UAR_TIMEOUT_SECONDS=300  # 5 minutes
```

## Getting Help

### Validate Your Configuration
```bash
python scripts/validate_config.py
```
This checks your .env file and provides helpful guidance.

### Check System Status
```bash
curl http://localhost:8000/api/status
```
Shows available skills and system health.

### View Logs
Check the server logs for detailed error information:
```bash
# If running via make up
# Logs appear in your terminal
```

### Still Stuck?
1. Check the [ONBOARDING.md](../ONBOARDING.md) guide
2. Review the [Skill Guide](#) in the web UI
3. Open an issue with the error message and steps to reproduce
