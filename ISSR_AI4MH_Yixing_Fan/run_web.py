import argparse
import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

def launch_dashboard(port: int = 7860):
    dashboard_path = os.path.join(PROJECT_ROOT, "web", "dashboard_app.py")
    print(f"🚀 Launching Interactive Crisis Triage Dashboard on http://localhost:{port} ...")
    env = os.environ.copy()
    env["GRADIO_SERVER_PORT"] = str(port)
    return subprocess.Popen([VENV_PYTHON, dashboard_path], env=env)

def launch_survey(port: int = 8081):
    survey_path = os.path.join(PROJECT_ROOT, "web", "survey_app.py")
    print(f"🌱 Launching Organic Data Collection Survey on http://localhost:{port} ...")
    env = os.environ.copy()
    env["SURVEY_PORT"] = str(port)
    return subprocess.Popen([VENV_PYTHON, survey_path], env=env)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Launch AI4MH Web Services")
    parser.add_argument("--dashboard", action="store_true", help="Launch the Gradio Interactive Triage Dashboard")
    parser.add_argument("--survey", action="store_true", help="Launch the FastAPI Organic Survey Portal")
    parser.add_argument("--all", action="store_true", help="Launch both Dashboard and Survey Portal")
    parser.add_argument("--survey-port", type=int, default=8081, help="Port for Survey Portal (default: 8081)")
    parser.add_argument("--dashboard-port", type=int, default=7860, help="Port for Triage Dashboard (default: 7860)")
    
    args = parser.parse_args()
    
    # Default to dashboard if no explicit flag given
    if not (args.dashboard or args.survey or args.all):
        args.all = True

    procs = []
    try:
        if args.dashboard or args.all:
            procs.append(launch_dashboard(port=args.dashboard_port))
        if args.survey or args.all:
            procs.append(launch_survey(port=args.survey_port))

        print("\n✨ Services running! Press Ctrl+C at any time to stop.")
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        for p in procs:
            p.terminate()
