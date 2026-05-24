from django.db import models

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Batch(models.Model):
    DAYS_CHOICES = [
        ('MWF', 'Mon-Wed-Fri'),
        ('TTS', 'Tue-Thu-Sat'),
        ('DAILY', 'Daily'),
        ('WEEKEND', 'Weekend'),
    ]
    TIME_SLOT_CHOICES = [
        ('morning', 'Morning (6AM–9AM)'),
        ('afternoon', 'Afternoon (12PM–3PM)'),
        ('evening', 'Evening (4PM–7PM)'),
    ]

    batch_name = models.CharField(max_length=100)
    batch_code = models.CharField(max_length=20, unique=True)
    class_level = models.CharField(max_length=5, choices=[(str(i), f'Class {i}') for i in range(5, 13)])
    board = models.CharField(max_length=10, choices=[('CBSE', 'CBSE'), ('ICSE', 'ICSE'), ('BOTH', 'Both')])
    subjects = models.ManyToManyField(Subject, blank=True)
    teacher = models.ForeignKey('staff.Staff', on_delete=models.SET_NULL, null=True)
    students = models.ManyToManyField('students.Student', blank=True, related_name='batches')
    days = models.CharField(max_length=20, choices=DAYS_CHOICES)
    time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField()
    max_students = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    room_number = models.CharField(max_length=20, blank=True)
    monthly_fee = models.DecimalField(max_digits=8, decimal_places=2)

    @property
    def current_strength(self):
        return self.students.filter(is_active=True).count()

    def __str__(self):
        return f"{self.batch_name} ({self.batch_code})"

