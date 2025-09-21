from .models import Workspace

def get_user_workspace(user):
    return Workspace.objects.filter(owner=user).first()