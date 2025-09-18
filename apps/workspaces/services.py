from .models import Workspace

def create_personal_workspace(*, owner, name=None):
    if name is None:
        display_name = owner.first_name.strip()

        if not display_name: 
            display_name = owner.email.split("@", maxsplit=1)[0]

        name = f"{display_name} Teaching"

    return Workspace.objects.create(owner=owner, name=name)