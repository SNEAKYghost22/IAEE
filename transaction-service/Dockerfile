# Dockerfile untuk Transaction Service

# 1. Gunakan base image resmi Python yang ringan
FROM python:3.9-slim

# 2. Atur direktori kerja di dalam container
WORKDIR /app

# 3. Salin file dependensi dan install terlebih dahulu untuk caching layer Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Salin semua sisa file proyek (kode dan folder templates) ke dalam container
COPY . .

# 5. Beri tahu Docker bahwa container akan berjalan di port 5003
EXPOSE 5003

# 6. Perintah untuk menjalankan aplikasi saat container dimulai
#    Menggunakan Gunicorn sebagai production-ready server
CMD ["gunicorn", "--bind", "0.0.0.0:5003", "app:app"]