FROM apache/airflow:2.10.3-python3.12

# Устанавливать пакеты нужно от пользователя airflow (политика образа).
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
