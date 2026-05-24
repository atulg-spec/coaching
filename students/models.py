from django.db import models
from django.conf import settings

class Student(models.Model):
    BOARD_CHOICES = [('CBSE', 'CBSE'), ('ICSE', 'ICSE')]
    CLASS_CHOICES = [(str(i), f'Class {i}') for i in range(5, 13)]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)
    date_of_birth = models.DateField()
    board = models.CharField(max_length=10, choices=BOARD_CHOICES)
    current_class = models.CharField(max_length=5, choices=CLASS_CHOICES)
    school_name = models.CharField(max_length=200)
    parent_name = models.CharField(max_length=100)
    parent_phone = models.CharField(max_length=15)
    parent_email = models.EmailField(blank=True)
    address = models.TextField()
    admission_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(upload_to='students/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.get_full_name()} | Class {self.current_class} {self.board}"

