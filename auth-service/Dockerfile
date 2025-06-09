# Dockerfile

# 1. Gunakan base image resmi Python
FROM python:3.9-slim

# 2. Atur direktori kerja di dalam container
WORKDIR /app

# 3. Salin file dependensi dan install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Salin semua file proyek (kode dan templates) ke dalam container
COPY . .

# 5. Beri tahu Docker bahwa container akan berjalan di port 5002
EXPOSE 5002

# 6. Perintah untuk menjalankan aplikasi saat container dimulai
# Menggunakan Gunicorn sebagai production server
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "app:app"]