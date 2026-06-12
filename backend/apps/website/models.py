from django.db import models


# Create your models here.
class EarlyAccessUser(models.Model):
    email = models.EmailField(unique=True, blank=False, null=False)
    is_beta_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email
