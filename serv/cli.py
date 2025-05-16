import argparse
import uvicorn
import os
from pathlib import Path
import importlib

from serv.app import App
from serv.config import load_raw_config, setup_app_from_config, ServConfigError, DEFAULT_CONFIG_FILE
from serv.bundled_plugins.welcome import WelcomePlugin

# Store parsed args globally for the reload helper. This is not ideal but helps the workaround.
_cli_args_for_reload_helper = None

def run_server():
    global _cli_args_for_reload_helper

    parser = argparse.ArgumentParser(description="Serv ASGI Web Framework CLI")
    parser.add_argument(
        "app_module", 
        nargs="?",
        default="serv.app:App", 
        help="The application module and instance to run (e.g., 'my_app:app'). Defaults to 'serv.app:App' for a basic Serv app."
    )
    parser.add_argument(
        "--host", 
        default=os.getenv("SERV_HOST", "127.0.0.1"), 
        help="Host IP to bind the server to. Default: 127.0.0.1 (or SERV_HOST env var)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=int(os.getenv("SERV_PORT", "8000")), 
        help="Port to bind the server to. Default: 8000 (or SERV_PORT env var)"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload on code changes."
    )
    parser.add_argument(
        "--workers", 
        type=int, 
        default=int(os.getenv("SERV_WORKERS", "1")), 
        help="Number of worker processes. Default: 1 (or SERV_WORKERS env var)"
    )
    parser.add_argument(
        "--config",
        default=os.getenv("SERV_CONFIG_PATH", DEFAULT_CONFIG_FILE),
        help=f"Path to the configuration YAML file. Defaults to '{DEFAULT_CONFIG_FILE}' in CWD (or SERV_CONFIG_PATH env var)."
    )
    parser.add_argument(
        "--factory",
        action="store_true",
        help="Treat app_module as an application factory (a function that returns an App instance) instead of a direct App instance."
    )

    args = parser.parse_args()
    _cli_args_for_reload_helper = args # Store for the reload helper

    # App creation and configuration is now deferred until after arg parsing.
    # If --help was used, argparse would have exited before this point.

    app_instance: App
    try:
        if args.factory:
            factory_path, factory_name = args.app_module.rsplit(":", 1)
            factory_module = importlib.import_module(factory_path)
            app_factory = getattr(factory_module, factory_name)
            if not callable(app_factory):
                raise ServConfigError(f"App factory '{args.app_module}\' is not callable.")
            app_instance = app_factory()
            if not isinstance(app_instance, App):
                raise ServConfigError(f"App factory '{args.app_module}\' did not return an instance of serv.App.")
        elif args.app_module == "serv.app:App":
            app_instance = App()
        else:
            module_path, app_name = args.app_module.rsplit(":", 1)
            app_module_obj = importlib.import_module(module_path)
            app_instance = getattr(app_module_obj, app_name)
            if not isinstance(app_instance, App):
                raise ServConfigError(f"Specified app '{args.app_module}\' is not an instance of serv.App.")
    except Exception as e:
        print(f"Error: Could not load app '{args.app_module}\': {str(e)}")
        return # Exit if app loading fails

    # Load config and setup app (only if not just displaying help etc.)
    config_loaded_successfully = False
    raw_config = {} # Ensure raw_config is always a dict
    try:
        loaded_data = load_raw_config(args.config)
        if loaded_data: # Ensure loaded_data is not None or empty if that's possible from load_raw_config
            raw_config = loaded_data
            # Defer setup_app_from_config until after we check for the welcome plugin condition
            config_loaded_successfully = True # Mark that we have a config to process

    except ServConfigError as e:
        print(f"Configuration Error: {str(e)}. Proceeding with default/minimal app configuration.")
    except Exception as e:
        print(f"Unexpected error during config loading: {str(e)}. Proceeding with default/minimal app configuration.")

    # Conditionally load WelcomePlugin for default app if no other plugins are configured
    if args.app_module == "serv.app:App":
        # Check if plugins are defined in the loaded config.
        # An empty list of plugins also means "no user-defined plugins".
        # If raw_config is empty (e.g. file not found), .get("plugins", []) will yield [].
        user_has_plugins_configured = bool(raw_config.get("plugins"))

        if not user_has_plugins_configured:
            print("INFO: No user plugins configured for default app. Attempting to load bundled WelcomePlugin.")
            try:
                welcome_plugin_instance = WelcomePlugin()
                app_instance.add_plugin(welcome_plugin_instance)
                print("INFO: Bundled WelcomePlugin loaded.")
            except Exception as e:
                print(f"ERROR: Could not load bundled WelcomePlugin: {str(e)}")

    # Now, if a config was loaded, process its plugins and middleware
    if config_loaded_successfully:
        try:
            print(f"INFO: Setting up app from configuration file: {args.config}")
            setup_app_from_config(app_instance, raw_config)
            print("INFO: App setup from configuration file completed.")
        except ServConfigError as e:
            print(f"Configuration Error during setup_app_from_config: {str(e)}.")
            # App continues with potentially partial config from welcome plugin
        except Exception as e:
            print(f"Unexpected error during setup_app_from_config: {str(e)}.")

    app_target_for_uvicorn: str | App
    if args.reload:
        if args.factory:
            app_target_for_uvicorn = args.app_module
        elif args.app_module == "serv.app:App":
            print("INFO: Using --reload with default 'serv.app:App'. Configuration will be applied via serv.cli._get_configured_app_for_reload.")
            app_target_for_uvicorn = "serv.cli:_get_configured_app_for_reload"
        else:
            print(f"WARNING: Using --reload with a direct app string '{args.app_module}\'."
                  f" If this is not a factory, serv_config.yaml might not apply consistently on reloads."
                  f" Consider using an app factory (module:function that returns App) with --factory.")
            app_target_for_uvicorn = args.app_module 
    else:
        app_target_for_uvicorn = app_instance

    uvicorn_kwargs = {
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
        "workers": args.workers if not args.reload else None,
        "factory": args.factory and args.reload and (app_target_for_uvicorn != "serv.cli:_get_configured_app_for_reload")
    }
    uvicorn_kwargs = {k: v for k, v in uvicorn_kwargs.items() if v is not None and v is not False}

    print(f"Starting server for '{app_target_for_uvicorn if isinstance(app_target_for_uvicorn, str) else app_instance.__class__.__name__}\' on http://{args.host}:{args.port}")
    if args.reload:
        print(f"Auto-reload enabled.")
        if not isinstance(app_target_for_uvicorn, str):
            print("ERROR: Inconsistent state. For --reload, app target must be an import string.")
            return
    
    uvicorn.run(app_target_for_uvicorn, **uvicorn_kwargs)

