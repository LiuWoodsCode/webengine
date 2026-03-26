import platform

def build_user_agent(project_version: str = "0.0.0") -> str:
    """
    Return a concise user-agent string used by Project Crimew.
    """
    python_version = platform.python_version()
    system_os = platform.system()
    architecture = platform.architecture()[0]
    return (
        f"Mozilla/5.0 ({system_os}; {architecture}) "
        f"Python/{python_version} ProjectCrimew/{project_version}"
    )