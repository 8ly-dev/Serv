class RouterPlugin(Plugin):
    async def on_app_request_begin(self, router: Router = dependency()) -> None:
        pass
