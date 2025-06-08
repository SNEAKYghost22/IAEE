# Langkah 1: Pilih base image Python yang efisien
FROM python:3.9-slim

# Langkah 2: Set direktori kerja di dalam kontainer
WORKDIR /app

# Langkah 3: Salin file dependensi dan install
# Menyalin requirements.txt terlebih dahulu memanfaatkan cache Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Langkah 4: Salin semua file proyek ke dalam direktori kerja di kontainer
# Ini termasuk app.py dan folder templates
COPY . .

# Langkah 5: Buka port yang digunakan oleh aplikasi
EXPOSE 5002

# Langkah 6: Perintah untuk menjalankan aplikasi saat kontainer dimulai
# Menggunakan Gunicorn sebagai server produksi
# app:app -> merujuk ke variabel 'app' di dalam file 'app.py'
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "app:app"]