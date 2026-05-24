import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from staff.models import Staff
from students.models import Student
from batches.models import Subject, Batch
from payments.models import Payment, Inquiry
from attendance.models import AttendanceSession, AttendanceRecord

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with initial test data for Success Coaching Classes'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting database seed...')
        
        # 1. Create Staff
        if not User.objects.filter(username='teacher1').exists():
            u1 = User.objects.create_user('teacher1', 't1@example.com', 'staff123', first_name='Rajesh', last_name='Kumar', role='staff')
            Staff.objects.create(user=u1, employee_id='EMP001', designation='Senior Mathematics Teacher', subject_expertise='Mathematics (CBSE)', qualification='M.Sc. Mathematics', date_of_joining=date(2021, 5, 10), salary=45000.00)
        
        if not User.objects.filter(username='teacher2').exists():
            u2 = User.objects.create_user('teacher2', 't2@example.com', 'staff123', first_name='Priya', last_name='Sharma', role='staff')
            Staff.objects.create(user=u2, employee_id='EMP002', designation='Science Teacher', subject_expertise='Physics, Chemistry', qualification='B.Ed, B.Sc Physics', date_of_joining=date(2022, 6, 15), salary=38000.00)

        staff_members = list(Staff.objects.all())

        # 2. Create Subjects
        sub_math, _ = Subject.objects.get_or_create(name='Mathematics', code='MATH')
        sub_sci, _ = Subject.objects.get_or_create(name='Science', code='SCI')

        # 3. Create Batches
        b1, _ = Batch.objects.get_or_create(
            batch_code='CBSE-10-MATH',
            defaults={
                'batch_name': 'Class 10 CBSE Math Target',
                'class_level': '10', 'board': 'CBSE',
                'teacher': staff_members[0] if staff_members else None,
                'days': 'MWF', 'time_slot': 'evening',
                'start_time': '16:00:00', 'end_time': '17:30:00',
                'start_date': date.today() - timedelta(days=30),
                'monthly_fee': 1500.00
            }
        )
        b1.subjects.add(sub_math)

        b2, _ = Batch.objects.get_or_create(
            batch_code='ICSE-09-SCI',
            defaults={
                'batch_name': 'Class 9 ICSE Science Core',
                'class_level': '9', 'board': 'ICSE',
                'teacher': staff_members[1] if len(staff_members)>1 else None,
                'days': 'TTS', 'time_slot': 'evening',
                'start_time': '17:00:00', 'end_time': '18:30:00',
                'start_date': date.today() - timedelta(days=60),
                'monthly_fee': 1200.00
            }
        )
        b2.subjects.add(sub_sci)

        # 4. Create Students
        for i in range(1, 6):
            username = f'student{i}'
            if not User.objects.filter(username=username).exists():
                su = User.objects.create_user(username, f's{i}@example.com', 'success123', first_name=f'Student {i}', last_name='Test', role='student')
                student = Student.objects.create(
                    user=su, student_id=f'STU00{i}', date_of_birth=date(2008+i, 1, 1),
                    board='CBSE' if i % 2 == 0 else 'ICSE', current_class=str(9 if i % 2 != 0 else 10),
                    school_name='Lucknow Public School', parent_name='Parent Name',
                    parent_phone='9876543210', address='123 Hazratganj, Lucknow'
                )
                if i % 2 == 0:
                    student.batches.add(b1)
                else:
                    student.batches.add(b2)

        # 5. Create Inquiries
        if not Inquiry.objects.exists():
            Inquiry.objects.create(name='Amit Singh', phone='9988776655', interested_class='11', message='Looking for physics coaching.')
            Inquiry.objects.create(name='Sunita Verma', phone='8877665544', interested_class='8', message='Do you have weekend batches?')

        self.stdout.write(self.style.SUCCESS('Successfully seeded dummy data!'))
