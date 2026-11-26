"""
Natasha Intelligence Engine.
Orchestrates natural language intent recognition, multi-turn conversational context,
entity extraction, disambiguation, and database response presentation.
"""

import re
import logging
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone

from . import natasha_tools
from .models import ChatbotConfig
from .services import CloudflareAIService

logger = logging.getLogger(__name__)


class NatashaEngine:
    """
    Intelligent personal administrative assistant for coaching institute.
    """

    @classmethod
    def process_query(cls, user_text: str, conversation, user=None) -> dict:
        """
        Main entry point for processing an admin's natural language request.
        Maintains conversational state in conversation.context_data.
        """
        query = user_text.strip()
        context = conversation.context_data or {}
        lower_q = query.lower()

        # Check for multi-turn follow-ups first
        follow_up_res = cls._check_follow_up(lower_q, context, conversation)
        if follow_up_res:
            return follow_up_res

        # 1. Active / Total Student Count
        if cls._is_student_count_query(lower_q):
            cls_match = cls._extract_class_number(lower_q)
            board_match = cls._extract_board(lower_q)
            res = natasha_tools.get_student_enrollment_stats(class_level=cls_match, board=board_match)
            cls._update_context(conversation, {
                "last_intent": "student_count",
                "student_ids": res.get("student_ids", []),
                "last_class": cls_match
            })
            return {"reply": res["markdown"], "kpis": res.get("kpis")}

        # 2. Student Admissions in period (e.g. "how many students admitted this month")
        if any(p in lower_q for p in ["admitted this month", "admissions this month", "admitted recently", "new admissions"]):
            period = "last_month" if "last month" in lower_q else "this_month"
            res = natasha_tools.get_admitted_students(period=period)
            cls._update_context(conversation, {
                "last_intent": "admissions",
                "student_ids": res.get("student_ids", [])
            })
            return {"reply": res["markdown"]}

        # 3. Classes with highest pending fees
        if ("highest pending" in lower_q or "highest dues" in lower_q or 
            ("which class" in lower_q and ("pending" in lower_q or "fee" in lower_q))):
            res = natasha_tools.get_pending_fees_by_class()
            cls._update_context(conversation, {"last_intent": "highest_pending_classes"})
            return {"reply": res["markdown"]}

        # 4. Specific student fee status or parent contact
        # Check patterns like "What is Rahul Sharma's fee status?", "fees of Rahul", "Rahul fee status"
        student_res = cls._check_student_specific_query(query, lower_q, conversation)
        if student_res:
            return student_res

        # 5. Overdue > 30 days / Overdue fees
        overdue_days_match = re.search(r'overdue\s+(?:by\s+)?(?:more\s+than\s+)?(\d+)\s*days?', lower_q)
        if overdue_days_match or "overdue fees" in lower_q or "overdue" in lower_q:
            days = int(overdue_days_match.group(1)) if overdue_days_match else 30
            cls_match = cls._extract_class_number(lower_q)
            res = natasha_tools.get_pending_fees_list(class_level=cls_match, overdue_days=days)
            cls._update_context(conversation, {
                "last_intent": "pending_fees",
                "student_ids": res.get("student_ids", []),
                "last_class": cls_match,
                "overdue_days": days
            })
            return {"reply": res["markdown"], "kpis": res.get("kpis")}

        # 6. Outstanding dues above ₹X (e.g. "dues above 5000", "pending above 5,000")
        above_match = re.search(r'(?:above|more than|greater than|over)\s*(?:rs\.?|₹)?\s*([\d,]+)', lower_q)
        if ("pending" in lower_q or "due" in lower_q or "fee" in lower_q) and above_match:
            min_amt = float(above_match.group(1).replace(',', ''))
            cls_match = cls._extract_class_number(lower_q)
            res = natasha_tools.get_pending_fees_list(class_level=cls_match, min_amount=min_amt)
            cls._update_context(conversation, {
                "last_intent": "pending_fees",
                "student_ids": res.get("student_ids", []),
                "min_amount": min_amt,
                "last_class": cls_match
            })
            return {"reply": res["markdown"], "kpis": res.get("kpis")}

        # 7. General Pending Fees / Who hasn't paid / Outstanding list
        if cls._is_pending_fee_query(lower_q):
            cls_match = cls._extract_class_number(lower_q)
            res = natasha_tools.get_pending_fees_list(class_level=cls_match)
            cls._update_context(conversation, {
                "last_intent": "pending_fees",
                "student_ids": res.get("student_ids", []),
                "last_class": cls_match,
                "total_pending_amount": res.get("total_pending_amount")
            })
            return {"reply": res["markdown"], "kpis": res.get("kpis")}

        # 8. Collected fees (e.g. "how much fee have we collected this month", "fee collection")
        if any(p in lower_q for p in ["collected this month", "fee collected", "collection this month", "total collection", "total fee collected"]):
            period = "last_month" if "last month" in lower_q else ("all_time" if "all time" in lower_q else "this_month")
            res = natasha_tools.get_fee_collection_stats(period=period)
            cls._update_context(conversation, {"last_intent": "fee_collection"})
            return {"reply": res["markdown"], "kpis": res.get("kpis")}

        # 9. Attendance Queries
        if "attendance" in lower_q or "absent" in lower_q or "roll call" in lower_q:
            res = natasha_tools.get_attendance_overview()
            cls._update_context(conversation, {"last_intent": "attendance"})
            return {"reply": res["markdown"], "kpis": res.get("kpis")}

        # 10. Batches / Classes overview
        if any(p in lower_q for p in ["batches", "batch schedule", "class schedule", "show batches", "active batches"]):
            cls_match = cls._extract_class_number(lower_q)
            res = natasha_tools.get_batches_and_classes_summary(class_level=cls_match)
            cls._update_context(conversation, {"last_intent": "batches"})
            return {"reply": res["markdown"]}

        # 11. Staff / Faculty overview
        if any(p in lower_q for p in ["staff", "teachers", "faculty", "salaries", "salary", "payroll"]):
            res = natasha_tools.get_staff_overview()
            cls._update_context(conversation, {"last_intent": "staff"})
            return {"reply": res["markdown"]}

        # 12. Inquiries / Leads
        if any(p in lower_q for p in ["inquir", "lead", "admission inquiry", "pending inquiry"]):
            res = natasha_tools.get_inquiries_overview()
            cls._update_context(conversation, {"last_intent": "inquiries"})
            return {"reply": res["markdown"]}

        # 13. General / Conversational fallback with Cloudflare Workers AI + ERP awareness
        return cls._call_llm_with_erp_context(query, conversation)

    # ==========================================================================
    # HELPER INTENT CHECKERS
    # ==========================================================================

    @classmethod
    def _is_student_count_query(cls, text: str) -> bool:
        phrases = [
            "how many active students",
            "active students",
            "total students",
            "enrolled students",
            "number of students",
            "student count",
            "strength of students",
            "how many students"
        ]
        return any(p in text for p in phrases) and not ("pending" in text or "fee" in text or "admitted" in text)

    @classmethod
    def _is_pending_fee_query(cls, text: str) -> bool:
        phrases = [
            "pending fee",
            "pending fees",
            "who hasn't paid",
            "who have not paid",
            "outstanding fee",
            "outstanding dues",
            "unpaid fee",
            "haven't paid their fees",
            "fees are pending",
            "dues list"
        ]
        return any(p in text for p in phrases)

    @classmethod
    def _extract_class_number(cls, text: str):
        m = re.search(r'\bclass\s*(\d+)\b', text)
        if m:
            return m.group(1)
        m2 = re.search(r'\bgrade\s*(\d+)\b', text)
        if m2:
            return m2.group(1)
        return None

    @classmethod
    def _extract_board(cls, text: str):
        if "cbse" in text:
            return "CBSE"
        if "icse" in text:
            return "ICSE"
        return None

    # ==========================================================================
    # MULTI-TURN FOLLOW-UP HANDLING
    # ==========================================================================

    @classmethod
    def _check_follow_up(cls, lower_q: str, context: dict, conversation) -> dict:
        """
        Handles conversational follow-ups like:
        - "Show their names."
        - "What is their total outstanding amount?"
        - "Show only students from Class 10."
        - "Show only Class 9."
        - "Give me their contact details."
        """
        last_intent = context.get("last_intent")
        student_ids = context.get("student_ids", [])

        # Follow-up: "Show only students from Class X" or "Filter to Class X"
        cls_filter = cls._extract_class_number(lower_q)
        if cls_filter and any(w in lower_q for w in ["show only", "only class", "filter to", "just class", "for class"]):
            if last_intent in ["pending_fees", "student_count"]:
                res = natasha_tools.get_pending_fees_list(class_level=cls_filter, student_ids=student_ids if student_ids else None)
                cls._update_context(conversation, {
                    "last_intent": "pending_fees",
                    "student_ids": res.get("student_ids", []),
                    "last_class": cls_filter,
                    "total_pending_amount": res.get("total_pending_amount")
                })
                return {
                    "reply": f"**Filtering to Class {cls_filter} students:**\n\n" + res["markdown"],
                    "kpis": res.get("kpis")
                }

        # Follow-up: "Show their names" / "Show the list" / "List them"
        if any(p in lower_q for p in ["show their names", "show names", "show the list", "list them", "who are they", "give me their names"]):
            if last_intent in ["pending_fees", "student_count"]:
                cls_val = context.get("last_class")
                res = natasha_tools.get_pending_fees_list(class_level=cls_val, student_ids=student_ids if student_ids else None)
                return {"reply": res["markdown"], "kpis": res.get("kpis")}

        # Follow-up: "What is their total outstanding amount?" / "Total amount?" / "Total due?"
        if any(p in lower_q for p in ["total outstanding amount", "total amount", "total due", "how much is the total", "combined outstanding"]):
            if last_intent == "pending_fees":
                amt = context.get("total_pending_amount")
                if amt is not None:
                    count = len(student_ids)
                    return {
                        "reply": (
                            f"### 💳 Total Outstanding Balance\n"
                            f"- **Combined Outstanding Amount:** **{natasha_tools.format_currency(amt)}**\n"
                            f"- **Students with Dues:** **{count}**\n"
                            f"- **Average Outstanding per Student:** **{natasha_tools.format_currency(amt / (count or 1))}**"
                        )
                    }

        # Follow-up: "Give me their contact details" / "Parent contacts"
        if any(p in lower_q for p in ["contact details", "phone numbers", "parent contacts", "contact numbers", "parent numbers"]):
            if student_ids:
                res = natasha_tools.get_pending_fees_list(student_ids=student_ids, limit=50)
                return {
                    "reply": (
                        "### 📞 Parent Contact Information for Outstanding Fees:\n\n"
                        "You can call parents directly or review their contact details below:\n\n"
                        + res["markdown"]
                    )
                }

        return None

    # ==========================================================================
    # STUDENT SPECIFIC QUERY RESOLVER
    # ==========================================================================

    @classmethod
    def _check_student_specific_query(cls, query: str, lower_q: str, conversation) -> dict:
        """
        Extracts student name from query like:
        - "What is Rahul Sharma's fee status?"
        - "What is the registered mobile number of ABC student's parent?"
        - "Fee status of Rahul"
        - "Parent contact of Anita"
        """
        wants_parent = any(w in lower_q for w in ["parent", "mobile", "phone", "contact", "guardian", "mother", "father"])
        wants_fees = any(w in lower_q for w in ["fee", "dues", "payment", "paid", "balance", "receipt", "status"])

        if not (wants_parent or wants_fees):
            # Might be just asking for student profile e.g. "Tell me about Rahul"
            if not any(w in lower_q for w in ["profile", "who is", "detail", "information", "info"]):
                return None

        # Clean search candidate
        candidate = re.sub(r"^(?:what is|what's|show|tell me|give me|find|get)\s+(?:the\s+)?", "", query, flags=re.IGNORECASE)
        candidate = re.sub(r"(?:registered\s+)?(?:mobile|phone|contact)\s*(?:number|details)?\s*(?:of\s+)?", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"(?:fee\s+status\s+of|fees\s+of|parent\s+of|contact\s+of)\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"'s\s+(?:parent|father|mother|guardian|fee\s+status|fees|phone|mobile|contact).*$", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"(?:'s\s+parent|'s\s+phone|'s\s+mobile|'s\s+contact|'s).*$", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\b(?:student's\s+parent|student\s+parent|student|parent|details|status|profile)\b", "", candidate, flags=re.IGNORECASE)
        candidate = candidate.replace('?', '').strip()

        # If too short or generic, skip
        if len(candidate) < 2 or candidate.lower() in ["all", "any", "the", "active", "enrolled", "today", "month"]:
            return None

        search_res = natasha_tools.find_students(candidate)
        if not search_res["success"] or search_res["count"] == 0:
            return None

        matches = search_res["matches"]

        # If exactly 1 match
        if len(matches) == 1:
            st = matches[0]
            cls._update_context(conversation, {
                "last_intent": "student_specific",
                "selected_student_id": st.id,
                "student_ids": [st.id]
            })

            if wants_parent and not wants_fees:
                res = natasha_tools.get_parent_contact_details(st)
                return {"reply": res["markdown"]}
            else:
                res = natasha_tools.get_student_fee_status(st)
                return {"reply": res["markdown"]}

        # If multiple matches -> Ask for clarification!
        clarification_md = [
            f"### 🔍 Clarification: Multiple Students Match '{candidate}'",
            f"I found **{len(matches)}** students matching your query. Please specify which student you would like to view:\n"
        ]
        for idx, m in enumerate(matches[:5], start=1):
            clarification_md.append(
                f"{idx}. **{m.user.get_full_name()}** &bull; Class {m.current_class} ({m.board}) &bull; ID: `{m.student_id}` &bull; Parent: {m.parent_name} (`{m.parent_phone}`)"
            )

        clarification_md.append("\n*Tip: You can reply with their Student ID (e.g. `STU202510014`) or their Class.*")

        cls._update_context(conversation, {
            "last_intent": "clarification_needed",
            "candidate_student_ids": [m.id for m in matches]
        })

        return {"reply": "\n".join(clarification_md)}

    # ==========================================================================
    # FALLBACK / LLM SENSITIVITY
    # ==========================================================================

    @classmethod
    def _call_llm_with_erp_context(cls, user_text: str, conversation) -> dict:
        """
        Invokes Cloudflare Workers AI with Natasha's persona and summary of the institute.
        """
        config = ChatbotConfig.get_settings()
        if not config.is_configured:
            return {
                "reply": (
                    f"Hello! I am **Natasha**, your personal assistant for Success Coaching institute.\n\n"
                    f"I can assist you with real-time operational data from our ERP:\n"
                    f"- **Student records & counts:** *'How many active students are enrolled?'*\n"
                    f"- **Fee registers & dues:** *'Show me all students whose fees are pending'* or *'Which classes have highest pending fees?'*\n"
                    f"- **Individual student inquiries:** *'What is Anita Golla's fee status?'*\n"
                    f"- **Parent communication:** *'What is the registered mobile number of Neel Kamdar's parent?'*\n"
                    f"- **Collections & Payroll:** *'How much fee have we collected this month?'*\n\n"
                    f"*(To also ask open-ended or curriculum questions, configure your Cloudflare API credentials in [Chatbot Settings](/chatbot/settings/)).*"
                )
            }

        # Build prompt
        system_persona = (
            "You are Natasha, the highly knowledgeable, polite, and efficient personal administrative assistant for Success Coaching. "
            "Address the user respectfully as the coaching institute administrator. If they ask about coaching operations, "
            "answer based on institute best practices, and remind them they can ask to view live pending fees, student enrollments, "
            "parent contact numbers, or batch timetables anytime."
        )

        history = [{"role": "user", "content": user_text}]
        ai_res = CloudflareAIService.query(history, config=config)

        if ai_res.get("success"):
            return {"reply": ai_res.get("reply", "")}
        else:
            return {
                "reply": (
                    "I am Natasha, your institute administrative assistant. "
                    "You can ask me to fetch pending fee registers, active student counts, parent contact information, "
                    "or monthly collection summaries directly from the database."
                )
            }

    @classmethod
    def _update_context(cls, conversation, new_data: dict):
        """Updates persistent conversation context."""
        try:
            curr = conversation.context_data or {}
            curr.update(new_data)
            conversation.context_data = curr
            conversation.save(update_fields=['context_data', 'updated_at'])
        except Exception as e:
            logger.error("Error updating conversation context: %s", e)
