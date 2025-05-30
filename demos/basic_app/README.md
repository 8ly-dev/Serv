# Basic Serv App Demo

This is a minimal example of a Serv application that demonstrates the modern Route class system with signature-based routing.

## Features Demonstrated

*   **Route Classes**: Using `Route` base class instead of functions
*   **Handler Methods**: Methods like `handle_get()` for HTTP methods  
*   **Type Annotations**: `Annotated[str, TextResponse]` for typed responses
*   **Extension System**: Clean registration of route classes
*   **Modern Patterns**: Updated approach to Serv application structure

## Running the Demo

```bash
cd demos/basic_app
python main.py
```

Then visit:
- http://127.0.0.1:8000/ for the homepage
- http://127.0.0.1:8000/about for the about page

## Code Structure

```python
class HomeRoute(Route):
    async def handle_get(self) -> Annotated[str, TextResponse]:
        return "Hello from Serv!"

class BasicAppExtension(Listener):
    async def on_app_request_begin(self, router: Router) -> None:
        router.add_route("/", HomeRoute)
```

## What's New in This Version

This updated demo showcases the modern Serv approach:

1. **Route Classes**: Instead of function handlers, we use Route classes that inherit from the `Route` base class
2. **Handler Methods**: Methods like `handle_get()` automatically handle HTTP GET requests
3. **Type Safety**: Return type annotations specify response types like `TextResponse` and `HtmlResponse`
4. **Clean Architecture**: Better separation of concerns and more maintainable code

For more advanced features like parameter injection and multiple handlers per method, check out the [signature routing demo](../signature_routing_demo/). 