# Template Dockerfile untuk setiap layanan
# Ganti 5001 dengan port yang sesuai (5002, 5003, 5004, 5005)

# 1. Gunakan base image resmi Python
FROM python:3.9-slim

# 2. Atur direktori kerja
WORKDIR /app

# 3. Salin dan install dependensi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Salin sisa file proyek
COPY . .

# 5. EXPOSE PORT (GANTI NOMOR PORT INI)
EXPOSE 5001

# 6. Perintah untuk menjalankan aplikasi (GANTI NOMOR PORT INI)
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--log-level", "debug", "app:app"]