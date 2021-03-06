"""
Copyright 2020 Google LLC

Licensed under the Apache License, Version 2.0 (the 'License');
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an 'AS IS' BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import os
from django.http import Http404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics

from django.contrib.auth.models import User, Group
from guardian.shortcuts import assign_perm, remove_perm

from main.models import Image, BasicUser, Project, AnnotationsJson
from noter_backend.generate_signed_urls import generate_signed_url
from main.permissions import IsOwnerAndReadOnlyOrRefuse, IsOwnerOrReadOnly, IsReadOnlyAndHasAccessOrRefuse, IsReadOnlyAndPublicOrRefuse, IsOwnerOrRefuse
from main.serializers import ImageSerializer, UserSerializer, BasicUserSerializer, ProjectSerializer, AnnotationsJsonSerializer, GroupSerializer


class WhoAmI(APIView):
    """
    Return the email of the authenticated user.
    """
    def get(self, request, format=None):
        return Response({request.user.email})


def get_object_or_404(Model, pk):
    try:
        model = Model.objects.get(pk=pk)
        return model
    except Model.DoesNotExist:
        raise Http404

class GetImage(APIView):
    permission_classes = [IsOwnerAndReadOnlyOrRefuse | IsReadOnlyAndHasAccessOrRefuse | IsReadOnlyAndPublicOrRefuse]

    def get_object(self, pk):
        try:
            image = Image.objects.get(pk=pk)
            self.check_object_permissions(self.request, image)
            return image
        except Image.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        image = self.get_object(pk)
        serializer = ImageSerializer(image)

        response = Response(status=200)
        response['Content-Type'] = ''
        response['Method'] = 'GET'
        path = serializer.data['image'].strip('/').split('/')[-1]
        if os.environ.get('NOTER_GS_MEDIA_BUCKET_NAME','').strip():
            path = generate_signed_url(
                service_account_file=os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'),
                http_method='GET', bucket_name=os.environ.get('NOTER_GS_MEDIA_BUCKET_NAME'),
                object_name=path, subresource='',
                expiration=int(900))

        response['X-Accel-Redirect'] = '/protected_media/' + path.strip('/')
        return response


class ShareImages(APIView):
    permission_classes = [IsOwnerOrRefuse]

    def post(self, request, format=None):
        if 'image_ids' not in request.data or not ('group_ids' in request.data or ('public' in request.data and request.data['public'].lower() == 'true')):
            return Response(status=400)

        for image in Image.objects.filter(id__in=request.data['image_ids']):
            self.check_object_permissions(self.request, image)

            if request.data['public'].lower() == 'true':
                public_group = Group.objects.get(id=1)
                assign_perm('view_obj', public_group, image)
            if 'group_ids' in request.data:
                for group in Group.objects.filter(id__in=request.data['group_ids']):
                    assign_perm('view_obj', group, image)
        return Response(status=200)

    def delete(self, request, format=None):
        if 'image_ids' not in request.data or 'group_ids' not in request.data:
            return Response(status=400)

        for image in Image.objects.filter(id__in=request.data['image_ids']):
            self.check_object_permissions(self.request, image)
            for group in Group.objects.filter(id__in=request.data['group_ids']):
                remove_perm('view_obj', group, image)
        return Response(status=200)

class WhatDoIHave(APIView):
    """
    Return all objects created by the authenticated user.
    """
    permission_classes = [IsOwnerOrRefuse]
    def get(self, request, format=None):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


# class UserList(generics.ListAPIView):
#     queryset = User.objects.all()
#     serializer_class = UserSerializer


# class UserDetail(generics.RetrieveAPIView):
#     queryset = User.objects.all()
#     serializer_class = UserSerializer



class CreateGroup(APIView):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    def post(self, request, format=None):
        serializer = GroupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            group = get_object_or_404(Group, pk= serializer.data['id'])
            request.user.groups.add(group)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# class GroupDetail(generics.RetrieveAPIView):
#     queryset = Group.objects.all()
#     serializer_class = GroupSerializer

class CreateProject(APIView):

    def post(self, request, format=None):
        serializer = ProjectSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(owner_email=request.user.email)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JoinGroup(APIView):
    @staticmethod
    def get_user_or_404(email):
        try:
            user = User.objects.get(email=email)
            return user
        except User.DoesNotExist:
            raise Http404

    @staticmethod
    def get_group_or_404(name):
        try:
            group = Group.objects.get(name=name)
            return group
        except User.DoesNotExist:
            raise Http404

    def post(self, request, group_name):
        if not request.user.groups.filter(name=group_name).exists():
            return Response(status=403)
        if 'email' not in request.data:
            return Response(status=400)

        user = self.get_user_or_404(email = request.data['email'])
        group = self.get_group_or_404(name=group_name)
        user.groups.add(group)
        return Response(status=200)

    def delete(self, request, group_name):
        if not request.user.groups.filter(name=group_name).exists():
            return Response(status=403)
        if 'email' not in request.data:
            return Response(status=400)

        user = self.get_user_or_404(email = request.data['email'])
        group = self.get_group_or_404(name=group_name)
        user.groups.remove(group)
        return Response(status=200)


class ProjectDetail(generics.RetrieveAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_object(self):
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, **filter)
        self.check_object_permissions(self.request, obj)
        return obj



class AnnotationsJsonList(generics.ListAPIView):
    queryset = AnnotationsJson.objects.all()
    serializer_class = AnnotationsJsonSerializer

    def post(self, request, format=None):
        serializer = AnnotationsJsonSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(image_id=request.data['image_id'], owner_email=request.user.email)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class AnnotationsJsonDetail(generics.RetrieveAPIView):
    queryset = AnnotationsJson.objects.all()
    serializer_class = AnnotationsJsonSerializer


class ImageList(APIView):
    """
    List all images, or create a new image.
    """
    def get(self, request, format=None):
        images = Image.objects.all()
        serializer = ImageSerializer(images, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = ImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project_id=request.data['project_id'], owner_email=request.user.email)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ImageDetail(APIView):
    """
    Retrieve, update or delete a image instance.
    """
    permission_classes = [IsOwnerOrRefuse]

    def get_object(self, pk):
        try:
            image = Image.objects.get(pk=pk)
            self.check_object_permissions(self.request, image)
            return image
        except Image.DoesNotExist:
            raise Http404


    def get(self, request, pk, format=None):
        image = self.get_object(pk)
        serializer = ImageSerializer(image)
        return Response(serializer.data)

    # def put(self, request, pk, format=None):
    #     image = self.get_object(pk)
    #     serializer = ImageSerializer(image, data=request.data)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data)
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        image = self.get_object(pk)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)