from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    fullname = models.TextField(blank=True, null=True)
    age = models.TextField(blank=True, null=True)
    country = models.TextField(blank=True, null=True)
    county = models.TextField(blank=True, null=True)
    income = models.TextField(blank=True, null=True)
    cstatus = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    marital = models.TextField(blank=True, null=True)
    goals = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.user.username

class ModuleProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module_name = models.CharField(max_length=100)
    is_complete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.module_name}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # print(f"Creating UserProfile for {instance.username}")
        # UserProfile.objects.create(user=instance)
        pass

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'userprofile'):
        print(f"Saving UserProfile for {instance.username}")
        instance.userprofile.save()