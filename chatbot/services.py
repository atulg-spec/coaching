import json
import logging
import requests
from .models import ChatbotConfig

logger = logging.getLogger(__name__)

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4/accounts"


class CloudflareAIService:
    @staticmethod
    def get_run_url(account_id: str, model_name: str) -> str:
        clean_account = account_id.strip()
        clean_model = model_name.strip()
        # Ensure model name does not have double slashes if prepended
        if clean_model.startswith('/'):
            clean_model = clean_model[1:]
        return f"{CLOUDFLARE_API_BASE}/{clean_account}/ai/run/{clean_model}"

    @classmethod
    def test_connection(cls, account_id: str, api_token: str, model_name: str = '@cf/meta/llama-3.1-8b-instruct') -> dict:
        """
        Tests the connection to Cloudflare Workers AI with the provided credentials.
        """
        if not account_id or not account_id.strip():
            return {"success": False, "error": "Cloudflare Account ID is missing."}
        if not api_token or not api_token.strip():
            return {"success": False, "error": "Cloudflare API Token is missing."}

        model = model_name or '@cf/meta/llama-3.1-8b-instruct'
        url = cls.get_run_url(account_id, model)
        headers = {
            "Authorization": f"Bearer {api_token.strip()}",
            "Content-Type": "application/json"
        }
        payload = {
            "messages": [
                {"role": "system", "content": "You are an assistant. Respond concisely."},
                {"role": "user", "content": "Say 'Cloudflare Workers AI connection successful!' in one brief sentence."}
            ],
            "max_tokens": 64,
            "temperature": 0.3
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            status_code = response.status_code

            if status_code == 200:
                data = response.json()
                reply = cls._extract_response_text(data)
                return {
                    "success": True,
                    "message": "Connection verified successfully!",
                    "sample_reply": reply,
                    "raw_response": data
                }
            elif status_code == 401 or status_code == 403:
                return {
                    "success": False,
                    "error": f"Authentication failed (HTTP {status_code}). Please verify your Cloudflare API Token has Workers AI permissions."
                }
            elif status_code == 404:
                return {
                    "success": False,
                    "error": f"Resource not found (HTTP 404). Check if the Account ID ({account_id}) or model name ({model}) is correct."
                }
            else:
                err_detail = response.text
                try:
                    err_json = response.json()
                    errors = err_json.get("errors", [])
                    if errors:
                        err_detail = "; ".join([e.get("message", str(e)) for e in errors])
                except Exception:
                    pass
                return {
                    "success": False,
                    "error": f"Cloudflare API Error (HTTP {status_code}): {err_detail}"
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Cloudflare API request timed out (20s). Please try again."}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Network or connection error: {str(e)}"}

    @classmethod
    def query(
        cls,
        conversation_messages: list,
        config: ChatbotConfig = None,
        include_config_system_prompt: bool = True,
        temperature: float = None,
        max_tokens: int = None,
    ) -> dict:
        """
        Sends conversation history to Cloudflare Workers AI and returns the generated response.
        conversation_messages should be a list of dicts: [{'role': 'user'|'assistant'|'system', 'content': '...'}]
        """
        if config is None:
            config = ChatbotConfig.get_settings()

        if not config.is_active:
            return {
                "success": False,
                "error": "The AI Chatbot is currently disabled by institute administration."
            }

        if not config.is_configured:
            return {
                "success": False,
                "not_configured": True,
                "error": "Cloudflare API credentials have not been configured yet. Please configure them in the Admin Panel."
            }

        url = cls.get_run_url(config.account_id, config.model_name)
        headers = {
            "Authorization": f"Bearer {config.api_token.strip()}",
            "Content-Type": "application/json"
        }

        # Build message payload with optional config system prompt
        messages_payload = []
        if include_config_system_prompt and config.system_prompt and config.system_prompt.strip():
            messages_payload.append({
                "role": "system",
                "content": config.system_prompt.strip()
            })

        for msg in conversation_messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if content and role in ['user', 'assistant', 'system']:
                messages_payload.append({
                    "role": role,
                    "content": content
                })

        payload = {
            "messages": messages_payload,
            "max_tokens": max_tokens if max_tokens is not None else (config.max_tokens or 1024),
            "temperature": temperature if temperature is not None else (config.temperature if config.temperature is not None else 0.7)
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=35)
            status_code = response.status_code

            if status_code == 200:
                data = response.json()
                reply_text = cls._extract_response_text(data)
                if not reply_text:
                    reply_text = "I received an empty response from the AI model. Please try again."
                return {
                    "success": True,
                    "reply": reply_text
                }
            elif status_code in (401, 403):
                logger.error("Cloudflare AI Auth error %d: %s", status_code, response.text)
                return {
                    "success": False,
                    "error": "Cloudflare authentication failed. Please ask the administrator to check API credentials."
                }
            else:
                err_msg = f"HTTP {status_code}"
                try:
                    err_json = response.json()
                    errors = err_json.get("errors", [])
                    if errors:
                        err_msg = "; ".join([e.get("message", str(e)) for e in errors])
                except Exception:
                    err_msg = response.text[:200]
                logger.error("Cloudflare AI error: %s", err_msg)
                return {
                    "success": False,
                    "error": f"AI service error: {err_msg}"
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out while waiting for Cloudflare AI response. Please try again."}
        except requests.exceptions.RequestException as e:
            logger.error("Cloudflare request exception: %s", e)
            return {"success": False, "error": f"Could not reach Cloudflare AI service: {str(e)}"}

    @staticmethod
    def _extract_response_text(data: dict) -> str:
        """Robust extractor for different Cloudflare Workers AI response formats."""
        if not isinstance(data, dict):
            return str(data)

        # Standard Cloudflare Workers AI response format: {"result": {"response": "..."}}
        result = data.get("result")
        if isinstance(result, dict):
            resp = result.get("response") or result.get("text") or result.get("output") or result.get("description")
            if resp is not None:
                if isinstance(resp, (dict, list)):
                    return json.dumps(resp)
                return str(resp).strip()
        elif isinstance(result, str):
            return result.strip()

        # Alternate formats (OpenAI-like or direct choices)
        if "response" in data and isinstance(data["response"], str):
            return data["response"].strip()

        choices = data.get("choices")
        if choices and isinstance(choices, list):
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message", {})
                if isinstance(msg, dict) and "content" in msg:
                    return msg["content"].strip()
                if "text" in first:
                    return first["text"].strip()

        return ""
