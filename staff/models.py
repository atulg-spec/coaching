from django.db import models
from django.conf import settings

class Staff(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=20, unique=True)
    designation = models.CharField(max_length=100)
    subject_expertise = models.CharField(max_length=200)
    qualification = models.CharField(max_length=200)
    date_of_joining = models.DateField()
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.designation}"

