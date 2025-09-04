import os

from serving.serv import Serv


def create_app():
    """Create the Serv application using environment variables for configuration.
    
    The working directory should be set by the CLI before this is called.
    The environment can be set via SERV_ENVIRONMENT env variable.
    """
    settings = {}
    
    # Check for environment variable (set by CLI or user)
    if 'SERV_ENVIRONMENT' in os.environ:
        settings['environment'] = os.environ['SERV_ENVIRONMENT']
    
    # Working directory is handled by the CLI changing to that directory
    # before launching uvicorn, so config files will be found in the current directory
    
    return Serv(**settings)


# Create the app instance
serv = create_app()
app = serv.app