import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from students.models import Student
from staff.models import Staff
from batches.models import Subject, Batch
from attendance.models import AttendanceSession, AttendanceRecord
from payments.models import Payment, FeeStructure

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with realistic Indian coaching center data (from Dec 2025).'

    def handle(self, *args, **kwargs):
        try:
            from faker import Faker
            fake = Faker('en_IN')
        except ImportError:
            self.stdout.write(self.style.ERROR('Faker is required. Please install it using: pip install faker'))
            return

        self.stdout.write(self.style.SUCCESS('Starting DB Seeding (Dec 2025)... This might take a few minutes.'))
        
        # Base date: Dec 1, 2025
        base_date = date(2025, 12, 1)

        # Avoid locking the SQLite database for the entire 3-minute process
        if True:
            # 1. Create Subjects
            self.stdout.write('Creating Subjects...')
            subject_names = [
                ('Mathematics', 'MATH'), ('Physics', 'PHY'), ('Chemistry', 'CHEM'),
                ('Biology', 'BIO'), ('Accountancy', 'ACCT'), ('Economics', 'ECO'),
                ('Business Studies', 'BST'), ('Computer Science', 'CS'), ('English', 'ENG')
            ]
            subjects = []
            for name, code in subject_names:
                sub, created = Subject.objects.get_or_create(name=name, code=code)
                subjects.append(sub)

            # 2. Create Staff (~60 staff)
            self.stdout.write('Creating Staff (~60)...')
            staff_list = list(Staff.objects.all())
            staff_count_to_create = max(0, 18 - len(staff_list))
            
            for i in range(staff_count_to_create):
                first_name = fake.first_name()
                last_name = fake.last_name()
                username = f"staff_{first_name.lower()}_{Staff.objects.count() + i + 1000}"
                
                user = User.objects.create_user(
                    username=username,
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    email=fake.email(),
                    role='staff',
                    phone=fake.phone_number()
                )
                
                designations = ['Teacher'] * 8 + ['Counselor', 'Admin Staff']
                designation = random.choice(designations)
                expertise = random.choice([s.name for s in subjects]) if designation == 'Teacher' else ''
                
                staff = Staff.objects.create(
                    user=user,
                    employee_id=f"EMP{2025}{(Staff.objects.count() + i):04d}",
                    designation=designation,
                    subject_expertise=expertise,
                    qualification=random.choice(["M.Sc.", "B.Ed.", "Ph.D.", "M.A.", "B.Tech"]),
                    date_of_joining=base_date - timedelta(days=random.randint(0, 365)),
                    salary=random.randint(25000, 80000),
                    address=fake.address()
                )
                if designation == 'Teacher':
                    staff_list.append(staff)
                
                if (i + 1) % 10 == 0:
                    self.stdout.write(f'  ... created {i + 1} staff members')

            # 3. Create Batches (~40 batches)
            self.stdout.write('Creating Batches (~40)...')
            classes = [str(i) for i in range(7, 13)]
            boards = ['CBSE', 'ICSE']
            batch_list = list(Batch.objects.all())
            
            batches_to_create = max(0, 40 - len(batch_list))
            teachers = [s for s in staff_list if s.designation == 'Teacher']
            
            for i in range(batches_to_create):
                c_level = random.choice(classes)
                b_board = random.choice(boards)
                b_name = f"Class {c_level} {b_board} - {random.choice(['Alpha', 'Beta', 'Gamma', 'Spark', 'Pinnacle'])} {i}"
                b_code = f"{b_board}{c_level}{Batch.objects.count() + i + 100}"
                
                teacher = random.choice(teachers) if teachers else None
                days = random.choice(['MWF', 'TTS', 'DAILY', 'WEEKEND'])
                slot = random.choice(['morning', 'afternoon', 'evening'])
                
                batch = Batch.objects.create(
                    batch_name=b_name,
                    batch_code=b_code,
                    class_level=c_level,
                    board=b_board,
                    teacher=teacher,
                    days=days,
                    time_slot=slot,
                    start_time=timezone.datetime.strptime("16:00", "%H:%M").time(),
                    end_time=timezone.datetime.strptime("18:00", "%H:%M").time(),
                    start_date=base_date,
                    max_students=40,
                    monthly_fee=random.choice([1500, 2000, 2500, 3000]),
                    room_number=f"Room {random.randint(101, 305)}"
                )
                
                # Add 1-3 random subjects to this batch
                batch_subjects = random.sample(subjects, random.randint(1, 3))
                batch.subjects.set(batch_subjects)
                batch_list.append(batch)
                
                if (i + 1) % 10 == 0:
                    self.stdout.write(f'  ... created {i + 1} batches')

            # 4. Create Students (~500 students)
            self.stdout.write('Creating Students (~500)...')
            student_count_to_create = max(0, 100 - Student.objects.count())
            all_students = []
            
            for i in range(student_count_to_create):
                first_name = fake.first_name()
                last_name = fake.last_name()
                username = f"std_{first_name.lower()}_{Student.objects.count() + i + 10000}"
                
                user = User.objects.create_user(
                    username=username,
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    email=fake.email(),
                    role='student',
                    phone=fake.phone_number()
                )
                
                c_level = random.choice(classes)
                b_board = random.choice(boards)
                
                student = Student.objects.create(
                    user=user,
                    student_id=f"STU{2025}{Student.objects.count() + i + 10000}",
                    date_of_birth=date(2010 - int(c_level) + 7, random.randint(1, 12), random.randint(1, 28)),
                    board=b_board,
                    current_class=c_level,
                    school_name=f"{fake.city()} Public School",
                    parent_name=fake.name_male(),
                    parent_phone=fake.phone_number(),
                    address=fake.address(),
                    admission_date=base_date + timedelta(days=random.randint(0, 30))
                )
                all_students.append(student)
                
                # Assign to 1-2 appropriate batches
                suitable_batches = [b for b in batch_list if b.class_level == c_level and b.board in [b_board, 'BOTH']]
                if suitable_batches:
                    enrolled_batches = random.sample(suitable_batches, min(len(suitable_batches), random.randint(1, 2)))
                    for b in enrolled_batches:
                        b.students.add(student)
                
                if (i + 1) % 50 == 0:
                    self.stdout.write(f'  ... created {i + 1} students (this is the slowest part due to secure password hashing!)')

            # 5. Generate some mock payments for Dec 2025 & Jan 2026
            self.stdout.write('Generating Payments...')
            payment_months = [date(2025, 12, 1), date(2026, 1, 1)]
            payments_created = 0
            
            for student in all_students:
                for batch in student.batches.all():
                    for month in payment_months:
                        # 80% chance they paid
                        status = 'paid' if random.random() < 0.8 else 'pending'
                        amount_paid = batch.monthly_fee if status == 'paid' else 0
                        
                        Payment.objects.create(
                            student=student,
                            batch=batch,
                            month=month,
                            amount_due=batch.monthly_fee,
                            amount_paid=amount_paid,
                            status=status,
                            payment_mode=random.choice(['upi', 'cash', 'bank_transfer']) if status == 'paid' else '',
                            payment_date=month + timedelta(days=random.randint(1, 10)) if status == 'paid' else None
                        )
                        payments_created += 1
                        if payments_created % 200 == 0:
                            self.stdout.write(f'  ... generated {payments_created} payment records')

            self.stdout.write(self.style.SUCCESS('Database successfully seeded with realistic Indian coaching center data!'))
            self.stdout.write(self.style.SUCCESS('All users (Staff/Students) have password: password123'))
