import json
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from students.models import Student
from batches.models import Batch, Subject
from payments.models import Payment, PaymentTransaction
from attendance.models import AttendanceRecord, AttendanceSession
from staff.models import Staff
from chatbot.models import ChatbotConfig, ChatConversation, ChatMessage
from chatbot.natasha_agent import NatashaAgent


class NatashaDynamicAgentTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_user(
            username='admin_natasha',
            email='admin@natasha.com',
            password='password123',
            role='admin',
            is_staff=True,
            is_superuser=True
        )

        # Faculty staff
        self.staff_user = User.objects.create_user(
            username='teacher_john',
            email='john@school.com',
            password='password123',
            role='staff'
        )
        self.staff = Staff.objects.create(
            user=self.staff_user,
            employee_id='EMP101',
            designation='Senior Faculty',
            subject_expertise='Physics',
            salary=Decimal('45000.00'),
            date_of_joining=date(2025, 1, 1),
            is_active=True
        )

        # Batches
        self.batch_10 = Batch.objects.create(
            batch_name='Class 10 Physics Champ',
            batch_code='C10-PHY-01',
            class_level='10',
            board='CBSE',
            teacher=self.staff,
            days='MWF',
            time_slot='evening',
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timedelta(hours=1)).time(),
            start_date=timezone.now().date(),
            max_students=30,
            monthly_fee=Decimal('3000.00'),
            is_active=True
        )

        self.batch_9 = Batch.objects.create(
            batch_name='Class 9 Foundation',
            batch_code='C9-FND-01',
            class_level='9',
            board='CBSE',
            teacher=self.staff,
            days='TTS',
            time_slot='evening',
            start_time=timezone.now().time(),
            end_time=(timezone.now() + timedelta(hours=1)).time(),
            start_date=timezone.now().date(),
            max_students=20,
            monthly_fee=Decimal('2500.00'),
            is_active=True
        )

        # Student 1: Rahul Sharma (Class 10) - Has pending fee
        self.u1 = User.objects.create_user(username='rahul_s', first_name='Rahul', last_name='Sharma', password='pass')
        self.s1 = Student.objects.create(
            user=self.u1,
            student_id='STU001',
            date_of_birth=date(2009, 5, 10),
            board='CBSE',
            current_class='10',
            school_name='Delhi Public School',
            parent_name='Ramesh Sharma',
            parent_phone='+919876543210',
            parent_email='ramesh@test.com',
            admission_date=timezone.now().date() - timedelta(days=20),
            is_active=True
        )
        self.batch_10.students.add(self.s1)

        # Student 2: Anita Desai (Class 9) - Has low attendance & pending fee
        self.u2 = User.objects.create_user(username='anita_d', first_name='Anita', last_name='Desai', password='pass')
        self.s2 = Student.objects.create(
            user=self.u2,
            student_id='STU002',
            date_of_birth=date(2010, 8, 14),
            board='CBSE',
            current_class='9',
            school_name='St Xavier',
            parent_name='Sunita Desai',
            parent_phone='+919811223344',
            admission_date=timezone.now().date() - timedelta(days=45),
            is_active=True
        )
        self.batch_9.students.add(self.s2)

        # Student 3: Another student sharing parent phone with Student 2 (Sibling test)
        self.u3 = User.objects.create_user(username='rohan_d', first_name='Rohan', last_name='Desai', password='pass')
        self.s3 = Student.objects.create(
            user=self.u3,
            student_id='STU003',
            date_of_birth=date(2012, 3, 22),
            board='CBSE',
            current_class='7',
            school_name='St Xavier',
            parent_name='Sunita Desai',
            parent_phone='+919811223344',  # Same as Anita!
            admission_date=timezone.now().date() - timedelta(days=10),
            is_active=True
        )

        # Student 4: Rahul Verma (Disambiguation test)
        self.u4 = User.objects.create_user(username='rahul_v', first_name='Rahul', last_name='Verma', password='pass')
        self.s4 = Student.objects.create(
            user=self.u4,
            student_id='STU004',
            date_of_birth=date(2009, 2, 20),
            board='ICSE',
            current_class='8',
            school_name='City Montessori',
            parent_name='Vikram Verma',
            parent_phone='+919833445566',
            admission_date=timezone.now().date() - timedelta(days=5),
            is_active=True
        )

        # Payments
        Payment.objects.create(
            student=self.s1,
            batch=self.batch_10,
            month=date(2026, 4, 1),
            amount_due=Decimal('3000.00'),
            amount_paid=Decimal('3000.00'),
            status='paid',
            receipt_number='REC-001'
        )
        Payment.objects.create(
            student=self.s1,
            batch=self.batch_10,
            month=date(2026, 5, 1),
            amount_due=Decimal('3000.00'),
            amount_paid=Decimal('0.00'),
            status='pending'
        )

        # Anita has ₹6,000 pending
        Payment.objects.create(
            student=self.s2,
            batch=self.batch_9,
            month=date(2026, 4, 1),
            amount_due=Decimal('3000.00'),
            amount_paid=Decimal('0.00'),
            status='pending'
        )
        Payment.objects.create(
            student=self.s2,
            batch=self.batch_9,
            month=date(2026, 5, 1),
            amount_due=Decimal('3000.00'),
            amount_paid=Decimal('0.00'),
            status='pending'
        )

        # Attendance Session: Anita is absent, Rahul is present
        session = AttendanceSession.objects.create(
            batch=self.batch_9,
            date=timezone.now().date(),
            marked_by=self.admin_user
        )
        AttendanceRecord.objects.create(session=session, student=self.s2, status='absent')

        # Conversation
        self.conv = ChatConversation.objects.create(user=self.admin_user, title="Natasha Agent Session")

    def test_hinglish_and_natural_language_queries(self):
        """Test: 'Kitne bachche abhi institute mein padh rahe hain?' and 'What's our current student strength?'"""
        # Hindi / Hinglish query
        res1 = NatashaAgent.process_query("Kitne bachche abhi institute mein padh rahe hain?", self.conv, self.admin_user)
        self.assertIn("Student Enrollment Records", res1["reply"])
        self.assertIn("Total Students Found:** **4**", res1["reply"])

        # Alternative English wording
        res2 = NatashaAgent.process_query("What's our current student strength?", self.conv, self.admin_user)
        self.assertIn("Total Students Found:** **4**", res2["reply"])

    def test_novel_duplicate_parent_phone_query(self):
        """Test: 'Find students whose parents have the same registered mobile number.'"""
        res = NatashaAgent.process_query("Find students whose parents have the same registered mobile number.", self.conv, self.admin_user)
        reply = res["reply"]
        # Anita and Rohan share parent phone +919811223344
        self.assertIn("Anita Desai", reply)
        self.assertIn("Rohan Desai", reply)
        self.assertIn("+919811223344", reply)

    def test_novel_low_attendance_and_pending_fees_query(self):
        """Test: 'Which students have both low attendance and pending fees?'"""
        res = NatashaAgent.process_query("Which students have both low attendance and pending fees?", self.conv, self.admin_user)
        reply = res["reply"]
        self.assertIn("Students with Both Low Attendance & Outstanding Fees", reply)
        self.assertIn("Anita Desai", reply)

    def test_batch_student_faculty_ratio(self):
        """Test: 'Which batch has the highest student-to-faculty ratio?'"""
        res = NatashaAgent.process_query("Which batch has the highest student-to-faculty ratio?", self.conv, self.admin_user)
        reply = res["reply"]
        self.assertIn("Academic Batches & Student-to-Faculty Ratios", reply)
        self.assertIn("Class 10 Physics Champ", reply)

    def test_multi_turn_follow_up_reasoning(self):
        """
        Test multi-step conversation:
        Turn 1: Tell me about students who haven't paid their fees.
        Turn 2: Which class has the highest outstanding amount?
        Turn 3: Show me their parents' mobile numbers.
        Turn 4: How much money can we collect if everyone clears their dues?
        """
        # Turn 1
        r1 = NatashaAgent.process_query("Tell me about students who haven't paid their fees.", self.conv, self.admin_user)
        self.assertIn("Outstanding Fees Report", r1["reply"])
        self.assertIn("Anita Desai", r1["reply"])
        self.assertIn("Rahul Sharma", r1["reply"])

        # Turn 2: "Which class has the highest outstanding amount?"
        r2 = NatashaAgent.process_query("Which class has the highest outstanding amount?", self.conv, self.admin_user)
        self.assertIn("Pending Fees Grouped by Class", r2["reply"])
        self.assertIn("Class 9", r2["reply"])  # Anita has ₹6000 in Class 9

        # Turn 3: "Show me their parents' mobile numbers."
        r3 = NatashaAgent.process_query("Show me their parents' mobile numbers.", self.conv, self.admin_user)
        self.assertIn("+919811223344", r3["reply"])
        self.assertIn("+919876543210", r3["reply"])

        # Turn 4: "How much money can we collect if everyone clears their dues?"
        r4 = NatashaAgent.process_query("How much money can we collect if everyone clears their dues?", self.conv, self.admin_user)
        self.assertIn("Total Outstanding Amount", r4["reply"])
        self.assertIn("₹9,000", r4["reply"])

    def test_disambiguation_for_ambiguous_names(self):
        """Test asking for 'Rahul' when both Rahul Sharma and Rahul Verma exist."""
        res = NatashaAgent.process_query("What is Rahul's fee status?", self.conv, self.admin_user)
        reply = res["reply"]
        self.assertIn("Clarification Needed", reply)
        self.assertIn("Rahul Sharma", reply)
        self.assertIn("Rahul Verma", reply)

    def test_admitted_in_last_60_days_with_dues(self):
        """Test: 'Find students admitted in the last 60 days who have not completed their fee payments.'"""
        res = NatashaAgent.process_query("Find students admitted in the last 60 days who have not completed their fee payments.", self.conv, self.admin_user)
        reply = res["reply"]
        self.assertIn("Student Enrollment Records", reply)
        self.assertIn("Rahul Sharma", reply)
        self.assertIn("Anita Desai", reply)

    def test_api_send_message_admin_integration(self):
        """Test end-to-end API call from chat UI."""
        self.client.login(username='admin_natasha', password='password123')
        response = self.client.post(
            reverse('chatbot_api_send'),
            data=json.dumps({'message': 'Kitne bachche abhi institute mein padh rahe hain?'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("Total Students Found:** **4**", data["reply"])
        self.assertIsNotNone(data.get("kpis"))

    def test_llm_react_multi_step_comparison(self):
        """Test true LLM-driven multi-step ReAct loop: two sequential tool calls + grounded synthesis."""
        ChatbotConfig.objects.create(
            account_id='test-acc-id',
            api_token='test-token',
            is_active=True,
        )
        today = timezone.now().date()
        last_month = (today.replace(day=1) - timedelta(days=1))

        # Mock CloudflareAIService.query to simulate a 2-tool ReAct trace
        llm_replies = [
            {
                "success": True,
                "reply": json.dumps({
                    "action": "call_tool",
                    "tool": "query_students",
                    "parameters": {"admission_month": today.month, "admission_year": today.year}
                })
            },
            {
                "success": True,
                "reply": json.dumps({
                    "action": "call_tool",
                    "tool": "query_students",
                    "parameters": {"admission_month": last_month.month, "admission_year": last_month.year}
                })
            },
            {
                "success": True,
                "reply": json.dumps({
                    "action": "final_answer",
                    "reply": "### Admission Comparison\n- This month vs last month admissions retrieved from ERP.",
                    "kpis": [{"label": "This Month", "value": "3", "color": "emerald"}]
                })
            }
        ]
        with patch('chatbot.natasha_agent.CloudflareAIService.query', side_effect=llm_replies) as mock_query:
            res = NatashaAgent.process_query("Compare this month's admissions with last month's.", self.conv, self.admin_user)
            self.assertEqual(mock_query.call_count, 3)
            self.assertIn("Admission Comparison", res["reply"])
            self.assertEqual(res["kpis"][0]["label"], "This Month")

    def test_llm_react_disambiguation_and_unavailable_data(self):
        """Test LLM ReAct loop triggers disambiguation on ambiguous student name and handles unavailable modules honestly."""
        ChatbotConfig.objects.create(
            account_id='test-acc-id',
            api_token='test-token',
            is_active=True,
        )
        with patch(
            'chatbot.natasha_agent.CloudflareAIService.query',
            return_value={
                "success": True,
                "reply": json.dumps({
                    "action": "call_tool",
                    "tool": "query_students",
                    "parameters": {"search": "Rahul"}
                })
            }
        ):
            res = NatashaAgent.process_query("Show me Rahul's details", self.conv, self.admin_user)
            self.assertIn("Clarification Needed", res["reply"])
            self.assertIn("Rahul Sharma", res["reply"])
            self.assertIn("Rahul Verma", res["reply"])

        with patch(
            'chatbot.natasha_agent.CloudflareAIService.query',
            return_value={
                "success": True,
                "reply": json.dumps({
                    "action": "final_answer",
                    "reply": "Exam records and test marks are not stored in the current ERP database.",
                    "kpis": []
                })
            }
        ):
            res2 = NatashaAgent.process_query("What did Rahul Sharma score in his Physics exam?", self.conv, self.admin_user)
            self.assertIn("not stored in the current ERP", res2["reply"])

    def test_llm_react_unescaped_newlines_and_plain_markdown_recovery(self):
        """Test resilience when LLM emits literal newlines in JSON or plain Markdown after tool observation."""
        ChatbotConfig.objects.create(
            account_id='test-acc-id',
            api_token='test-token',
            is_active=True,
        )
        # Case 1: Literal newline inside JSON reply string
        literal_newline_json = '{"action": "final_answer", "reply": "### Student Profile: Rahul Sharma\n* **Class**: 10"}'
        with patch('chatbot.natasha_agent.CloudflareAIService.query', return_value={"success": True, "reply": literal_newline_json}):
            res = NatashaAgent.process_query("Hi", self.conv, self.admin_user)
            self.assertIn("Student Profile: Rahul Sharma", res["reply"])

        # Case 2: Step 1 calls tool, Step 2 replies in plain Markdown directly
        llm_seq = [
            {"success": True, "reply": json.dumps({"action": "call_tool", "tool": "query_students", "parameters": {"is_active": True}})},
            {"success": True, "reply": "### Active Students\nThere are **4** active students currently enrolled."}
        ]
        with patch('chatbot.natasha_agent.CloudflareAIService.query', side_effect=llm_seq):
            res2 = NatashaAgent.process_query("How many active students?", self.conv, self.admin_user)
            self.assertIn("Active Students", res2["reply"])
            self.assertIn("4", res2["reply"])
