from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import MinValueValidator

import uuid
from decimal import Decimal

from .managers import UserManager

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    username = None

    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

class TeacherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )

    avatar = models.ImageField(upload_to='teachers_avatars/', blank=True)
    bio = models.TextField(blank=True)
    timezone = models.CharField(max_length=64, default="Europe/Warsaw")
    language = models.CharField(max_length=10, default='pl')
    currency = models.CharField(max_length=3, default="PLN")
    default_lesson_duration = models.PositiveSmallIntegerField(
        default=60, 
        validators=[MinValueValidator(15),]
    )

    default_lesson_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Teacher profile: {self.user.email}"