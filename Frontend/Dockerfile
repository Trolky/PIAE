FROM python:3.12-slim

WORKDIR /app

# GNU gettext tools (msguniq, msgfmt) pro django-admin makemessages/compilemessages
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

# Install deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project
COPY . /app

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "manage.py", "migrate_and_runserver", "0.0.0.0:8000"]
