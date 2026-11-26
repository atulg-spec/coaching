"""
Natasha Agentic Architecture.
A dynamic, LLM-driven ReAct (Reason + Act) personal assistant for the coaching institute
administrator. Understands arbitrary natural-language queries, executes multi-step read-only
Django ORM tool calls, maintains conversational context across follow-up turns, and synthesizes
grounded, accurate executive responses without predefined question dependencies.
"""

import json
import re
import logging
from django.utils import timezone

from . import dynamic_tools
from .models import ChatbotConfig
from .services import CloudflareAIService

logger = logging.getLogger(__name__)


class NatashaAgent:
    """
    Intelligent Agentic Personal Assistant for Coaching Institute Administrator.
    """

    MAX_TOOL_STEPS = 4

    @classmethod
    def _build_agent_system_prompt(cls) -> str:
        """Builds the dynamic system prompt with today's date and live tool schemas."""
        today = timezone.now().date()
        tools_json = json.dumps(dynamic_tools.TOOL_DEFINITIONS, indent=2)
        return (
            f"You are Natasha, the intelligent personal AI executive assistant for the administrator at Success Coaching.\n"
            f"Today's date is {today.isoformat()} (Month: {today.month}, Year: {today.year}).\n\n"
            "CORE PRINCIPLES:\n"
            "1. You have full understanding of the institute's Coaching ERP: Students, Parents, Fee Payments, Attendance, "
            "Academic Batches, Staff/Payroll, and Admissions Inquiries.\n"
            "2. NEVER invent, guess, or fabricate any student names, phone numbers, counts, or financial figures. "
            "Always call the appropriate database tool(s) first to retrieve real records.\n"
            "3. Understand ANY natural language phrasing (English, Hindi, Hinglish, or informal) and any unseen/novel "
            "question. You may call multiple tools in sequence (e.g., to compare two time periods or combine modules).\n"
            "4. HONESTY ABOUT UNAVAILABLE DATA: The current ERP database does NOT store exam records, test scores, "
            "report cards, library, hostel, or transport data. If asked for something not in the ERP, state clearly "
            "that those records are unavailable in the platform.\n"
            "5. AMBIGUITY & DISAMBIGUATION: If searching for a specific student by name returns multiple matching students, "
            "ask the administrator to clarify which student they mean (listing their name, class, ID, and parent).\n"
            "6. CONTEXTUAL FOLLOW-UPS: Use the conversation history and working memory (e.g. previous student_ids, "
            "last_class) to resolve 'them', 'their parents', 'those students', 'only class X', etc.\n"
            "7. PRESENTATION: In your final answer, format data cleanly with Markdown headings, bullet summaries, "
            "Markdown tables (include `[Profile](/dashboard/students/<id>/)` links when student IDs are present), "
            "and INR currency formatting (`₹X,XXX`). Distinguish between zero values and missing data.\n\n"
            f"AVAILABLE READ-ONLY ERP TOOLS:\n{tools_json}\n\n"
            "RESPONSE FORMAT (STRICT JSON ONLY):\n"
            "To call a database tool, output:\n"
            "{\"action\": \"call_tool\", \"tool\": \"<tool_name>\", \"parameters\": {<param>: <value>}}\n\n"
            "When you have enough real data (or for greetings / unavailable-module explanations), output:\n"
            "{\"action\": \"final_answer\", \"reply\": \"<markdown executive response>\", "
            "\"kpis\": [{\"label\": \"<short label>\", \"value\": \"<formatted value>\", \"color\": \"emerald|blue|amber|rose\"}]}\n\n"
            "Output valid JSON only. Do not wrap JSON in commentary."
        )

    @classmethod
    def process_query(cls, user_text: str, conversation, user=None) -> dict:
        """
        Orchestrates Natasha's end-to-end agent workflow.
        Uses the LLM ReAct loop when Cloudflare AI is configured; falls back cleanly if offline/unconfigured.
        """
        query = user_text.strip()
        context = dict(conversation.context_data or {})
        config = ChatbotConfig.get_settings()

        # Primary Path: Genuine LLM-Driven Multi-Step ReAct Agent
        if config.is_configured:
            agent_res = cls._run_llm_agent_loop(query, conversation, context, config)
            if agent_res is not None:
                return agent_res

        # Fallback Path (when Cloudflare credentials are not configured or API fails)
        return cls._run_offline_fallback(query, conversation, context, config)

    # ==========================================================================
    # PRIMARY PATH: LLM-DRIVEN MULTI-STEP REACT LOOP
    # ==========================================================================

    @classmethod
    def _run_llm_agent_loop(cls, query: str, conversation, context: dict, config: ChatbotConfig) -> dict:
        """
        Executes a multi-step Reason + Act loop where the LLM dynamically plans tool calls,
        observes real Django ORM results, decides whether more queries are needed, and
        synthesizes the final grounded response.
        """
        system_prompt = cls._build_agent_system_prompt()
        history_msgs = cls._load_recent_history(conversation, exclude_latest_user=True)

        context_note = cls._format_working_memory(context)
        user_payload = f"{context_note}\nAdministrator Question: {query}" if context_note else query

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history_msgs)
        messages.append({"role": "user", "content": user_payload})

        last_tool_name = None
        last_parameters = {}
        latest_student_ids = []
        latest_pending_sum = None
        observations = []

        for step in range(cls.MAX_TOOL_STEPS):
            ai_res = CloudflareAIService.query(
                messages,
                config=config,
                include_config_system_prompt=False,
                temperature=0.0,
                max_tokens=max(config.max_tokens or 1024, 1536),
            )
            if not ai_res.get("success"):
                logger.warning("LLM agent step %d failed: %s", step + 1, ai_res.get("error"))
                return None

            raw_reply = str(ai_res.get("reply", "")).strip()
            parsed = cls._parse_agent_json(ai_res.get("reply", ""))
            if not parsed:
                # If we already gathered tool observations, NEVER discard them!
                if observations:
                    if raw_reply and not raw_reply.startswith("{"):
                        cls._persist_agent_context(
                            conversation, context, last_tool_name, last_parameters,
                            latest_student_ids, latest_pending_sum
                        )
                        return {"reply": raw_reply, "kpis": []}
                    last_obs = observations[-1]
                    cls._persist_agent_context(
                        conversation, context, last_tool_name, last_parameters,
                        latest_student_ids, latest_pending_sum
                    )
                    return cls._synthesize_fallback_response(last_obs["tool"], last_obs["parameters"], last_obs["result"])
                # At step 0, if the model echoed Markdown instead of calling a tool, nudge it once
                if step == 0 and raw_reply:
                    messages.append({"role": "assistant", "content": raw_reply[:400]})
                    messages.append({
                        "role": "user",
                        "content": (
                            "Remember: output valid JSON only. To query the database, output "
                            "{\"action\": \"call_tool\", \"tool\": \"<tool_name>\", \"parameters\": {...}}. "
                            "Do not output Markdown directly without calling a tool first."
                        )
                    })
                    continue
                logger.warning("Could not parse JSON from LLM agent at step %d: %s", step + 1, raw_reply[:200])
                return None

            # Check if LLM is ready with the final answer
            if parsed.get("action") == "final_answer" or "final_answer" in parsed or "reply" in parsed or "direct_response" in parsed:
                reply_text = parsed.get("reply") or parsed.get("final_answer") or parsed.get("direct_response") or ""
                kpis = parsed.get("kpis") if isinstance(parsed.get("kpis"), list) else []
                cls._persist_agent_context(
                    conversation, context, last_tool_name, last_parameters,
                    latest_student_ids, latest_pending_sum
                )
                return {"reply": reply_text, "kpis": kpis}

            # Otherwise, execute requested tool
            tool_name = parsed.get("tool")
            parameters = parsed.get("parameters") or {}
            if not tool_name or tool_name not in dynamic_tools.TOOL_REGISTRY:
                logger.warning("LLM requested invalid tool '%s'", tool_name)
                return None

            tool_result = dynamic_tools.execute_tool(tool_name, parameters)
            last_tool_name = tool_name
            last_parameters = parameters

            # Disambiguation guard for single-student name lookups
            disambiguation = cls._check_student_disambiguation(query, tool_result, tool_name, parameters)
            if disambiguation:
                cls._update_context(conversation, {
                    "last_intent": "clarification_needed",
                    "candidate_student_ids": disambiguation["candidate_ids"]
                })
                return {"reply": disambiguation["markdown"], "kpis": []}

            if isinstance(tool_result, dict):
                if tool_result.get("student_ids"):
                    latest_student_ids = tool_result["student_ids"]
                if tool_result.get("total_balance_sum") is not None:
                    latest_pending_sum = tool_result["total_balance_sum"]
                elif tool_result.get("total_pending_due_sum") is not None:
                    latest_pending_sum = tool_result["total_pending_due_sum"]

            observations.append({"tool": tool_name, "parameters": parameters, "result": tool_result})

            # Feed observation back to the LLM for next reasoning step
            messages.append({"role": "assistant", "content": json.dumps({"action": "call_tool", "tool": tool_name, "parameters": parameters})})
            obs_str = json.dumps(tool_result, default=str)
            if len(obs_str) > 12000:
                obs_str = obs_str[:12000] + "... (truncated)"
            messages.append({
                "role": "user",
                "content": (
                    f"TOOL OBSERVATION ({tool_name}):\n{obs_str}\n\n"
                    "Now either call another tool with JSON "
                    "{\"action\": \"call_tool\", \"tool\": \"...\", \"parameters\": {...}}, "
                    "or write your final answer directly in clean Markdown (or JSON "
                    "{\"action\": \"final_answer\", \"reply\": \"...\", \"kpis\": [...]})."
                )
            })

        # Max tool steps reached — ask LLM for final synthesis from collected observations
        messages.append({
            "role": "user",
            "content": (
                "You have gathered all necessary database observations. "
                "Write your final executive answer now in clean Markdown based solely on those observations."
            )
        })
        final_res = CloudflareAIService.query(
            messages,
            config=config,
            include_config_system_prompt=False,
            temperature=0.2,
            max_tokens=max(config.max_tokens or 1024, 1536),
        )
        if final_res.get("success"):
            parsed = cls._parse_agent_json(final_res.get("reply", ""))
            if parsed and (parsed.get("reply") or parsed.get("final_answer")):
                cls._persist_agent_context(
                    conversation, context, last_tool_name, last_parameters,
                    latest_student_ids, latest_pending_sum
                )
                return {
                    "reply": parsed.get("reply") or parsed.get("final_answer"),
                    "kpis": parsed.get("kpis") if isinstance(parsed.get("kpis"), list) else [],
                }
            raw_final = str(final_res.get("reply", "")).strip()
            if raw_final and not raw_final.startswith("{"):
                cls._persist_agent_context(
                    conversation, context, last_tool_name, last_parameters,
                    latest_student_ids, latest_pending_sum
                )
                return {"reply": raw_final, "kpis": []}

        # If synthesis failed after running tools, use deterministic presenter on the last observation
        if observations:
            last_obs = observations[-1]
            cls._persist_agent_context(
                conversation, context, last_tool_name, last_parameters,
                latest_student_ids, latest_pending_sum
            )
            return cls._synthesize_fallback_response(last_obs["tool"], last_obs["parameters"], last_obs["result"])

        return None

    @staticmethod
    def _load_recent_history(conversation, exclude_latest_user: bool = True) -> list:
        """Loads recent ChatMessage turns for multi-turn conversational awareness."""
        try:
            qs = conversation.messages.order_by('-created_at')[:9]
            ordered = list(reversed(qs))
            if exclude_latest_user and ordered and ordered[-1].role == 'user':
                ordered = ordered[:-1]
            return [
                {"role": m.role, "content": m.content[:1500]}
                for m in ordered[-8:]
                if m.role in ('user', 'assistant') and m.content
            ]
        except Exception:
            return []

    @staticmethod
    def _format_working_memory(context: dict) -> str:
        """Formats structured working memory from previous turns for the LLM."""
        parts = []
        if context.get("student_ids"):
            parts.append(f"student_ids={context['student_ids'][:30]}")
        if context.get("last_class"):
            parts.append(f"last_class={context['last_class']}")
        if context.get("last_tool"):
            parts.append(f"last_tool={context['last_tool']}")
        if context.get("candidate_student_ids"):
            parts.append(f"clarification_candidate_student_ids={context['candidate_student_ids']}")
        if not parts:
            return ""
        return "[Conversation Working Memory: " + ", ".join(parts) + "]"

    @staticmethod
    def _parse_agent_json(reply) -> dict:
        """
        Safely parses JSON action objects from LLM output (dict, list, or text with JSON).
        Handles literal newlines inside JSON strings (strict=False) and truncated final_answer replies.
        """
        if isinstance(reply, dict):
            return reply
        if isinstance(reply, list):
            return reply[0] if reply and isinstance(reply[0], dict) else None
        text = str(reply or "").strip()
        if not text:
            return None
        # Strip markdown code fences if present
        fenced = re.search(r'```(?:json)?\s*(\{[\s\S]*\})\s*```', text)
        if fenced:
            text = fenced.group(1)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            candidate = json_match.group(0)
            try:
                parsed = json.loads(candidate, strict=False)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        # Fallback: extract truncated or unescaped final_answer reply reliably
        if '"final_answer"' in text and '"reply"' in text:
            after_reply = text.split('"reply"', 1)[1]
            after_colon = re.sub(r'^\s*:\s*"', '', after_reply)
            cleaned = re.sub(r'"\s*(?:,\s*"kpis"\s*:[\s\S]*)?\}?\s*$', '', after_colon)
            extracted = cleaned.replace('\\n', '\n').replace('\\"', '"').strip()
            if extracted:
                return {"action": "final_answer", "reply": extracted, "kpis": []}

        return None

    @classmethod
    def _persist_agent_context(
        cls, conversation, context: dict, tool_name: str, parameters: dict,
        student_ids: list, pending_sum
    ):
        """Persists updated conversational working memory."""
        cls._update_context(conversation, {
            "last_tool": tool_name or context.get("last_tool"),
            "last_parameters": parameters or context.get("last_parameters"),
            "student_ids": student_ids or context.get("student_ids", []),
            "last_class": (parameters or {}).get("current_class") or context.get("last_class"),
            "total_pending_amount": pending_sum if pending_sum is not None else context.get("total_pending_amount"),
            "candidate_student_ids": [],
        })

    # ==========================================================================
    # OFFLINE / UNCONFIGURED FALLBACK PATH
    # ==========================================================================

    @classmethod
    def _run_offline_fallback(cls, query: str, conversation, context: dict, config: ChatbotConfig) -> dict:
        """
        Deterministic fallback when Cloudflare AI credentials are not configured or offline.
        """
        lower_q = query.lower()
        plan = cls._resolve_contextual_references(lower_q, context) or cls._semantic_planner_fallback(lower_q, query, context)

        if "direct_response" in plan and not plan.get("tool"):
            return {"reply": plan["direct_response"], "kpis": []}

        tool_name = plan.get("tool")
        parameters = plan.get("parameters", {})
        tool_result = dynamic_tools.execute_tool(tool_name, parameters)

        disambiguation = cls._check_student_disambiguation(query, tool_result, tool_name, parameters)
        if disambiguation:
            cls._update_context(conversation, {
                "last_intent": "clarification_needed",
                "candidate_student_ids": disambiguation["candidate_ids"]
            })
            return {"reply": disambiguation["markdown"], "kpis": []}

        synthesis = cls._synthesize_fallback_response(tool_name, parameters, tool_result)

        new_student_ids = tool_result.get("student_ids") or context.get("student_ids", [])
        pending_sum = tool_result.get("total_balance_sum") or tool_result.get("total_due_sum")
        cls._persist_agent_context(conversation, context, tool_name, parameters, new_student_ids, pending_sum)

        return synthesis

    @classmethod
    def _resolve_contextual_references(cls, lower_q: str, context: dict) -> dict:
        """Resolves anaphoric references in offline fallback mode."""
        student_ids = context.get("student_ids", [])

        cls_match = re.search(r'(?:only|just|for|filter\s+to)\s+class\s*(\d+)', lower_q)
        if cls_match:
            target_cls = cls_match.group(1)
            if student_ids:
                return {
                    "tool": "query_students",
                    "parameters": {"current_class": target_cls, "student_ids": student_ids}
                }
            return {
                "tool": "query_payments",
                "parameters": {"current_class": target_cls, "status": "pending", "aggregate_by": "student"}
            }

        if any(w in lower_q for w in ["their parents", "parent mobile", "parents' mobile", "contact details", "parents number", "phone numbers"]):
            if student_ids:
                return {
                    "tool": "query_students",
                    "parameters": {"student_ids": student_ids, "limit": 50}
                }

        if any(w in lower_q for w in ["show their names", "show names", "show the list", "list them", "who are they", "give me their names"]):
            if student_ids:
                return {
                    "tool": "query_students",
                    "parameters": {"student_ids": student_ids, "limit": 50}
                }
            return {
                "tool": "query_payments",
                "parameters": {"status": "pending", "aggregate_by": "student"}
            }

        if any(w in lower_q for w in ["total outstanding amount", "how much money can we collect", "total due", "total amount", "combined outstanding"]):
            if student_ids:
                return {
                    "tool": "query_payments",
                    "parameters": {"status": "pending", "student_ids": student_ids, "aggregate_by": "student"}
                }

        return None

    @classmethod
    def _semantic_planner_fallback(cls, lower_q: str, raw_query: str, context: dict) -> dict:
        """
        Semantic fallback planner used only when Cloudflare AI is offline or unconfigured.
        """
        if "same registered mobile" in lower_q or "same mobile" in lower_q or "same parent phone" in lower_q:
            return {"tool": "query_students", "parameters": {"parent_phone_duplicate": True}}

        if "ratio" in lower_q or "student-to-faculty" in lower_q or "highest student" in lower_q:
            return {"tool": "query_batches", "parameters": {"compute_ratio": True}}

        if ("low attendance" in lower_q or "attendance" in lower_q) and ("pending" in lower_q or "fee" in lower_q or "due" in lower_q):
            return {"tool": "query_students", "parameters": {"attendance_below": 75.0, "has_pending_fees": True}}

        days_match = re.search(r'admitted\s+in\s+(?:the\s+last\s+)?(\d+)\s+days', lower_q)
        if days_match and ("fee" in lower_q or "paid" in lower_q or "payment" in lower_q or "due" in lower_q):
            return {"tool": "query_students", "parameters": {"admission_days_ago": int(days_match.group(1)), "has_pending_fees": True}}

        overdue_match = re.search(r'overdue\s+(?:by\s+)?(?:more\s+than\s+)?(\d+)\s+days', lower_q)
        if overdue_match:
            return {"tool": "query_payments", "parameters": {"overdue_days": int(overdue_match.group(1))}}

        above_match = re.search(r'(?:above|more than|greater than|over)\s*(?:rs\.?|₹)?\s*([\d,]+)', lower_q)
        if above_match and ("pending" in lower_q or "due" in lower_q or "fee" in lower_q):
            val = float(above_match.group(1).replace(',', ''))
            return {"tool": "query_payments", "parameters": {"min_balance": val, "status": "pending", "aggregate_by": "student"}}

        months_ago_match = re.search(r'last\s+(\d+)\s+months', lower_q)
        if months_ago_match and ("collected" in lower_q or "fee" in lower_q or "payment" in lower_q):
            cls_match = re.search(r'class\s*(\d+)', lower_q)
            return {
                "tool": "query_payments",
                "parameters": {
                    "status": "collected",
                    "months_ago": int(months_ago_match.group(1)),
                    "current_class": cls_match.group(1) if cls_match else None
                }
            }

        if ("highest pending" in lower_q or "highest dues" in lower_q or "highest outstanding" in lower_q
                or ("which class" in lower_q and any(w in lower_q for w in ["fee", "outstanding", "dues", "pending"]))
                or ("class" in lower_q and "highest" in lower_q)):
            return {"tool": "query_payments", "parameters": {"status": "pending", "aggregate_by": "class"}}

        if any(w in lower_q for w in ["collected this month", "fee collected", "collection this month", "total collection"]):
            return {"tool": "query_payments", "parameters": {"status": "collected", "months_ago": 1}}

        if any(w in lower_q for w in [
            "pending fee", "pending fees", "who hasn't paid", "who haven't paid",
            "haven't paid", "have not paid", "not paid their", "not paid the",
            "not completed their fee", "fee not paid", "not cleared their fee",
            "outstanding fee", "outstanding dues", "unpaid fee", "fee pending",
            "students who haven", "tell me about students who"
        ]):
            cls_match = re.search(r'class\s*(\d+)', lower_q)
            return {
                "tool": "query_payments",
                "parameters": {
                    "status": "pending",
                    "aggregate_by": "student",
                    "current_class": cls_match.group(1) if cls_match else None
                }
            }

        if any(w in lower_q for w in ["fee status", "fees of", "parent of", "mobile number of", "parent phone", "contact of", "details of"]):
            candidate = re.sub(r"^(?:what is|what's|show|tell me|give me|find|get)\s+(?:the\s+)?", "", raw_query, flags=re.IGNORECASE)
            candidate = re.sub(r"(?:registered\s+)?(?:mobile|phone|contact)\s*(?:number|details)?\s*(?:of\s+)?", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"(?:fee\s+status\s+of|fees\s+of|parent\s+of|contact\s+of)\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"'s\s+(?:parent|father|mother|guardian|fee\s+status|fees|phone|mobile|contact).*$", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"(?:student's\s+parent|student\s+parent|student|parent|details|status|profile)\b", "", candidate, flags=re.IGNORECASE).strip(' ?')
            if len(candidate) > 2:
                if any(w in lower_q for w in ["fee", "dues", "payment", "paid"]):
                    return {"tool": "query_payments", "parameters": {"student_name": candidate}}
                return {"tool": "query_students", "parameters": {"search": candidate}}

        if any(w in lower_q for w in ["kitne bachche", "how many students", "active students", "current student strength", "enrollment count", "enrolled students"]):
            cls_match = re.search(r'class\s*(\d+)', lower_q)
            board_val = "CBSE" if "cbse" in lower_q else ("ICSE" if "icse" in lower_q else None)
            return {
                "tool": "query_students",
                "parameters": {"is_active": True, "current_class": cls_match.group(1) if cls_match else None, "board": board_val}
            }

        if any(w in lower_q for w in ["attendance", "roll call", "absent", "absentees"]):
            return {"tool": "query_attendance", "parameters": {"date_val": None}}

        if any(w in lower_q for w in ["batches", "batch schedule", "class schedule"]):
            return {"tool": "query_batches", "parameters": {}}

        if any(w in lower_q for w in ["staff", "faculty", "teachers", "salaries", "payroll"]):
            return {"tool": "query_staff", "parameters": {}}

        if any(w in lower_q for w in ["overview", "summary", "dashboard", "health check"]):
            return {"tool": "get_institute_overview", "parameters": {}}

        clean_search = re.sub(
            r"^(?:tell me about|who is|show me|find|search|lookup|get details of|about|info on)\s+",
            "", raw_query, flags=re.IGNORECASE
        ).strip(" ?.")
        return {"tool": "query_students", "parameters": {"search": clean_search or raw_query}}

    # ==========================================================================
    # DISAMBIGUATION CHECK
    # ==========================================================================

    @classmethod
    def _check_student_disambiguation(cls, query: str, tool_result: dict, tool_name: str = None, parameters: dict = None) -> dict:
        """
        If searching for a specific student by name yields multiple matches, ask for clarification.
        Only triggers for name-based lookups (search= or student_name=), never for bulk/list queries.
        """
        params = parameters or {}

        is_name_lookup = bool(params.get("search")) and not any(
            p in params for p in ["is_active", "has_pending_fees", "parent_phone_duplicate",
                                  "attendance_below", "admission_days_ago", "current_class",
                                  "student_ids", "admission_month", "admission_date_from"]
        )
        if tool_name == "query_students" and is_name_lookup:
            students = tool_result.get("students", [])
            if len(students) > 1:
                return cls._build_disambiguation_response(students)

        if tool_name == "query_payments" and params.get("student_name"):
            name_param = str(params["student_name"]).strip()
            student_check = dynamic_tools.query_students(search=name_param, limit=10)
            matched_students = student_check.get("students", [])
            if len(matched_students) > 1:
                return cls._build_disambiguation_response(matched_students)

        return None

    @classmethod
    def _build_disambiguation_response(cls, students: list) -> dict:
        """Build a clarification message when multiple students match."""
        md = [
            "### 🔍 Clarification Needed",
            f"I found **{len(students)}** students matching your request. Which student would you like to review?\n"
        ]
        for idx, s in enumerate(students[:6], start=1):
            md.append(f"{idx}. **{s['name']}** &bull; Class {s['current_class']} ({s['board']}) &bull; ID: `{s['student_id']}` &bull; Parent: {s['parent_name']} (`{s['parent_phone']}`)")
        md.append("\n*Please reply with their Student ID or Class to proceed.*")
        return {
            "markdown": "\n".join(md),
            "candidate_ids": [s["id"] for s in students]
        }

    # ==========================================================================
    # DETERMINISTIC FALLBACK PRESENTERS
    # ==========================================================================

    @classmethod
    def _synthesize_fallback_response(cls, tool_name: str, parameters: dict, tool_result: dict) -> dict:
        """Formats tool result data into a structured executive presentation when offline."""
        if tool_name == "query_students":
            return cls._present_students(tool_result, parameters)
        if tool_name == "query_payments":
            return cls._present_payments(tool_result, parameters)
        if tool_name == "query_attendance":
            return cls._present_attendance(tool_result, parameters)
        if tool_name == "query_batches":
            return cls._present_batches(tool_result, parameters)
        if tool_name == "query_staff":
            return cls._present_staff(tool_result, parameters)
        if tool_name == "query_inquiries":
            return cls._present_inquiries(tool_result, parameters)
        if tool_name == "get_institute_overview":
            return cls._present_overview(tool_result)
        return {"reply": str(tool_result), "kpis": []}

    @classmethod
    def _present_students(cls, data: dict, params: dict) -> dict:
        total = data.get("total_matched", 0)
        students = data.get("students", [])

        if params.get("parent_phone_duplicate"):
            if total == 0:
                return {
                    "reply": (
                        "### 📞 Parent Contact Analysis\n"
                        "I scanned all registered student profiles in the database. Currently, **no two students share the same parent mobile number** "
                        "(all enrolled students have unique registered parent contacts)."
                    ),
                    "kpis": [{"label": "Shared Parent Contacts", "value": "0", "color": "blue"}]
                }

        if params.get("attendance_below") and params.get("has_pending_fees"):
            md = [
                "### ⚠️ Students with Both Low Attendance & Outstanding Fees",
                f"Found **{total}** student(s) with attendance below 75% who also have pending fee dues.\n"
            ]
            if total == 0:
                md.append("✅ **No students currently have both low attendance and pending fees.**")
            else:
                md.append("| Student Name | Class | Parent Name | Parent Mobile | Outstanding Due | Profile |")
                md.append("| :--- | :--- | :--- | :--- | :---: | :--- |")
                for s in students[:25]:
                    md.append(f"| **{s['name']}** (`{s['student_id']}`) | Class {s['current_class']} | {s['parent_name']} | `{s['parent_phone']}` | {dynamic_tools.format_inr(s['pending_due'])} | [View Profile]({s['profile_url']}) |")
            return {"reply": "\n".join(md), "kpis": [{"label": "At-Risk Students", "value": str(total), "color": "rose"}]}

        if len(students) == 1 and params.get("search"):
            s = students[0]
            md = [
                f"### 👤 Student Profile: {s['name']} (`{s['student_id']}`)",
                f"- **Class & Board:** Class {s['current_class']} ({s['board']}) | **School:** {s['school_name'] or 'N/A'}",
                f"- **Parent / Guardian:** **{s['parent_name']}** | **Mobile:** `[{s['parent_phone']}](tel:{s['parent_phone']})`",
                f"- **Parent Email:** {s['parent_email'] or 'Not provided'}",
                f"- **Residential Address:** {s['address'] or 'Not provided'}",
                f"- **Admission Date:** {s['admission_date']} | **Status:** {'Active' if s['is_active'] else 'Inactive'}",
                f"- **Pending Dues:** **{dynamic_tools.format_inr(s['pending_due'])}**",
                f"- [Open Full Profile]({s['profile_url']}) &bull; [Fee Collection](/dashboard/payments/collect/)"
            ]
            return {"reply": "\n".join(md), "kpis": [{"label": "Pending Dues", "value": dynamic_tools.format_inr(s['pending_due']), "color": "amber"}]}

        cls_txt = f" in Class {params['current_class']}" if params.get('current_class') else ""
        board_txt = f" ({params['board']})" if params.get('board') else ""

        kpis = [
            {"label": "Total Matched", "value": str(total), "color": "emerald"},
            {"label": "Showing", "value": str(len(students)), "color": "blue"}
        ]

        md = [
            f"### 🎓 Student Enrollment Records{cls_txt}{board_txt}",
            f"- **Total Students Found:** **{total}**",
            ""
        ]

        if total > 0:
            md.append("| Student Name | Student ID | Class & Board | Parent Name | Parent Mobile | Dues | Action |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :---: | :--- |")
            for s in students[:30]:
                due_badge = dynamic_tools.format_inr(s['pending_due']) if s['pending_due'] > 0 else "✅ Paid"
                md.append(f"| **{s['name']}** | `{s['student_id']}` | Class {s['current_class']} {s['board']} | {s['parent_name']} | `{s['parent_phone']}` | {due_badge} | [Profile]({s['profile_url']}) |")
            if total > 30:
                md.append(f"\n*Showing 30 of {total} records.*")
        else:
            md.append("No student records found matching the specified parameters.")

        return {"reply": "\n".join(md), "kpis": kpis}

    @classmethod
    def _present_payments(cls, data: dict, params: dict) -> dict:
        agg = data.get("aggregation")

        if agg == "class":
            results = data.get("results", [])
            total_bal = data.get("total_balance_sum", 0.0)
            md = [
                "### 📊 Pending Fees Grouped by Class",
                f"- **Total Outstanding Dues:** **{dynamic_tools.format_inr(total_bal)}**",
                "",
                "| Class | Outstanding Due | Students Affected | Total Billed | Total Paid |",
                "| :--- | :---: | :---: | :---: | :---: |"
            ]
            for r in results:
                md.append(
                    f"| Class {r['student__current_class']} | **{dynamic_tools.format_inr(r['total_balance'])}** | "
                    f"{r['student_count']} | {dynamic_tools.format_inr(r['total_due'])} | {dynamic_tools.format_inr(r['total_paid'])} |"
                )
            return {
                "reply": "\n".join(md),
                "kpis": [{"label": "Combined Dues", "value": dynamic_tools.format_inr(total_bal), "color": "rose"}]
            }

        if agg == "student":
            students = data.get("students", [])
            count = data.get("student_count", len(students))
            total_bal = data.get("total_balance_sum", 0.0)

            title_suffix = ""
            if params.get("min_balance"):
                title_suffix += f" (Above {dynamic_tools.format_inr(params['min_balance'])})"
            if params.get("current_class"):
                title_suffix += f" for Class {params['current_class']}"

            kpis = [
                {"label": "Total Dues", "value": dynamic_tools.format_inr(total_bal), "color": "rose"},
                {"label": "Students with Dues", "value": str(count), "color": "amber"},
                {"label": "Average Due / Student", "value": dynamic_tools.format_inr(total_bal / (count or 1)), "color": "blue"}
            ]

            md = [
                f"### 💳 Outstanding Fees Report{title_suffix}",
                f"- **Total Outstanding Amount:** **{dynamic_tools.format_inr(total_bal)}** across **{count}** student(s)",
                ""
            ]

            if count == 0:
                md.append("✅ **No pending dues found matching your criteria.**")
            else:
                md.append("| Student Name | Class | Parent Name | Parent Mobile | Outstanding Due | Action |")
                md.append("| :--- | :--- | :--- | :--- | :---: | :--- |")
                for s in students[:35]:
                    name = f"{s['student__user__first_name']} {s['student__user__last_name']}".strip()
                    sid = s['student__id']
                    profile_url = f"/dashboard/students/{sid}/"
                    md.append(
                        f"| **{name}** (`{s['student__student_id']}`) | Class {s['student__current_class']} {s['student__board']} | "
                        f"{s['student__parent_name']} | `{s['student__parent_phone']}` | **{dynamic_tools.format_inr(s['total_balance'])}** | [Profile]({profile_url}) |"
                    )

            return {"reply": "\n".join(md), "kpis": kpis}

        records = data.get("records", [])
        total_bal = data.get("total_balance_sum", 0.0)
        total_paid = data.get("total_paid_sum", 0.0)

        if params.get("student_name") and records:
            first = records[0]
            st_name = first["student_name"]
            md = [
                f"### 📋 Fee Register: {st_name} (`{first['student_code']}`)",
                f"- **Class:** Class {first['current_class']}",
                f"- **Parent Name:** {first['parent_name']} | **Mobile:** `{first['parent_phone']}`",
                f"- **Total Fees Billed:** {dynamic_tools.format_inr(data.get('total_due_sum'))} | **Total Paid:** {dynamic_tools.format_inr(total_paid)} | **Balance Due:** **{dynamic_tools.format_inr(total_bal)}**",
                "",
                "| Month | Batch | Billed | Paid | Due | Status | Mode / Receipt |",
                "| :--- | :--- | :---: | :---: | :---: | :---: | :--- |"
            ]
            for r in records[:25]:
                md.append(
                    f"| {r['month']} | {r['batch_name']} | {dynamic_tools.format_inr(r['amount_due'])} | "
                    f"{dynamic_tools.format_inr(r['amount_paid'])} | **{dynamic_tools.format_inr(r['balance'])}** | {r['status'].title()} | {r['payment_mode'] or '-'} {r['receipt_number']} |"
                )
            return {
                "reply": "\n".join(md),
                "kpis": [
                    {"label": "Total Paid", "value": dynamic_tools.format_inr(total_paid), "color": "emerald"},
                    {"label": "Pending Balance", "value": dynamic_tools.format_inr(total_bal), "color": "rose"}
                ]
            }

        md = [
            "### 💰 Fee Transactions & Collections",
            f"- **Records Found:** **{data.get('total_records', 0)}** | **Total Paid:** **{dynamic_tools.format_inr(total_paid)}** | **Total Balance:** **{dynamic_tools.format_inr(total_bal)}**",
            ""
        ]
        if records:
            md.append("| Student | Class | Month | Billed | Paid | Balance | Status |")
            md.append("| :--- | :--- | :--- | :---: | :---: | :---: | :---: |")
            for r in records[:25]:
                md.append(
                    f"| **{r['student_name']}** | Class {r['current_class']} | {r['month']} | "
                    f"{dynamic_tools.format_inr(r['amount_due'])} | {dynamic_tools.format_inr(r['amount_paid'])} | "
                    f"{dynamic_tools.format_inr(r['balance'])} | {r['status'].title()} |"
                )

        return {
            "reply": "\n".join(md),
            "kpis": [
                {"label": "Total Collected", "value": dynamic_tools.format_inr(total_paid), "color": "emerald"},
                {"label": "Total Balance", "value": dynamic_tools.format_inr(total_bal), "color": "amber"}
            ]
        }

    @classmethod
    def _present_attendance(cls, data: dict, params: dict) -> dict:
        total = data.get("total_records", 0)
        present = data.get("present_count", 0)
        absent = data.get("absent_count", 0)
        rate = data.get("attendance_rate", 0)
        items = data.get("items", [])

        md = [
            f"### 📅 Attendance Report ({data.get('date_queried')})",
            f"- **Total Marked:** **{total}** | **Present:** **{present}** | **Absent:** **{absent}** | **Rate:** **{rate}%**",
            ""
        ]

        if total == 0:
            latest = data.get("latest_session_date")
            md.append(f"ℹ️ **No attendance sessions marked for {data.get('date_queried')}.**")
            if latest:
                md.append(f"*The most recent attendance roll call in the system was on **{latest}**.*")
        elif items:
            md.append("| Student | Class | Batch | Status | Parent Contact |")
            md.append("| :--- | :--- | :--- | :---: | :--- |")
            for i in items[:30]:
                md.append(f"| **{i['student_name']}** | Class {i['current_class']} | {i['batch_name']} | {i['status'].title()} | `{i['parent_phone']}` |")

        return {
            "reply": "\n".join(md),
            "kpis": [
                {"label": "Attendance Rate", "value": f"{rate}%", "color": "emerald"},
                {"label": "Absent Today", "value": str(absent), "color": "rose"}
            ]
        }

    @classmethod
    def _present_batches(cls, data: dict, params: dict) -> dict:
        batches = data.get("batches", [])
        md = [
            "### 🏫 Academic Batches & Student-to-Faculty Ratios",
            f"- **Total Active Batches:** **{data.get('total_batches', 0)}**",
            "",
            "| Batch Name | Class | Faculty | Students | Capacity | Utilization | Fee / Mo |",
            "| :--- | :--- | :--- | :---: | :---: | :---: | :---: |"
        ]
        for b in batches:
            md.append(
                f"| **{b['batch_name']}** (`{b['batch_code']}`) | Class {b['class_level']} {b['board']} | "
                f"{b['teacher']} | **{b['enrolled_students']}** | {b['max_students']} | {b['utilization_pct']}% | {dynamic_tools.format_inr(b['monthly_fee'])} |"
            )
        return {
            "reply": "\n".join(md),
            "kpis": [{"label": "Active Batches", "value": str(data.get("total_batches", 0)), "color": "blue"}]
        }

    @classmethod
    def _present_staff(cls, data: dict, params: dict) -> dict:
        staff = data.get("staff", [])
        payroll = data.get("total_monthly_payroll", 0.0)
        md = [
            "### 👨‍🏫 Faculty & Staff Directory",
            f"- **Total Staff:** **{data.get('total_staff', 0)}** | **Monthly Payroll:** **{dynamic_tools.format_inr(payroll)}**",
            "",
            "| Name | ID | Designation | Subject | Phone | Salary |",
            "| :--- | :--- | :--- | :--- | :--- | :---: |"
        ]
        for s in staff:
            md.append(f"| **{s['name']}** | `{s['employee_id']}` | {s['designation']} | {s['subject']} | `{s['phone']}` | {dynamic_tools.format_inr(s['salary'])} |")
        return {
            "reply": "\n".join(md),
            "kpis": [{"label": "Monthly Payroll", "value": dynamic_tools.format_inr(payroll), "color": "blue"}]
        }

    @classmethod
    def _present_inquiries(cls, data: dict, params: dict) -> dict:
        inquiries = data.get("inquiries", [])
        md = [
            "### 🎯 Admissions Inquiries & Leads",
            f"- **Total Inquiries:** **{data.get('total', 0)}** | **Pending Follow-up:** **{data.get('pending_followup', 0)}**",
            ""
        ]
        if inquiries:
            md.append("| Name | Phone | Interested Class | Submitted | Followed Up |")
            md.append("| :--- | :--- | :--- | :--- | :---: |")
            for i in inquiries[:25]:
                fu = "✅ Yes" if i["is_followed_up"] else "⏳ Pending"
                md.append(f"| **{i['name']}** | `{i['phone']}` | {i['interested_class']} | {i['submitted_at']} | {fu} |")
        return {
            "reply": "\n".join(md),
            "kpis": [{"label": "Pending Follow-ups", "value": str(data.get("pending_followup", 0)), "color": "amber"}]
        }

    @classmethod
    def _present_overview(cls, data: dict) -> dict:
        md = [
            f"### 🏛️ Success Coaching — Institute Overview ({data.get('today_date')})",
            f"- **Active Students:** **{data.get('active_students', 0)}** (Inactive: {data.get('inactive_students', 0)})",
            f"- **Active Batches:** **{data.get('active_batches', 0)}** | **Active Staff:** **{data.get('active_staff', 0)}**",
            f"- **Fees Billed:** {dynamic_tools.format_inr(data.get('fees_total_billed'))} | **Collected:** {dynamic_tools.format_inr(data.get('fees_total_collected'))} | **Pending:** **{dynamic_tools.format_inr(data.get('fees_total_pending'))}**",
            f"- **Today's Attendance:** {data.get('today_attendance_present', 0)}/{data.get('today_attendance_marked', 0)} present",
            f"- **Pending Admissions Inquiries:** {data.get('pending_inquiries', 0)}",
        ]
        return {
            "reply": "\n".join(md),
            "kpis": [
                {"label": "Active Students", "value": str(data.get("active_students", 0)), "color": "emerald"},
                {"label": "Pending Fees", "value": dynamic_tools.format_inr(data.get("fees_total_pending")), "color": "rose"},
                {"label": "Pending Leads", "value": str(data.get("pending_inquiries", 0)), "color": "amber"},
            ]
        }

    # ==========================================================================
    # CONTEXT PERSISTENCE
    # ==========================================================================

    @classmethod
    def _update_context(cls, conversation, updates: dict):
        """Updates and persists conversational memory in ChatConversation.context_data."""
        ctx = dict(conversation.context_data or {})
        for k, v in updates.items():
            if v is not None:
                ctx[k] = v
        conversation.context_data = ctx
        conversation.save(update_fields=['context_data', 'updated_at'])
