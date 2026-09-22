import sys
from pathlib import Path

def main():
    from streamlit.web import cli
    app = Path(__file__).parent / "ui" / "wizard_app.py"
    sys.argv = ["streamlit", "run", str(app), *sys.argv[1:]]
    return cli.main()
