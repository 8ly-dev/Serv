from serving.injectors import PathParam


class CredentialProvider:
    def has_credentials(self, permissions: set[str], token: PathParam[str]) -> bool:
        print(f"Checking if {permissions} are granted for {token}")
        if permissions == {"permission:demo:view-dashboard"}:
            return False

        return True
