from django.contrib.admin.apps import AdminConfig


class LumeraAdminConfig(AdminConfig):
    default_site = (
        "config.admin_site.LumeraAdminSite"
    )