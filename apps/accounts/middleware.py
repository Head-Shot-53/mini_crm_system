from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                timezone_name = request.user.teacher_profile.timezone

                timezone.activate(ZoneInfo(timezone_name))

            except (AttributeError, ZoneInfoNotFoundError):
                timezone.deactivate()

        else:
            timezone.deactivate()

        return self.get_response(request)
        