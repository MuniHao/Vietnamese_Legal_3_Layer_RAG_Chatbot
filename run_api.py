#!/usr/bin/env python3
"""
Script to run the API server with correct Python path
"""
import sys
import os
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def kill_port(port):
    """Kill any process using the specified port"""
    try:
        # Try to find process using the port (macOS/Linux)
        result = subprocess.run(
            ['lsof', '-ti', str(port)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    subprocess.run(['kill', '-9', pid], check=False)
                    print(f"Đã dừng process cũ (PID: {pid}) trên port {port}")
                except Exception as e:
                    print(f"Không thể dừng process {pid}: {e}")
    except FileNotFoundError:
        # lsof not available, skip
        pass
    except Exception as e:
        print(f"Lỗi khi kiểm tra port: {e}")

# Now import and run
if __name__ == "__main__":
    import uvicorn
    from src.api.main import app
    
    host = "0.0.0.0"
    port = 8000
    
    # Kill any existing process on the port
    kill_port(port)
    
    print(f"Starting Law Chat API server on {host}:{port}")
    print(f"Project root: {project_root}")
    print(f"API docs: http://localhost:{port}/docs")
    print(f"Health check: http://localhost:{port}/health")
    print("-" * 50)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )

