FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends socat && apt-get clean
ENV PYTHONUNBUFFERED=1
COPY start.sh /start.sh
ENTRYPOINT ["bash", "/start.sh"]
