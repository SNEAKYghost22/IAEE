# Tahap 1: Gunakan base image resmi Python yang ringan.
FROM python:3.9-slim

# Tahap 2: Tentukan direktori kerja di dalam kontainer.
WORKDIR /app

# Tahap 3: Salin file requirements dan install dependensi.
# Ini dilakukan terpisah agar Docker bisa menggunakan cache-nya jika dependensi tidak berubah.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tahap 4: Salin seluruh kode proyek ke dalam direktori kerja di kontainer.
COPY . .

# Tahap 5: Buka port yang akan digunakan oleh Gunicorn untuk menerima koneksi.
EXPOSE 5004

# Tahap 6: Perintah default untuk menjalankan aplikasi saat kontainer dimulai.
# Ini menjalankan Gunicorn, mengikatnya ke semua alamat IP pada port 5002.
# 'app:app' berarti: dari file 'app.py', gunakan variabel bernama 'app'.
CMD ["gunicorn", "--bind", "0.0.0.0:5004", "app:app"]