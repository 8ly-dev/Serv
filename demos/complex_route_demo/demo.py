from serv.routes import Route, GetRequest, Form, Jinja2Response, HtmlResponse, RedirectResponse
from serv.exceptions import HTTPNotFoundException, HTTPMethodNotAllowedException
from dataclasses import dataclass


class HomeRoute(Route):
    async def show_home_page(self, request: GetRequest) -> Jinja2Response:
        return Jinja2Response("home.html", {"request": request})


@dataclass
class UserForm(Form):
    name: str
    email: str


class SubmitRoute(Route):
    async def receive_form_submission(self, form: UserForm) -> HtmlResponse:
        # In a real app, you'd save the data or process it
        response_html = f"""
        <h1>Submission Received!</h1>
        <p>Thanks, {form.name}!</p>
        <p>Email: {form.email}</p>
        """
        response_html += "<a href=\"/\">Go Back</a>"
        return HtmlResponse(response_html)
