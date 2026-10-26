from django.conf import settings
from django.http import HttpResponse
from rest_framework.response import Response
from accounts.views import SecureView, validated
from ai.transcription import provider_status as transcription_status
from classrooms.services import paginated
from .permissions import AssistantUser
from .serializers import (ConversationCreateSerializer, ConversationUpdateSerializer, FeedbackSerializer, MessageCreateSerializer,
    conversation_data, message_data, scope_data)
from .services import (SendAccess, ask, can_send, chat_scopes, check_conversation_rate, check_spam, create_conversation, delete_feedback, export_markdown,
    feedback_by_message, filtered_conversations, message_page, own_conversation, own_message, put_feedback, question_quota,
    restore, settings_rows, settings_row, teachers_by_id, trash, update_conversation)
from .voice import transcribe_question


class AssistantView(SecureView):
    permission_classes = [AssistantUser]


class ScopesView(AssistantView):
    def get(self, request):
        scopes = chat_scopes(request.user)
        rows, teachers = settings_rows(scopes), teachers_by_id(scopes)
        return Response({'results': [scope_data(s, rows[s.key], question_quota(request.user, s.source_type, s.scope_id, rows[s.key]),
            teachers.get(s.teacher_id)) for s in scopes], 'voice': {'available': transcription_status()['configured'],
            'max_seconds': settings.ASSISTANT_MAX_AUDIO_SECONDS, 'max_mb': settings.ASSISTANT_MAX_AUDIO_MB}})


class ConversationsView(AssistantView):
    def get(self, request):
        access = SendAccess(request.user)
        return Response(paginated(request, filtered_conversations(request), lambda c: conversation_data(c, access(c))))

    def post(self, request):
        check_conversation_rate(request)
        data = validated(ConversationCreateSerializer, request)
        conversation = create_conversation(request.user, data)
        return Response(conversation_data(conversation, True), status=201)


class ConversationDetailView(AssistantView):
    def get(self, request, uid):
        conversation = own_conversation(request.user, uid)
        return Response(conversation_data(conversation, can_send(request.user, conversation)))

    def patch(self, request, uid):
        conversation = own_conversation(request.user, uid)
        data = validated(ConversationUpdateSerializer, request)
        conversation = update_conversation(request.user, conversation, data)
        return Response(conversation_data(conversation, can_send(request.user, conversation)))

    def delete(self, request, uid):
        conversation = trash(own_conversation(request.user, uid))
        return Response(conversation_data(conversation, False))


class RestoreView(AssistantView):
    def post(self, request, uid):
        conversation = restore(own_conversation(request.user, uid))
        return Response(conversation_data(conversation, can_send(request.user, conversation)))


class MessagesView(AssistantView):
    def get(self, request, uid):
        conversation = own_conversation(request.user, uid)
        messages, has_more = message_page(request, conversation)
        feedback = feedback_by_message(messages)
        return Response({'results': [message_data(m, feedback.get(m.pk)) for m in messages], 'has_more': has_more})

    def post(self, request, uid):
        check_spam(request)
        conversation = own_conversation(request.user, uid)
        data = validated(MessageCreateSerializer, request)
        question, answer, replayed = ask(request, conversation, data)
        conversation.refresh_from_db()
        feedback = feedback_by_message([answer]) if replayed else {}
        row = settings_row(conversation.source_type, conversation.scope_id)
        return Response({'question': message_data(question), 'answer': message_data(answer, feedback.get(answer.pk)),
            'conversation': conversation_data(conversation, can_send(request.user, conversation) if replayed else True),
            'quota': question_quota(request.user, conversation.source_type, conversation.scope_id, row)}, status=200 if replayed else 201)


class ExportView(AssistantView):
    def get(self, request, uid):
        conversation = own_conversation(request.user, uid)
        response = HttpResponse(export_markdown(conversation), content_type='text/markdown; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="conversation-{conversation.pk}.md"'
        return response


class FeedbackView(AssistantView):
    def put(self, request, uid):
        message, conversation = own_message(request.user, uid)
        data = validated(FeedbackSerializer, request)
        feedback = put_feedback(request.user, message, conversation, data)
        return Response(message_data(message, feedback))

    def delete(self, request, uid):
        message, _ = own_message(request.user, uid)
        delete_feedback(message)
        return Response(status=204)


class TranscriptionView(AssistantView):
    def post(self, request):
        return Response(transcribe_question(request))


