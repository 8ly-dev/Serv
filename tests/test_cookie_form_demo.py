import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Import necessary components from the demo
from demos.cookie_form_app.main import (
    cookie_based_router_middleware,
    # To potentially mock or spy
)
from serv.app import App


@pytest_asyncio.fixture
async def demo_app():
    app = App(dev_mode=True)
    # Add routes to the routers directly as they are in the demo
    # form_router and welcome_router are already configured in their import
    app.add_middleware(cookie_based_router_middleware)
    # The middleware adds either form_router or welcome_router to the app's root router.
    return app


@pytest.mark.asyncio
async def test_form_submission_no_cookie(demo_app: App):
    """
    Tests submitting the name form when no 'username' cookie is initially present.
    This should use the form_router, process the POST, set the cookie, and redirect.
    """
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1:8000"
    ) as client:
        # Data to be sent as if it's from a form
        form_data = {"username": "ServUser"}

        # Make the POST request to submit the form
        response = await client.post("/", data=form_data)
        # 1. Check for redirect
        assert response.status_code == 303  # As per handle_name_submission_handler
        assert response.headers["location"] == "/"

        # 2. Check if the cookie was set
        assert "username" in response.cookies
        assert response.cookies["username"] == "ServUser"

        # 3. (Optional) Verify that a subsequent GET request (with the new cookie)
        #    now routes to the welcome page.
        #    The client automatically handles cookies set by the server for subsequent requests.
        welcome_response = await client.get("/")
        assert welcome_response.status_code == 200
        assert "<h1>Hello, ServUser!</h1>" in welcome_response.text


@pytest.mark.asyncio
async def test_get_form_no_cookie(demo_app: App):
    """
    Tests GET / when no 'username' cookie is present.
    Should display the name submission form.
    """
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1:8000"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "<h1>Please enter your name:</h1>" in response.text
        assert '<form method="POST" action="/">' in response.text


@pytest.mark.asyncio
async def test_get_welcome_with_cookie(demo_app: App):
    """
    Tests GET / when 'username' cookie is present.
    Should display the welcome message.
    """
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1:8000"
    ) as client:
        # Manually set the cookie for this request
        client.cookies.set("username", "TestUser")

        response = await client.get("/")
        assert response.status_code == 200
        assert "<h1>Hello, TestUser!</h1>" in response.text
        assert '<form method="POST" action="/logout">' in response.text


@pytest.mark.asyncio
async def test_logout(demo_app: App):
    """
    Tests POST /logout when 'username' cookie is present.
    Should delete the cookie and redirect.
    """
    transport = ASGITransport(app=demo_app)
    async with AsyncClient(
        transport=transport, base_url="http://127.0.0.1:8000"
    ) as client:
        # Set a cookie to simulate a logged-in user
        client.cookies.set("username", "LogoutUser")

        # Make the POST request to /logout
        response = await client.post("/logout")

        # 1. Check for redirect
        assert response.status_code == 303
        assert response.headers["location"] == "/"

        # 2. Check if the cookie was deleted
        # httpx client might still show it in response.cookies if it was set by server then deleted in same response.
        # A better check is that a subsequent request does not have the cookie or goes to the form page.
        # However, the cookie should have Max-Age=0 or Expires in the past.
        # For simplicity, we'll check if the cookie value is now empty or if 'username' is not in client.cookies for next request

        # Check Set-Cookie header for deletion attributes
        set_cookie_header = response.headers.get("set-cookie")
        assert set_cookie_header is not None
        # Example: username=; Max-Age=0; Path=/; httponly; samesite=lax
        # We expect to see that the cookie value is cleared and/or Max-Age=0 or an old Expires date
        assert "username=;" in set_cookie_header or 'username="";' in set_cookie_header
        assert (
            "Max-Age=0" in set_cookie_header or "expires=" in set_cookie_header.lower()
        )

        # 3. Verify that a subsequent GET request routes to the form page (as cookie should be gone)
        # Explicitly clear the cookie from the client to ensure it doesn't send it on the next request,
        # simulating a fresh request or a client that has fully processed the deletion.
        if "username" in client.cookies:
            del client.cookies["username"]

        after_logout_response = await client.get("/")
        assert after_logout_response.status_code == 200
        assert "<h1>Please enter your name:</h1>" in after_logout_response.text
        assert "username" not in client.cookies or client.cookies["username"] == ""
