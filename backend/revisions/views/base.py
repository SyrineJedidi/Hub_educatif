"""Shared base of the module views."""
from rest_framework.response import Response
from accounts.permissions import ActiveAccount
from accounts.views import SecureView
from ..serializers import SheetDetailSerializer


def detail(sheet, request, status=200):
    return Response(SheetDetailSerializer(sheet, context={'user': request.user}).data, status=status)




class SheetView(SecureView):
    permission_classes = [ActiveAccount]
