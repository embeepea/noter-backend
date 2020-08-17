# Copyright 2015, Google, Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START docker]

# The Google App Engine python runtime is Debian Jessie with Python installed
# and various os-level packages to allow installation of popular Python
# libraries. The source is on github at:
# https://github.com/GoogleCloudPlatform/python-docker

FROM gcr.io/google_appengine/python

# Create a virtualenv for the application dependencies.
RUN virtualenv -p python3 /env
ENV PATH /env/bin:$PATH

ADD . /noter-backend
RUN /env/bin/pip install --upgrade pip && /env/bin/pip install -r /noter-backend/requirements.txt


RUN apt-get update
RUN apt-get upgrade -y
RUN apt-get install -y \
        postgresql \
        postgresql-contrib

# [END docker]
