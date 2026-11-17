from django.db import models

class Notice(models.Model):
    TARGET_CHOICES = [
        ('all', 'All Users'),
        ('staff', 'Staff Only'),
    ]
    title = models.CharField(max_length=200)
    content = models.TextField()
    date_posted = models.DateTimeField(auto_now_add=True)
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-date_posted']
