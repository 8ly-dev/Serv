# Testing the Serv CLI

This document outlines the approach to end-to-end testing of the Serv Command Line Interface (CLI).

## Overview

The Serv CLI provides various commands to manage Serv applications:
- `serv app init` - Initialize a new Serv project
- `serv app details` - Display application configuration 
- `serv plugin enable/disable/list/validate` - Manage plugins
- `serv create plugin/middleware/route/entrypoint` - Create components
- `serv launch` - Start the application server

End-to-end testing of the CLI ensures these commands work correctly and produce expected side effects.

## Testing Approach

Our testing approach consists of two main strategies:

1. **Command execution validation** - Test that CLI commands execute successfully and produce expected output and file artifacts.
2. **HTTP behavior validation** - Test that CLI-configured applications behave correctly when handling HTTP requests.

## Current Test Coverage

Currently, we have two test files for CLI functionality:

1. `tests/e2e/test_cli_commands.py` - Tests basic CLI functionality:
   - `test_init_command` - Tests `serv app init`
   - `test_create_plugin_command` - Tests creating a plugin structure
   - `test_app_details_command` - Tests `serv app details`
   - `test_launch_dry_run` - Tests `serv launch --dry-run`
   - `test_cli_with_async_client` - Tests a basic app created via CLI

2. `tests/e2e/test_cli_http.py` - Tests HTTP behavior with CLI plugins and middleware:
   - `test_plugin_enable_disable` *(xfailed)* - Tests enabling and disabling a plugin
   - `test_multiple_plugins` *(xfailed)* - Tests multiple plugins working together
   - `test_middleware_enable_disable` *(xfailed)* - Tests middleware functionality
   - `test_api_endpoint_with_json` *(xfailed)* - Tests JSON API plugin

## Known Issues and Future Work

Some tests are currently marked as xfailed due to issues with plugin loading:

1. **Entry field missing in plugin.yaml** - The plugin creation and plugin loader code expect an 'entry' field in plugin.yaml, but the tests don't provide it correctly. This needs to be addressed by either:
   - Updating the plugin templates in the tests to include the correct entry field
   - Enhancing the plugin loader to handle different formats of plugin.yaml

2. **Non-interactive mode support** - We've added the `--non-interactive` flag to support testing without user input. This should be applied consistently across all CLI command tests.

3. **Test isolation and cleanup** - Ensure that tests clean up after themselves to prevent test pollution.

## How to Run Tests

To run all CLI tests:
```bash
python -m pytest tests/e2e/test_cli_commands.py tests/e2e/test_cli_http.py
```

To run just the passing tests:
```bash
python -m pytest tests/e2e/test_cli_commands.py
``` 