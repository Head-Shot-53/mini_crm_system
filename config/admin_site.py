from django.contrib.admin import AdminSite


class LumeraAdminSite(AdminSite):

    site_header = "Lumera Administration"

    site_title = "Lumera Admin"

    index_title = "Platform Administration"

    def has_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_superuser
        )