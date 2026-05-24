from django.core.management.base import BaseCommand
from django.utils import timezone
from students.models import Student
from payments.models import Payment
from datetime import date

class Command(BaseCommand):
    help = 'Generates pending monthly fee records for all active students'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        first_day_of_month = date(today.year, today.month, 1)
        
        active_students = Student.objects.filter(is_active=True)
        created_count = 0
        
        for student in active_students:
            for batch in student.batches.all():
                payment, created = Payment.objects.get_or_create(
                    student=student,
                    batch=batch,
                    month=first_day_of_month,
                    defaults={
                        'amount_due': batch.monthly_fee,
                        'status': 'pending'
                    }
                )
                if created:
                    created_count += 1
                    
        self.stdout.write(self.style.SUCCESS(f'Successfully generated {created_count} pending fee records for {first_day_of_month.strftime("%B %Y")}.'))
