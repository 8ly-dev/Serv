from typing import Annotated, Any
from serv.routes import Route, GetRequest, Form, Jinja2Response, HtmlResponse
from dataclasses import dataclass


class HomeRoute(Route):
    async def show_home_page(
        self, request: GetRequest
    ) -> Annotated[
        tuple[str, dict[str, Any]], 
        Jinja2Response
    ]:
        return "home.html", {"request": request}


@dataclass
class UserForm(Form):
    name: str
    email: str


class SubmitRoute(Route):
    async def receive_form_submission(self, form: UserForm) -> Annotated[str, HtmlResponse]:
        # In a real app, you'd save the data or process it
        return f"""
        <h1>Submission Received!</h1>
        <p>Thanks, {form.name}!</p>
        <p>Email: {form.email}</p>
        <a href=\"/\">Go Back</a>
        """
