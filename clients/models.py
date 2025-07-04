from django.db import models

class Client(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новий'),
        ('potential', 'Потенційний'),
        ('active', 'Активний'),
        ('inactive', 'Неактивний'),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20,blank=True)
    company = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} - {self.status}'