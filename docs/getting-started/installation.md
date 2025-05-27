# Installation

This guide will help you install Serv and get your development environment set up.

## Requirements

Serv requires **Python 3.13 or higher**. Make sure you have a compatible Python version installed:

```bash
python --version
```

## Installing Serv

### Using pip

The easiest way to install Serv is using pip:

```bash
pip install getserving
```

!!! note "Package Name"
    The PyPI package is named `getserving` because `serv` was already taken. However, you'll still import it as `serv` in your Python code.

### Using uv (Recommended)

If you're using [uv](https://docs.astral.sh/uv/) (which we highly recommend for Python project management):

```bash
uv add getserving
```

### Development Installation

If you want to contribute to Serv or install the latest development version:

```bash
git clone https://github.com/8ly-dev/Serv.git
cd Serv
uv sync --group dev
```

## Verifying Installation

To verify that Serv is installed correctly, you can run:

```bash
python -c "import serv; print(serv.__version__)"
```

Or use the CLI:

```bash
serv --version
```

## Optional Dependencies

Serv has several optional dependencies that you might want to install depending on your use case:

### Template Rendering
For Jinja2 template support (already included by default):

```bash
pip install getserving[jinja]
```

### File Upload Support
For multipart form data and file upload support (already included by default):

```bash
pip install getserving[multipart]
```

### Development Tools
For development and testing:

```bash
pip install getserving[dev]
```

This includes:
- `pytest` and `pytest-asyncio` for testing
- `uvicorn` for running the development server
- `httpx` for making HTTP requests in tests
- `ruff` for linting and formatting

## ASGI Server

Serv is an ASGI framework, so you'll need an ASGI server to run your applications. We recommend [Uvicorn](https://www.uvicorn.org/):

```bash
pip install uvicorn
```

Or with uv:

```bash
uv add uvicorn
```

## IDE Setup

### VS Code

For the best development experience with VS Code, install the Python extension and configure it to use your virtual environment.

### PyCharm

PyCharm has excellent support for Python and ASGI applications. Make sure to configure your interpreter to use the virtual environment where Serv is installed.

## Next Steps

Now that you have Serv installed, you're ready to:

1. **[Quick Start](quick-start.md)** - Create your first Serv application
2. **[Your First App](first-app.md)** - Build a complete application step by step
3. **[Configuration](configuration.md)** - Learn about configuring Serv

## Troubleshooting

### Python Version Issues

If you're getting errors about Python version compatibility, make sure you're using Python 3.13 or higher:

```bash
python --version
```

### Import Errors

If you're getting import errors, make sure you're importing from `serv`, not `getserving`:

```python
# ✅ Correct
from serv import App

# ❌ Incorrect
from getserving import App
```

### Virtual Environment Issues

If you're having dependency conflicts, try creating a fresh virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install getserving
``` 