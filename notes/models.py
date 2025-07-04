from django.db import models
from clients.models import Client

class Note(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='notes')
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title} ({self.client.name})'
    
    