def _get_configured_app_for_reload():
    global _cli_args_for_reload_helper
    
    print("Reload Function: Creating new App instance and applying config (if any).")
    app = App() # Create a new app instance for the reloaded process
    
    config_path_to_load = None
    if _cli_args_for_reload_helper and _cli_args_for_reload_helper.config:
        config_path_to_load = _cli_args_for_reload_helper.config
        print(f"Reload Function: Attempting to load config from: {config_path_to_load}")
    else:
        print(f"Reload Function: No CLI args found for config path, will try default '{DEFAULT_CONFIG_FILE}'.")

    try:
        raw_config = load_raw_config(config_path_to_load) 
        if raw_config:
            setup_app_from_config(app, raw_config)
            print("Reload Function: Configuration applied successfully.")
        else:
            print("Reload Function: No config file found or config was empty.")
    except ServConfigError as e:
        print(f"Reload Function: Configuration Error: {str(e)}")
    except Exception as e:
        print(f"Reload Function: Unexpected error during config loading: {str(e)}")
    return app

if __name__ == "__main__":
    # This __main__ block in serv/cli.py is less critical if serv/__main__.py is the primary entry point.
    # However, to ensure _cli_args_for_reload_helper gets populated if someone runs `python serv/cli.py` directly:
    parser_for_main = argparse.ArgumentParser(add_help=False) # Minimal parser just for config path
    parser_for_main.add_argument("--config", default=os.getenv("SERV_CONFIG_PATH", DEFAULT_CONFIG_FILE))
    # Potentially other args needed by _get_configured_app_for_reload if it evolves
    parsed_args_for_main, _ = parser_for_main.parse_known_args()
    _cli_args_for_reload_helper = parsed_args_for_main

    run_server() 