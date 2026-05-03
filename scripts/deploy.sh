#!/bin/bash

# Production deployment script for UAR
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="universal-agent-runtime"
BACKUP_DIR="/var/backups/uar"
LOG_FILE="/var/log/uar/deploy.log"

# Helper functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1" >> "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >> "$LOG_FILE"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if running as root for production
    if [[ "$ENVIRONMENT" == "production" && $EUID -ne 0 ]]; then
        error "Production deployment must run as root"
    fi
    
    # Check required commands
    for cmd in python3 pip systemctl; do
        if ! command -v "$cmd" &> /dev/null; then
            error "Required command not found: $cmd"
        fi
    done
    
    # Check environment file
    if [[ ! -f ".env" ]]; then
        error ".env file not found. Copy .env.example and configure it first."
    fi
    
    # Check Python version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$python_version < 3.10" | bc -l) -eq 1 ]]; then
        error "Python 3.10+ required, found $python_version"
    fi
    
    log "Prerequisites check passed"
}

# Create backup
create_backup() {
    if [[ "$ENVIRONMENT" == "production" ]]; then
        log "Creating backup..."
        
        sudo mkdir -p "$BACKUP_DIR"
        backup_name="backup-$(date +%Y%m%d-%H%M%S)"
        backup_path="$BACKUP_DIR/$backup_name"
        
        # Backup current installation
        if [[ -d "/opt/uar" ]]; then
            sudo cp -r "/opt/uar" "$backup_path"
            log "Backup created at $backup_path"
        else
            warn "No existing installation to backup"
        fi
    fi
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."
    
    # Install Python dependencies
    python3 -m pip install --upgrade pip
    python3 -m pip install -e ".[dev]"
    
    log "Dependencies installed"
}

# Run tests
run_tests() {
    log "Running tests..."
    
    if ! python3 -m pytest tests/ -v --cov=uar --cov-report=term-missing; then
        error "Tests failed"
    fi
    
    log "All tests passed"
}

# Validate configuration
validate_config() {
    log "Validating configuration..."
    
    # Load and validate config
    python3 -c "
import sys
sys.path.insert(0, '.')
from uar.config import config

issues = config.validate()
if issues:
    print('Configuration issues:')
    for issue in issues:
        print(f'  - {issue}')
    sys.exit(1)
print('Configuration validation passed')
"
    
    log "Configuration validation passed"
}

# Deploy application
deploy_application() {
    log "Deploying application..."
    
    # Create directories
    sudo mkdir -p /opt/uar
    sudo mkdir -p /var/log/uar
    sudo mkdir -p /var/lib/uar
    
    # Copy application files
    sudo rsync -av --exclude='.git' --exclude='tests' --exclude='__pycache__' \
        --exclude='*.pyc' --exclude='node_modules' \
        . /opt/uar/
    
    # Set permissions
    sudo chown -R root:root /opt/uar
    sudo chmod -R 755 /opt/uar
    sudo chmod +x /opt/uar/scripts/*.sh
    
    log "Application deployed"
}

# Setup systemd service
setup_service() {
    log "Setting up systemd service..."
    
    cat > /tmp/uar.service << EOF
[Unit]
Description=Universal Agent Runtime API
After=network.target

[Service]
Type=exec
User=root
Group=root
WorkingDirectory=/opt/uar
Environment=PATH=/opt/uar/venv/bin
ExecStart=/opt/uar/venv/bin/python -m uvicorn uar.api.server:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/uar /var/log/uar

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=uar

[Install]
WantedBy=multi-user.target
EOF
    
    sudo mv /tmp/uar.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable uar
    
    log "Systemd service setup complete"
}

# Setup nginx reverse proxy (optional)
setup_nginx() {
    if command -v nginx &> /dev/null; then
        log "Setting up nginx reverse proxy..."
        
        cat > /tmp/uar-nginx.conf << EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}
EOF
        
        sudo mv /tmp/uar-nginx.conf /etc/nginx/sites-available/uar
        sudo ln -sf /etc/nginx/sites-available/uar /etc/nginx/sites-enabled/
        sudo nginx -t && sudo systemctl reload nginx
        
        log "Nginx setup complete"
    else
        warn "Nginx not found, skipping reverse proxy setup"
    fi
}

# Health check
health_check() {
    log "Performing health check..."
    
    # Wait for service to start
    sleep 5
    
    # Check service status
    if ! sudo systemctl is-active --quiet uar; then
        error "UAR service is not running"
    fi
    
    # Check API endpoint
    if ! curl -f http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
        error "Health check endpoint failed"
    fi
    
    log "Health check passed"
}

# Main deployment flow
main() {
    log "Starting UAR deployment..."
    
    # Load environment
    if [[ -f ".env" ]]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    check_prerequisites
    create_backup
    install_dependencies
    run_tests
    validate_config
    deploy_application
    setup_service
    setup_nginx
    
    # Start service
    log "Starting UAR service..."
    sudo systemctl start uar
    
    health_check
    
    log "Deployment completed successfully!"
    log "UAR is running at: http://127.0.0.1:8000"
    log "API documentation: http://127.0.0.1:8000/docs"
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        log "Production deployment complete"
        log "Monitor logs with: journalctl -u uar -f"
    fi
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "rollback")
        if [[ "$ENVIRONMENT" == "production" ]]; then
            log "Rolling back to previous version..."
            latest_backup=$(ls -t "$BACKUP_DIR" | head -n1)
            if [[ -n "$latest_backup" ]]; then
                sudo systemctl stop uar
                sudo rm -rf /opt/uar
                sudo cp -r "$BACKUP_DIR/$latest_backup" /opt/uar
                sudo systemctl start uar
                log "Rollback completed"
            else
                error "No backup found for rollback"
            fi
        else
            error "Rollback only available in production"
        fi
        ;;
    "status")
        sudo systemctl status uar
        ;;
    "logs")
        sudo journalctl -u uar -f
        ;;
    "help")
        echo "Usage: $0 {deploy|rollback|status|logs|help}"
        echo "  deploy  - Deploy the application (default)"
        echo "  rollback - Rollback to previous version (production only)"
        echo "  status  - Show service status"
        echo "  logs    - Show service logs"
        echo "  help    - Show this help"
        ;;
    *)
        error "Unknown command: $1"
        ;;
esac
