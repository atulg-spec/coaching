from django.db import models
from django.conf import settings

class FeeStructure(models.Model):
    batch = models.ForeignKey('batches.Batch', on_delete=models.CASCADE)
    monthly_fee = models.DecimalField(max_digits=8, decimal_places=2)
    registration_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    effective_from = models.DateField()

class Payment(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('waived', 'Waived'),
    ]
    MODE_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='payments')
    batch = models.ForeignKey('batches.Batch', on_delete=models.CASCADE)
    month = models.DateField()
    amount_due = models.DecimalField(max_digits=8, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_mode = models.CharField(max_length=20, choices=MODE_CHOICES, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    receipt_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student} - ₹{self.month} - {self.batch}"

    class Meta:
        unique_together = ('student', 'batch', 'month')

    @property
    def balance_due(self):
        return self.amount_due - self.amount_paid

class PaymentTransaction(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=Payment.MODE_CHOICES)
    payment_date = models.DateField(auto_now_add=True)
    receipt_number = models.CharField(max_length=50, unique=True)
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.receipt_number} - ₹{self.amount}"

class Inquiry(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    interested_class = models.CharField(max_length=20)
    message = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_followed_up = models.BooleanField(default=False)

class StaffSalary(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
    ]
    MODE_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]
    staff = models.ForeignKey('staff.Staff', on_delete=models.CASCADE, related_name='salaries')
    month = models.DateField()  # Typically the 1st of the month the salary is for
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_mode = models.CharField(max_length=20, choices=MODE_CHOICES, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    remarks = models.TextField(blank=True)

    class Meta:
        unique_together = ('staff', 'month')
