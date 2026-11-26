import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from .models import ChatbotConfig, ChatConversation, ChatMessage
from .forms import ChatbotConfigForm
from .services import CloudflareAIService
from .natasha_agent import NatashaAgent

logger = logging.getLogger(__name__)


def _is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)


def _get_or_create_user_conversation(request, conversation_id=None):
    """Helper to fetch or create a conversation safely belonging to the requester."""
    if conversation_id:
        if request.user.is_authenticated:
            conv = ChatConversation.objects.filter(id=conversation_id, user=request.user).first()
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.save()
                session_key = request.session.session_key
            conv = ChatConversation.objects.filter(id=conversation_id, session_key=session_key).first()
        if conv:
            return conv

    # Create new conversation
    if request.user.is_authenticated:
        return ChatConversation.objects.create(user=request.user, title="New Chat")
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key
        return ChatConversation.objects.create(session_key=session_key, title="New Chat")


@login_required
@ensure_csrf_cookie
def dashboard_chat_view(request):
    """Chatbot interface for Admin and Staff in the Institute Dashboard."""
    config = ChatbotConfig.get_settings()
    
    # Check permissions
    if not config.enable_for_staff and request.user.role == 'staff':
        messages.warning(request, "AI Chatbot is currently disabled for staff.")
        return redirect('dashboard_home')

    conversations = ChatConversation.objects.filter(user=request.user).order_by('-updated_at')
    active_conv = conversations.first()
    if not active_conv:
        active_conv = ChatConversation.objects.create(user=request.user, title="New Chat")
        conversations = [active_conv]

    context = {
        'config': config,
        'conversations': conversations,
        'active_conversation': active_conv,
        'is_admin': _is_admin(request.user),
    }
    return render(request, 'chatbot/dashboard_chat.html', context)


@login_required
@ensure_csrf_cookie
def student_chat_view(request):
    """AI Tutor Chatbot interface inside the Student Portal."""
    config = ChatbotConfig.get_settings()

    if not config.enable_for_students and request.user.role == 'student':
        messages.warning(request, "AI Tutor is currently disabled by institute administration.")
        return redirect('student_portal_home')

    conversations = ChatConversation.objects.filter(user=request.user).order_by('-updated_at')
    active_conv = conversations.first()
    if not active_conv:
        active_conv = ChatConversation.objects.create(user=request.user, title="New Study Chat")
        conversations = [active_conv]

    context = {
        'config': config,
        'conversations': conversations,
        'active_conversation': active_conv,
    }
    return render(request, 'chatbot/student_chat.html', context)


@login_required
def admin_settings_view(request):
    """Admin configuration panel for Cloudflare API credentials and model tuning."""
    if not _is_admin(request.user):
        messages.error(request, "Access restricted to administrators.")
        return redirect('dashboard_home')

    config = ChatbotConfig.get_settings()

    if request.method == 'POST':
        form = ChatbotConfigForm(request.POST, instance=config)
        if form.is_valid():
            # If the user leaves api_token empty when saving and we already had one, keep existing token
            new_token = form.cleaned_data.get('api_token')
            instance = form.save(commit=False)
            if not new_token and config.api_token:
                instance.api_token = config.api_token
            instance.save()
            messages.success(request, "Cloudflare AI configuration updated successfully!")
            return redirect('chatbot_settings')
        else:
            messages.error(request, "Please check the form for errors.")
    else:
        form = ChatbotConfigForm(instance=config)

    context = {
        'form': form,
        'config': config,
        'is_configured': config.is_configured,
        'models_list': ChatbotConfig.MODEL_CHOICES,
    }
    return render(request, 'chatbot/settings.html', context)


@login_required
@require_POST
def api_test_connection(request):
    """Test Cloudflare Workers AI connection with saved or newly entered credentials."""
    if not _is_admin(request.user):
        return HttpResponseForbidden("Admin access required.")

    account_id = request.POST.get('account_id', '').strip()
    api_token = request.POST.get('api_token', '').strip()
    model_name = request.POST.get('model_name', '').strip()

    config = ChatbotConfig.get_settings()

    # Fall back to saved credentials if blank in POST
    if not account_id:
        account_id = config.account_id
    if not api_token:
        api_token = config.api_token
    if not model_name:
        model_name = config.model_name

    result = CloudflareAIService.test_connection(account_id, api_token, model_name)
    return JsonResponse(result)


