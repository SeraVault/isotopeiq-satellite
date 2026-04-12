FROM python:3.12-slim

# System deps for psycopg2, python-ldap, pywinrm, djangosaml2/xmlsec1
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        libldap2-dev \
        libsasl2-dev \
        libssl-dev \
        xmlsec1 \
        libxmlsec1-openssl \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
