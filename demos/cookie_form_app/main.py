from dataclasses import dataclass
from serv.app import App
from serv.injectors import Cookie
from serv.routing import Router
from serv.requests import Request
from serv.responses import ResponseBuilder
from bevy import dependency
from bevy.containers import Container
from typing import Annotated, AsyncIterator # For middleware

# --- Application Setup ---
app = App()

# --- Routers Instances (these will be selected by middleware) ---
form_router = Router()
welcome_router = Router()

# --- Model Definitions ---

@dataclass
class NameForm:
    username: str

# --- Handler Definitions ---

# Form Router Handlers
async def show_name_form_handler(response: ResponseBuilder = dependency()):
    response.content_type("text/html")
    response.body(
        '''
        <html>
            <head><title>Enter Your Name</title></head>
            <body>
                <h1>Please enter your name:</h1>
                <form method="POST" action="/">
                    <label for="username">Name:</label>
                    <input type="text" id="username" name="username" required>
                    <button type="submit">Submit</button>
                </form>
            </body>
        </html>
        '''
    )

async def handle_name_submission_handler(request: Request = dependency(), response: ResponseBuilder = dependency()):
    form = await request.form(NameForm)

    if form.username:
        response.set_cookie("username", form.username, path="/", httponly=True, samesite="lax")
        print(f"Username submitted: {form.username}. Cookie set.")
    else:
        print("No username submitted in form.")
    
    response.redirect("/", status_code=303)

# Welcome Router Handlers
async def show_welcome_message_handler(request: Request = dependency(), response: ResponseBuilder = dependency()):
    username = request.cookies.get("username") # Should be present if this router is active
    if not username:
        # This is a safeguard; middleware should prevent this router from being used if no cookie.
        print("Error: Welcome router called without username cookie. Redirecting to form.")
        response.redirect("/", status_code=303) 
        return

    response.content_type("text/html")
    response.body(
        f'''
        <html>
            <head><title>Welcome!</title></head>
            <body>
                <h1>Hello, {username}!</h1>
                <p>Welcome back to the amazing Serv demo.</p>
                <form method="POST" action="/logout">
                    <button type="submit">Logout</button>
                </form>
            </body>
        </html>
        '''
    )

# Logout Handler
async def app_logout_handler(response: ResponseBuilder = dependency()): # No request needed if not used
    response.delete_cookie("username", path="/", httponly=True, samesite="lax")
    print("User logged out. Cookie deleted.")
    response.redirect("/", status_code=303)

# --- Add Routes to Router Instances ---
form_router.add_route("/", show_name_form_handler, methods=["GET"])
form_router.add_route("/", handle_name_submission_handler, methods=["POST"])

welcome_router.add_route("/", show_welcome_message_handler, methods=["GET"])
welcome_router.add_route("/logout", app_logout_handler, methods=["POST"])


# --- Middleware for Router Selection ---
async def cookie_based_router_middleware(router: Router = dependency(), username: Annotated[str, Cookie("username", default="")] = dependency()) -> AsyncIterator[None]:
    if username:
        print(f"Username cookie found: '{username}'. Setting welcome_router for the request.")
        router.add_router(welcome_router)
    else:
        print("No username cookie. Setting form_router for the request.")
        router.add_router(form_router)
    
    yield # Allow processing to continue to the (now selected) router
    
    # No cleanup needed after yield for this middleware

# --- Add Middleware to App ---
app.add_middleware(cookie_based_router_middleware)


# --- Run the application ---
if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("Uvicorn is not installed. Please install it with: pip install uvicorn")
        print("You also need 'bevy': pip install bevy")
        print("And 'serv' itself (e.g. pip install -e . from project root)")
    else:
        print("Starting Serv cookie_form_app demo (middleware routing) on http://127.0.0.1:8001")
        print("Access it at: http://127.0.0.1:8001/")
        print("Press Ctrl+C to stop.")
        uvicorn.run(app, host="127.0.0.1", port=8001) 