@require_POST
def api_send_message(request):
    """
    Main endpoint for sending chat messages to Cloudflare AI.
    Accepts JSON payload: { 'message': str, 'conversation_id': int }
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    user_text = data.get('message', '').strip()
    conversation_id = data.get('conversation_id')

    if not user_text:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty.'}, status=400)

    config = ChatbotConfig.get_settings()

    # Permission checks
    if request.user.is_authenticated:
        if request.user.role == 'student' and not config.enable_for_students:
            return JsonResponse({'success': False, 'error': 'AI Chatbot disabled for students.'}, status=403)
        if request.user.role == 'staff' and not config.enable_for_staff:
            return JsonResponse({'success': False, 'error': 'AI Chatbot disabled for staff.'}, status=403)
    else:
        if not config.enable_public_widget:
            return JsonResponse({'success': False, 'error': 'Public chatbot is disabled.'}, status=403)

    # Fetch or create conversation
    conv = _get_or_create_user_conversation(request, conversation_id)

    # Save user message
    ChatMessage.objects.create(conversation=conv, role='user', content=user_text)

    # If conversation is default named, give it a title based on first user query
    if conv.title in ["New Chat", "New Conversation", "New Study Chat", "Natasha Assistant"]:
        short_title = user_text[:35].strip()
        if len(user_text) > 35:
            short_title += "..."
        conv.title = short_title
        conv.save(update_fields=['title', 'updated_at'])
    else:
        conv.save(update_fields=['updated_at'])

    # 1. Admin & Staff Persona: Natasha Personal Assistant (Queries actual ERP database)
    if request.user.is_authenticated and (request.user.role in ['admin', 'staff'] or request.user.is_superuser):
        natasha_res = NatashaAgent.process_query(user_text, conv, user=request.user)
        reply_content = natasha_res.get('reply', '')
        bot_msg = ChatMessage.objects.create(conversation=conv, role='assistant', content=reply_content)
        return JsonResponse({
            'success': True,
            'reply': reply_content,
            'kpis': natasha_res.get('kpis'),
            'conversation_id': conv.id,
            'conversation_title': conv.title,
            'message_id': bot_msg.id,
            'created_at': bot_msg.created_at.strftime("%I:%M %p")
        })

    # 2. Student Portal & Public Guest Queries: Powered by Cloudflare Workers AI
    if not config.is_configured:
        return JsonResponse({
            'success': False,
            'not_configured': True,
            'error': 'Cloudflare API credentials have not been configured yet in the admin panel.'
        }, status=200)

    # Build context window from conversation history (last 10 messages)
    recent_msgs = conv.messages.order_by('-created_at')[:10]
    ordered_msgs = list(reversed(recent_msgs))
    history_payload = [{'role': m.role, 'content': m.content} for m in ordered_msgs]

    # Call Cloudflare AI
    ai_result = CloudflareAIService.query(history_payload, config=config)

    if ai_result.get('success'):
        reply_content = ai_result.get('reply', '')
        bot_msg = ChatMessage.objects.create(conversation=conv, role='assistant', content=reply_content)
        return JsonResponse({
            'success': True,
            'reply': reply_content,
            'conversation_id': conv.id,
            'conversation_title': conv.title,
            'message_id': bot_msg.id,
            'created_at': bot_msg.created_at.strftime("%I:%M %p")
        })
    else:
        return JsonResponse({
            'success': False,
            'error': ai_result.get('error', 'Failed to generate response.'),
            'not_configured': ai_result.get('not_configured', False),
            'conversation_id': conv.id
        })


@login_required
def api_get_conversations(request):
    """Retrieve list of user's saved conversations."""
    convs = ChatConversation.objects.filter(user=request.user).order_by('-updated_at')
    data = [{
        'id': c.id,
        'title': c.title,
        'updated_at': c.updated_at.strftime("%b %d, %I:%M %p"),
        'count': c.messages.count()
    } for c in convs]
    return JsonResponse({'success': True, 'conversations': data})


def api_get_messages(request, conversation_id):
    """Retrieve message history for a conversation."""
    if request.user.is_authenticated:
        conv = get_object_or_404(ChatConversation, id=conversation_id, user=request.user)
    else:
        session_key = request.session.session_key
        conv = get_object_or_404(ChatConversation, id=conversation_id, session_key=session_key)

    msgs = conv.messages.all().order_by('created_at')
    data = [{
        'id': m.id,
        'role': m.role,
        'content': m.content,
        'created_at': m.created_at.strftime("%I:%M %p")
    } for m in msgs]

    return JsonResponse({
        'success': True,
        'conversation_id': conv.id,
        'title': conv.title,
        'messages': data
    })


@require_POST
def api_new_conversation(request):
    """Create a new blank conversation."""
    title = "New Study Chat" if request.user.is_authenticated and request.user.role == 'student' else "New Chat"
    if request.user.is_authenticated:
        conv = ChatConversation.objects.create(user=request.user, title=title)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key
        conv = ChatConversation.objects.create(session_key=session_key, title=title)

    return JsonResponse({
        'success': True,
        'id': conv.id,
        'title': conv.title
    })


@require_POST
def api_delete_conversation(request, conversation_id):
    """Delete a conversation."""
    if request.user.is_authenticated:
        conv = get_object_or_404(ChatConversation, id=conversation_id, user=request.user)
    else:
        session_key = request.session.session_key
        conv = get_object_or_404(ChatConversation, id=conversation_id, session_key=session_key)

    conv.delete()
    return JsonResponse({'success': True})
