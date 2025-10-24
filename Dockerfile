FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1

ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --upgrade pip && pip install -r requirements.txt

COPY web/ ./

#CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]


